from datetime import date
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.infrastructure.exchange_rates.frankfurter import (
    ExchangeRateProviderError,
    FrankfurterExchangeRateProvider,
    UnsupportedCurrencyError,
)
from app.infrastructure.web.dependencies import get_exchange_rate_service
from app.interfaces.repositories.sql_exchange_rate_repository import SqlExchangeRateRepository
from app.main import app
from app.use_cases.exchange_rates import ExchangeRateService
from app.use_cases.interfaces.exchange_rate_provider import (
    ExchangeRateProviderInterface,
    ProviderRate,
    SupportedCurrency,
)


class StubProvider(ExchangeRateProviderInterface):
    name = "stub"

    def __init__(self) -> None:
        self.fetch_count = 0

    def fetch_rate(self, base_currency: str, quote_currency: str, on_date: date) -> ProviderRate:
        self.fetch_count += 1
        return ProviderRate(
            base_currency=base_currency,
            quote_currency=quote_currency,
            requested_date=on_date,
            effective_date=on_date,
            rate=Decimal("5.2500000000"),
            provider=self.name,
        )

    def list_currencies(self) -> list[SupportedCurrency]:
        return [
            SupportedCurrency(code="BRL", name="Brazilian Real", symbol="R$"),
            SupportedCurrency(code="USD", name="United States Dollar", symbol="$"),
        ]


def _http_response(status_code: int, payload: object) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("GET", "https://rates.example/test"),
    )


def test_service_fetches_persists_and_reuses_rate(db_session: Session) -> None:
    provider = StubProvider()
    service = ExchangeRateService(SqlExchangeRateRepository(db_session), provider)

    first = service.quote(Decimal("10.00"), "USD", "BRL", date(2026, 9, 30))
    second = service.quote(Decimal("2.00"), "USD", "BRL", date(2026, 9, 30))

    assert first.converted_amount == Decimal("52.50")
    assert second.converted_amount == Decimal("10.50")
    assert provider.fetch_count == 1


def test_service_converts_signed_balances(db_session: Session) -> None:
    provider = StubProvider()
    service = ExchangeRateService(SqlExchangeRateRepository(db_session), provider)

    quote = service.quote(Decimal("-10.00"), "USD", "BRL", date(2026, 9, 30))

    assert quote.converted_amount == Decimal("-52.50")


def test_currency_list_endpoint_uses_provider_metadata(
    client: TestClient, auth_headers: dict, db_session: Session
) -> None:
    service = ExchangeRateService(SqlExchangeRateRepository(db_session), StubProvider())
    app.dependency_overrides[get_exchange_rate_service] = lambda: service
    try:
        response = client.get("/api/v1/currencies/", headers=auth_headers)
    finally:
        app.dependency_overrides.pop(get_exchange_rate_service, None)

    assert response.status_code == 200
    assert response.json()[0] == {
        "code": "BRL",
        "name": "Brazilian Real",
        "symbol": "R$",
    }


def test_frankfurter_adapter_parses_rate_and_currency_list(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [
            _http_response(
                200,
                {"date": "2026-09-30", "base": "USD", "quote": "BRL", "rate": 5.2027},
            ),
            _http_response(
                200,
                [
                    {"iso_code": "USD", "name": "United States Dollar", "symbol": "$"},
                    {"iso_code": "BRL", "name": "Brazilian Real", "symbol": "R$"},
                ],
            ),
        ]
    )
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: next(responses))
    provider = FrankfurterExchangeRateProvider("https://rates.example/v2")

    rate = provider.fetch_rate("USD", "BRL", date(2026, 9, 30))
    currencies = provider.list_currencies()

    assert rate.rate == Decimal("5.2027000000")
    assert rate.effective_date == date(2026, 9, 30)
    assert [item.code for item in currencies] == ["BRL", "USD"]


@pytest.mark.parametrize(
    ("response", "exception_type"),
    [
        (_http_response(422, {"message": "invalid currency"}), UnsupportedCurrencyError),
        (_http_response(500, {"message": "failure"}), ExchangeRateProviderError),
    ],
)
def test_frankfurter_adapter_maps_http_failures(
    monkeypatch: pytest.MonkeyPatch,
    response: httpx.Response,
    exception_type: type[Exception],
) -> None:
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: response)
    provider = FrankfurterExchangeRateProvider("https://rates.example/v2")

    with pytest.raises(exception_type):
        provider.fetch_rate("XXX", "BRL", date(2026, 9, 30))


def test_frankfurter_adapter_rejects_invalid_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: _http_response(200, {"rate": -1}))
    provider = FrankfurterExchangeRateProvider("https://rates.example/v2")

    with pytest.raises(ExchangeRateProviderError):
        provider.fetch_rate("USD", "BRL", date(2026, 9, 30))


def test_frankfurter_adapter_retries_transient_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    responses: list[httpx.Response | Exception] = [
        httpx.ConnectTimeout("temporary timeout"),
        _http_response(
            200,
            {"date": "2026-09-30", "base": "USD", "quote": "BRL", "rate": 5.2},
        ),
    ]

    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(httpx, "get", fake_get)
    provider = FrankfurterExchangeRateProvider("https://rates.example/v2")

    rate = provider.fetch_rate("USD", "BRL", date(2026, 9, 30))

    assert rate.rate == Decimal("5.2000000000")
    assert responses == []
