"""Frankfurter v2 exchange-rate provider adapter."""

from datetime import date
from decimal import Decimal, InvalidOperation

import httpx

from app.domain.entities import normalize_rate
from app.use_cases.interfaces.exchange_rate_provider import (
    ExchangeRateProviderInterface,
    ProviderRate,
    SupportedCurrency,
)


class ExchangeRateProviderError(RuntimeError):
    """Raised when the external provider cannot supply a valid response."""


class UnsupportedCurrencyError(ValueError):
    """Raised when a provider rejects a currency code or pair."""


class FrankfurterExchangeRateProvider(ExchangeRateProviderInterface):
    name = "frankfurter"

    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _get(self, path: str, *, params: dict[str, str] | None = None) -> object:
        try:
            response = httpx.get(
                f"{self.base_url}{path}", params=params, timeout=self.timeout_seconds
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {400, 404, 422}:
                raise UnsupportedCurrencyError("Unsupported currency or rate date") from exc
            raise ExchangeRateProviderError("Exchange-rate provider is unavailable") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ExchangeRateProviderError("Exchange-rate provider is unavailable") from exc

    def fetch_rate(self, base_currency: str, quote_currency: str, on_date: date) -> ProviderRate:
        payload = self._get(
            f"/rate/{base_currency}/{quote_currency}", params={"date": on_date.isoformat()}
        )
        if not isinstance(payload, dict):
            raise ExchangeRateProviderError("Exchange-rate provider returned an invalid payload")
        try:
            effective_date = date.fromisoformat(str(payload["date"]))
            rate = normalize_rate(Decimal(str(payload["rate"])))
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ExchangeRateProviderError(
                "Exchange-rate provider returned an invalid rate"
            ) from exc
        if rate <= 0:
            raise ExchangeRateProviderError("Exchange-rate provider returned an invalid rate")
        return ProviderRate(
            base_currency=base_currency,
            quote_currency=quote_currency,
            requested_date=on_date,
            effective_date=effective_date,
            rate=rate,
            provider=self.name,
        )

    def list_currencies(self) -> list[SupportedCurrency]:
        payload = self._get("/currencies")
        if not isinstance(payload, list):
            raise ExchangeRateProviderError("Exchange-rate provider returned an invalid payload")
        currencies: list[SupportedCurrency] = []
        try:
            for item in payload:
                if not isinstance(item, dict):
                    raise TypeError
                currencies.append(
                    SupportedCurrency(
                        code=str(item["iso_code"]),
                        name=str(item["name"]),
                        symbol=str(item["symbol"]) if item.get("symbol") else None,
                    )
                )
        except (KeyError, TypeError) as exc:
            raise ExchangeRateProviderError(
                "Exchange-rate provider returned invalid currency metadata"
            ) from exc
        return sorted(currencies, key=lambda item: item.code)
