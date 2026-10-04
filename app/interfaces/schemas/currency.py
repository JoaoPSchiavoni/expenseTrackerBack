"""Currency conversion API schemas."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.interfaces.schemas.common import CurrencyCode


class CurrencyResponse(BaseModel):
    code: CurrencyCode
    name: str
    symbol: str | None = None


class ConversionQuoteResponse(BaseModel):
    base_currency: CurrencyCode
    quote_currency: CurrencyCode
    amount: Decimal
    converted_amount: Decimal
    rate: Decimal
    requested_date: date
    effective_date: date
    provider: str
