"""Supported currency and conversion quote endpoints."""

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.domain.entities import User
from app.infrastructure.exchange_rates.frankfurter import ExchangeRateProviderError
from app.infrastructure.web.dependencies import get_current_user, get_exchange_rate_service
from app.interfaces.schemas.currency import ConversionQuoteResponse, CurrencyResponse
from app.use_cases.exchange_rates import ExchangeRateService

router = APIRouter(prefix="/currencies", tags=["Currencies"])


@router.get("/", response_model=list[CurrencyResponse])
def list_currencies(
    current_user: User = Depends(get_current_user),
    service: ExchangeRateService = Depends(get_exchange_rate_service),
) -> list[CurrencyResponse]:
    del current_user
    try:
        return [
            CurrencyResponse(code=item.code, name=item.name, symbol=item.symbol)
            for item in service.list_currencies()
        ]
    except ExchangeRateProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/quote", response_model=ConversionQuoteResponse)
def get_conversion_quote(
    amount: str = Query(..., pattern=r"^\d+(\.\d{1,2})?$"),
    base_currency: str = Query(..., min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$"),
    quote_currency: str = Query(..., min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$"),
    on_date: str | None = Query(None, alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    current_user: User = Depends(get_current_user),
    service: ExchangeRateService = Depends(get_exchange_rate_service),
) -> ConversionQuoteResponse:
    del current_user
    try:
        requested_date = date.fromisoformat(on_date) if on_date else datetime.now(UTC).date()
        quote = service.quote(
            Decimal(amount), base_currency.upper(), quote_currency.upper(), requested_date
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExchangeRateProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ConversionQuoteResponse.model_validate(quote, from_attributes=True)
