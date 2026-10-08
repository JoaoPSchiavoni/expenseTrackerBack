"""Financial automation: categorization rules and recurring-charge detection."""

import re
import statistics
import unicodedata
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from app.domain.entities import (
    BillingAlert,
    BillingAlertType,
    CategorizationRule,
    DetectedSubscription,
    RuleMatchType,
    SubscriptionStatus,
    normalize_money,
    require_id,
)
from app.infrastructure.database.models import TransactionModel, WalletModel
from app.interfaces.repositories.sql_automation_repository import SqlAutomationRepository


class AutomationService:
    def __init__(self, repository: SqlAutomationRepository) -> None:
        self.repository = repository

    @staticmethod
    def _matches(rule: CategorizationRule, description: str) -> bool:
        candidate = description.casefold().strip()
        pattern = rule.pattern.casefold().strip()
        if rule.match_type == RuleMatchType.EXACT:
            return candidate == pattern
        if rule.match_type == RuleMatchType.REGEX:
            try:
                return re.search(rule.pattern, description, flags=re.IGNORECASE) is not None
            except re.error:
                return False
        return pattern in candidate

    def match_category(
        self, user_id: int, description: str | None, *, imports_only: bool = False
    ) -> int | None:
        if not description:
            return None
        for rule in self.repository.list_rules(user_id, active_only=True):
            if imports_only and not rule.applies_to_imports:
                continue
            if self._matches(rule, description):
                return rule.category_id
        return None

    @staticmethod
    def validate_pattern(match_type: RuleMatchType, pattern: str) -> None:
        if not pattern.strip():
            raise ValueError("Rule pattern cannot be empty")
        if match_type == RuleMatchType.REGEX:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"Invalid regular expression: {exc}") from exc

    @staticmethod
    def normalize_merchant(description: str) -> str:
        normalized = unicodedata.normalize("NFKD", description)
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = normalized.casefold()
        normalized = re.sub(r"\b(compra|pagamento|debito|credito|pix|cartao)\b", " ", normalized)
        normalized = re.sub(r"\d+", " ", normalized)
        normalized = re.sub(r"[^a-z]+", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()[:160]

    def detect_subscriptions(self, user_id: int) -> list[DetectedSubscription]:
        grouped: dict[
            tuple[int, str], list[tuple[TransactionModel, WalletModel]]
        ] = defaultdict(list)
        for transaction, wallet in self.repository.expense_history(user_id):
            key = self.normalize_merchant(transaction.description or "")
            if key:
                grouped[(wallet.id, key)].append((transaction, wallet))

        detected: list[DetectedSubscription] = []
        for (wallet_id, key), rows in grouped.items():
            if len(rows) < 3:
                continue
            rows.sort(key=lambda pair: pair[0].occurred_at)
            gaps = [
                (rows[index][0].occurred_at.date() - rows[index - 1][0].occurred_at.date()).days
                for index in range(1, len(rows))
            ]
            median_gap = statistics.median(gaps)
            if 5 <= median_gap <= 9:
                frequency, interval = "WEEKLY", 7
            elif 20 <= median_gap <= 40:
                frequency, interval = "MONTHLY", 30
            elif 330 <= median_gap <= 400:
                frequency, interval = "YEARLY", 365
            else:
                continue

            amounts = [Decimal(str(pair[0].amount)) for pair in rows]
            average = sum(amounts, Decimal("0")) / len(amounts)
            if average <= 0 or (max(amounts) - min(amounts)) / average > Decimal("0.20"):
                continue
            gap_total = sum(
                (abs(Decimal(str(gap)) - Decimal(str(median_gap))) for gap in gaps),
                Decimal("0"),
            )
            gap_deviation = gap_total / Decimal(max(len(gaps), 1))
            confidence = max(
                Decimal("60"),
                min(Decimal("99"), Decimal("98") - gap_deviation * Decimal("2")),
            )
            latest, wallet = rows[-1]
            next_expected = latest.occurred_at.date() + timedelta(days=interval)
            category_ids = [pair[0].category_id for pair in rows if pair[0].category_id]
            category_id = max(set(category_ids), key=category_ids.count) if category_ids else None
            detected.append(
                self.repository.upsert_subscription(
                    DetectedSubscription(
                        user_id=user_id,
                        wallet_id=wallet_id,
                        category_id=category_id,
                        merchant_name=(latest.description or key)[:160],
                        normalized_key=key,
                        average_amount=normalize_money(average),
                        currency=wallet.currency,
                        frequency=frequency,
                        next_expected_date=next_expected,
                        last_charge_date=latest.occurred_at.date(),
                        confidence=confidence.quantize(Decimal("0.01")),
                    )
                )
            )
        return detected

    def sync_alerts(
        self, user_id: int, *, today: date, days_ahead: int = 7
    ) -> list[BillingAlert]:
        self.detect_subscriptions(user_id)
        cutoff = today + timedelta(days=days_ahead)
        alerts: list[BillingAlert] = []
        for subscription in self.repository.list_subscriptions(user_id):
            if (
                subscription.status != SubscriptionStatus.ACTIVE
                or subscription.next_expected_date > cutoff
            ):
                continue
            alert_type = (
                BillingAlertType.OVERDUE
                if subscription.next_expected_date < today
                else BillingAlertType.DUE_SOON
            )
            alerts.append(
                self.repository.upsert_alert(
                    BillingAlert(
                        user_id=user_id,
                        subscription_id=require_id(subscription.id),
                        alert_type=alert_type,
                        expected_date=subscription.next_expected_date,
                        expected_amount=subscription.average_amount,
                        currency=subscription.currency,
                    )
                )
            )
        return alerts
