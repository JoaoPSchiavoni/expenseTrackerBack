"""External exchange-rate provider contract."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class ProviderRate:
    """Rate returned by a provider, including its effective market date."""

    base_currency: str
    quote_currency: str
    requested_date: date
    effective_date: date
    rate: Decimal
    provider: str


@dataclass(frozen=True)
class SupportedCurrency:
    """Currency metadata exposed by the provider."""

    code: str
    name: str
    symbol: str | None = None


class ExchangeRateProviderInterface(ABC):
    """Port implemented by an external source of reference rates."""

    name: str

    @abstractmethod
    def fetch_rate(self, base_currency: str, quote_currency: str, on_date: date) -> ProviderRate:
        """Fetch the reference rate for a currency pair and requested date."""

    @abstractmethod
    def list_currencies(self) -> list[SupportedCurrency]:
        """Return currently supported currencies."""
