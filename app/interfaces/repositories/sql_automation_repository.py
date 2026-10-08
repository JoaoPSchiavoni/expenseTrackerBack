"""SQLAlchemy adapter for categorization rules, subscriptions, and billing alerts."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.domain.entities import (
    BillingAlert,
    BillingAlertType,
    CategorizationRule,
    DetectedSubscription,
    RuleMatchType,
    SubscriptionStatus,
)
from app.infrastructure.database.models import (
    BillingAlertModel,
    CategorizationRuleModel,
    DetectedSubscriptionModel,
    TransactionModel,
    WalletModel,
)


class SqlAutomationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _rule(model: CategorizationRuleModel) -> CategorizationRule:
        return CategorizationRule(
            id=model.id,
            user_id=model.user_id,
            category_id=model.category_id,
            name=model.name,
            pattern=model.pattern,
            match_type=RuleMatchType(model.match_type),
            priority=model.priority,
            applies_to_imports=model.applies_to_imports,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def create_rule(self, rule: CategorizationRule) -> CategorizationRule:
        model = CategorizationRuleModel(
            user_id=rule.user_id,
            category_id=rule.category_id,
            name=rule.name,
            pattern=rule.pattern,
            match_type=rule.match_type.value,
            priority=rule.priority,
            applies_to_imports=rule.applies_to_imports,
            is_active=rule.is_active,
        )
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return self._rule(model)

    def list_rules(self, user_id: int, *, active_only: bool = False) -> list[CategorizationRule]:
        query = self.session.query(CategorizationRuleModel).filter(
            CategorizationRuleModel.user_id == user_id
        )
        if active_only:
            query = query.filter(CategorizationRuleModel.is_active.is_(True))
        models = query.order_by(
            CategorizationRuleModel.priority.asc(), CategorizationRuleModel.id.asc()
        ).all()
        return [self._rule(model) for model in models]

    def get_rule(self, rule_id: int, user_id: int) -> CategorizationRule | None:
        model = self.session.query(CategorizationRuleModel).filter(
            CategorizationRuleModel.id == rule_id,
            CategorizationRuleModel.user_id == user_id,
        ).first()
        return self._rule(model) if model else None

    def update_rule(self, rule: CategorizationRule) -> CategorizationRule:
        model = self.session.get(CategorizationRuleModel, rule.id)
        if model is None or model.user_id != rule.user_id:
            raise ValueError("Categorization rule not found")
        model.category_id = rule.category_id
        model.name = rule.name
        model.pattern = rule.pattern
        model.match_type = rule.match_type.value
        model.priority = rule.priority
        model.applies_to_imports = rule.applies_to_imports
        model.is_active = rule.is_active
        model.updated_at = datetime.now(UTC)
        self.session.flush()
        self.session.refresh(model)
        return self._rule(model)

    def delete_rule(self, rule_id: int, user_id: int) -> None:
        model = self.session.query(CategorizationRuleModel).filter(
            CategorizationRuleModel.id == rule_id,
            CategorizationRuleModel.user_id == user_id,
        ).first()
        if model is None:
            raise ValueError("Categorization rule not found")
        self.session.delete(model)
        self.session.flush()

    def expense_history(self, user_id: int) -> list[tuple[TransactionModel, WalletModel]]:
        rows = (
            self.session.query(TransactionModel, WalletModel)
            .join(WalletModel, TransactionModel.wallet_id == WalletModel.id)
            .filter(
                WalletModel.user_id == user_id,
                TransactionModel.transaction_type == "EXPENSE",
                TransactionModel.description.is_not(None),
            )
            .order_by(TransactionModel.occurred_at.asc())
            .all()
        )
        return [(transaction, wallet) for transaction, wallet in rows]

    @staticmethod
    def _subscription(model: DetectedSubscriptionModel) -> DetectedSubscription:
        return DetectedSubscription(
            id=model.id,
            user_id=model.user_id,
            wallet_id=model.wallet_id,
            category_id=model.category_id,
            merchant_name=model.merchant_name,
            normalized_key=model.normalized_key,
            average_amount=model.average_amount,
            currency=model.currency,
            frequency=model.frequency,
            next_expected_date=model.next_expected_date,
            last_charge_date=model.last_charge_date,
            confidence=model.confidence,
            status=SubscriptionStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def upsert_subscription(self, item: DetectedSubscription) -> DetectedSubscription:
        model = self.session.query(DetectedSubscriptionModel).filter(
            DetectedSubscriptionModel.user_id == item.user_id,
            DetectedSubscriptionModel.wallet_id == item.wallet_id,
            DetectedSubscriptionModel.normalized_key == item.normalized_key,
        ).first()
        if model is None:
            model = DetectedSubscriptionModel(
                user_id=item.user_id,
                wallet_id=item.wallet_id,
                normalized_key=item.normalized_key,
                status=item.status.value,
            )
            self.session.add(model)
        model.category_id = item.category_id
        model.merchant_name = item.merchant_name
        model.average_amount = item.average_amount
        model.currency = item.currency
        model.frequency = item.frequency
        model.next_expected_date = item.next_expected_date
        model.last_charge_date = item.last_charge_date
        model.confidence = item.confidence
        model.updated_at = datetime.now(UTC)
        self.session.flush()
        self.session.refresh(model)
        self.session.query(BillingAlertModel).filter(
            BillingAlertModel.subscription_id == model.id,
            BillingAlertModel.expected_date <= model.last_charge_date,
            BillingAlertModel.resolved_at.is_(None),
        ).update({BillingAlertModel.resolved_at: datetime.now(UTC)})
        return self._subscription(model)

    def list_subscriptions(self, user_id: int) -> list[DetectedSubscription]:
        models = self.session.query(DetectedSubscriptionModel).filter(
            DetectedSubscriptionModel.user_id == user_id
        ).order_by(
            DetectedSubscriptionModel.status.asc(),
            DetectedSubscriptionModel.next_expected_date.asc(),
        ).all()
        return [self._subscription(model) for model in models]

    def get_subscription(self, subscription_id: int, user_id: int) -> DetectedSubscription | None:
        model = self.session.query(DetectedSubscriptionModel).filter(
            DetectedSubscriptionModel.id == subscription_id,
            DetectedSubscriptionModel.user_id == user_id,
        ).first()
        return self._subscription(model) if model else None

    def set_subscription_status(
        self, subscription_id: int, user_id: int, status: SubscriptionStatus
    ) -> DetectedSubscription:
        model = self.session.query(DetectedSubscriptionModel).filter(
            DetectedSubscriptionModel.id == subscription_id,
            DetectedSubscriptionModel.user_id == user_id,
        ).first()
        if model is None:
            raise ValueError("Detected subscription not found")
        model.status = status.value
        model.updated_at = datetime.now(UTC)
        self.session.flush()
        self.session.refresh(model)
        return self._subscription(model)

    @staticmethod
    def _alert(model: BillingAlertModel) -> BillingAlert:
        return BillingAlert(
            id=model.id,
            user_id=model.user_id,
            subscription_id=model.subscription_id,
            alert_type=BillingAlertType(model.alert_type),
            expected_date=model.expected_date,
            expected_amount=model.expected_amount,
            currency=model.currency,
            read_at=model.read_at,
            resolved_at=model.resolved_at,
            created_at=model.created_at,
        )

    def upsert_alert(self, alert: BillingAlert) -> BillingAlert:
        model = self.session.query(BillingAlertModel).filter(
            BillingAlertModel.subscription_id == alert.subscription_id,
            BillingAlertModel.expected_date == alert.expected_date,
            BillingAlertModel.alert_type == alert.alert_type.value,
        ).first()
        if model is None:
            model = BillingAlertModel(
                user_id=alert.user_id,
                subscription_id=alert.subscription_id,
                alert_type=alert.alert_type.value,
                expected_date=alert.expected_date,
                expected_amount=alert.expected_amount,
                currency=alert.currency,
            )
            self.session.add(model)
            self.session.flush()
            self.session.refresh(model)
        return self._alert(model)

    def list_alerts(self, user_id: int, *, include_resolved: bool = False) -> list[BillingAlert]:
        query = self.session.query(BillingAlertModel).filter(BillingAlertModel.user_id == user_id)
        if not include_resolved:
            query = query.filter(BillingAlertModel.resolved_at.is_(None))
        models = query.order_by(
            BillingAlertModel.expected_date.asc(), BillingAlertModel.created_at.desc()
        ).all()
        return [self._alert(model) for model in models]

    def mark_alert_read(self, alert_id: int, user_id: int) -> BillingAlert:
        model = self.session.query(BillingAlertModel).filter(
            BillingAlertModel.id == alert_id, BillingAlertModel.user_id == user_id
        ).first()
        if model is None:
            raise ValueError("Billing alert not found")
        model.read_at = datetime.now(UTC)
        self.session.flush()
        self.session.refresh(model)
        return self._alert(model)
