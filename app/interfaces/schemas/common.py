"""Reusable validated scalar types shared by HTTP schemas."""

from typing import Annotated

from pydantic import BeforeValidator, StringConstraints


def _normalize_currency(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Currency must be a three-letter ISO code")
    return value.strip().upper()


CurrencyCode = Annotated[
    str,
    BeforeValidator(_normalize_currency),
    StringConstraints(pattern=r"^[A-Z]{3}$"),
]
