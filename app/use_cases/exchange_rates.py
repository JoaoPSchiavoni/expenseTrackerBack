"""Application service for deterministic currency conversion."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.entities import normalize_money, normalize_rate
from app.use_cases.interfaces.exchange_rate_provider import (
    ExchangeRateProviderInterface,
    ProviderRate,
    SupportedCurrency,
)
from app.use_cases.interfaces.exchange_rate_repository import ExchangeRateRepositoryInterface


@dataclass(frozen=True)
class ConversionQuote:
    base_currency: str
    quote_currency: str
    amount: Decimal
    converted_amount: Decimal
    rate: Decimal
    requested_date: date
    effective_date: date
    provider: str


class ExchangeRateService:
    """Resolve, cache, and apply daily reference rates."""

    def __init__(
        self,
        repository: ExchangeRateRepositoryInterface,
        provider: ExchangeRateProviderInterface,
    ) -> None:
        self.repository = repository
        self.provider = provider

    def get_rate(self, base_currency: str, quote_currency: str, on_date: date) -> ProviderRate:
        base = base_currency.upper()
        quote = quote_currency.upper()
        if base == quote:
            return ProviderRate(
                base_currency=base,
                quote_currency=quote,
                requested_date=on_date,
                effective_date=on_date,
                rate=normalize_rate(1),
                provider="identity",
            )
        cached = self.repository.get(base, quote, on_date, self.provider.name)
        if cached is not None:
            return cached
        return self.repository.save(self.provider.fetch_rate(base, quote, on_date))

    def quote(
        self,
        amount: Decimal,
        base_currency: str,
        quote_currency: str,
        on_date: date,
    ) -> ConversionQuote:
        provider_rate = self.get_rate(base_currency, quote_currency, on_date)
        normalized_amount = normalize_money(amount)
        return ConversionQuote(
            base_currency=provider_rate.base_currency,
            quote_currency=provider_rate.quote_currency,
            amount=normalized_amount,
            converted_amount=normalize_money(normalized_amount * provider_rate.rate),
            rate=provider_rate.rate,
            requested_date=provider_rate.requested_date,
            effective_date=provider_rate.effective_date,
            provider=provider_rate.provider,
        )

    def list_currencies(self) -> list[SupportedCurrency]:
        return self.provider.list_currencies()
