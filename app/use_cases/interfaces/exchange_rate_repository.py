"""Persistence contract for cached exchange rates."""

from abc import ABC, abstractmethod
from datetime import date

from app.use_cases.interfaces.exchange_rate_provider import ProviderRate


class ExchangeRateRepositoryInterface(ABC):
    """Storage port used by the conversion service."""

    @abstractmethod
    def get(
        self,
        base_currency: str,
        quote_currency: str,
        requested_date: date,
        provider: str,
    ) -> ProviderRate | None:
        """Return a cached rate for an exact lookup key."""

    @abstractmethod
    def save(self, rate: ProviderRate) -> ProviderRate:
        """Persist a provider rate for future conversions."""
