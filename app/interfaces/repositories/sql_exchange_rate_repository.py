"""SQLAlchemy adapter for exchange-rate caching."""

from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database.models import ExchangeRateModel
from app.use_cases.interfaces.exchange_rate_provider import ProviderRate
from app.use_cases.interfaces.exchange_rate_repository import ExchangeRateRepositoryInterface


class SqlExchangeRateRepository(ExchangeRateRepositoryInterface):
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _to_rate(model: ExchangeRateModel) -> ProviderRate:
        return ProviderRate(
            base_currency=model.base_currency,
            quote_currency=model.quote_currency,
            requested_date=model.requested_date,
            effective_date=model.effective_date,
            rate=model.rate,
            provider=model.provider,
        )

    def get(
        self,
        base_currency: str,
        quote_currency: str,
        requested_date: date,
        provider: str,
    ) -> ProviderRate | None:
        model = (
            self.session.query(ExchangeRateModel)
            .filter(
                ExchangeRateModel.base_currency == base_currency,
                ExchangeRateModel.quote_currency == quote_currency,
                ExchangeRateModel.requested_date == requested_date,
                ExchangeRateModel.provider == provider,
            )
            .first()
        )
        return self._to_rate(model) if model else None

    def save(self, rate: ProviderRate) -> ProviderRate:
        existing = self.get(
            rate.base_currency,
            rate.quote_currency,
            rate.requested_date,
            rate.provider,
        )
        if existing is not None:
            return existing
        model = ExchangeRateModel(
            base_currency=rate.base_currency,
            quote_currency=rate.quote_currency,
            requested_date=rate.requested_date,
            effective_date=rate.effective_date,
            rate=rate.rate,
            provider=rate.provider,
        )
        try:
            with self.session.begin_nested():
                self.session.add(model)
                self.session.flush()
        except IntegrityError:
            concurrent = self.get(
                rate.base_currency,
                rate.quote_currency,
                rate.requested_date,
                rate.provider,
            )
            if concurrent is None:
                raise
            return concurrent
        self.session.refresh(model)
        return self._to_rate(model)
