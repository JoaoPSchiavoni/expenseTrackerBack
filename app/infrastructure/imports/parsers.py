"""In-memory CSV and OFX statement parsers with normalized output."""

import csv
import hashlib
import io
import re
import unicodedata
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from ofxparse import OfxParser  # type: ignore[import-untyped]

from app.domain.entities import (
    TransactionType,
    normalize_event_datetime,
    normalize_money,
)
from app.domain.imports import ImportFileType


class ImportParseError(ValueError):
    """Raised when a statement cannot be safely interpreted."""


class ParsedRow:
    def __init__(
        self,
        *,
        row_number: int,
        occurred_at: datetime | None = None,
        amount: Decimal | None = None,
        transaction_type: TransactionType | None = None,
        description: str | None = None,
        external_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self.row_number = row_number
        self.occurred_at = occurred_at
        self.amount = amount
        self.transaction_type = transaction_type
        self.description = description
        self.external_id = external_id
        self.error_message = error_message


class ParsedStatement:
    def __init__(self, rows: list[ParsedRow], currency: str | None = None) -> None:
        self.rows = rows
        self.currency = currency.upper() if currency else None


_ALIASES: dict[str, set[str]] = {
    "date": {"date", "data", "transactiondate", "datatransacao", "posteddate"},
    "description": {
        "description",
        "descricao",
        "memo",
        "history",
        "historico",
        "payee",
        "estabelecimento",
    },
    "amount": {"amount", "valor", "value", "transactionamount"},
    "debit": {"debit", "debito", "saida", "withdrawal"},
    "credit": {"credit", "credito", "entrada", "deposit"},
    "type": {"type", "tipo", "transactiontype", "natureza"},
    "id": {"id", "fitid", "transactionid", "identificador", "documento"},
}


def _normalize_header(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_value.strip().lower())


def _parse_decimal(raw: str) -> Decimal:
    value = raw.strip().replace("R$", "").replace("$", "").replace(" ", "")
    negative_parentheses = value.startswith("(") and value.endswith(")")
    if negative_parentheses:
        value = value[1:-1]
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(".", "").replace(",", ".")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ImportParseError(f"Invalid monetary value: {raw}") from exc
    return -parsed if negative_parentheses else parsed


def _parse_date(raw: str, timezone_name: str, date_format: str | None) -> datetime:
    value = raw.strip()
    if date_format:
        try:
            return normalize_event_datetime(datetime.strptime(value, date_format), timezone_name)
        except ValueError as exc:
            raise ImportParseError(f"Date does not match {date_format}: {raw}") from exc
    try:
        return normalize_event_datetime(datetime.fromisoformat(value), timezone_name)
    except ValueError:
        pass
    for candidate in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return normalize_event_datetime(datetime.strptime(value, candidate), timezone_name)
        except ValueError:
            continue
    raise ImportParseError(f"Invalid date: {raw}")


def _parse_type(raw: str) -> TransactionType:
    normalized = _normalize_header(raw)
    if normalized in {"income", "receita", "credit", "credito", "entrada", "c"}:
        return TransactionType.INCOME
    if normalized in {"expense", "despesa", "debit", "debito", "saida", "d"}:
        return TransactionType.EXPENSE
    raise ImportParseError(f"Invalid transaction type: {raw}")


def _make_external_ids(rows: list[ParsedRow], prefix: str) -> None:
    occurrences: defaultdict[str, int] = defaultdict(int)
    for row in rows:
        if row.error_message or row.occurred_at is None or row.amount is None:
            continue
        if row.external_id:
            row.external_id = f"{prefix}:{row.external_id.strip()}"[:255]
            continue
        signature = "|".join(
            (
                row.occurred_at.isoformat(),
                str(row.amount),
                row.transaction_type.value if row.transaction_type else "",
                " ".join((row.description or "").lower().split()),
            )
        )
        occurrences[signature] += 1
        digest = hashlib.sha256(f"{signature}|{occurrences[signature]}".encode()).hexdigest()
        row.external_id = f"{prefix}:{digest}"


class StatementParser:
    """Parse supported statements without persisting uploaded source files."""

    def parse(
        self,
        content: bytes,
        file_type: ImportFileType,
        timezone_name: str,
        options: dict[str, str] | None = None,
    ) -> ParsedStatement:
        if file_type == ImportFileType.CSV:
            return self._parse_csv(content, timezone_name, options or {})
        return self._parse_ofx(content, timezone_name)

    @staticmethod
    def _decode_csv(content: bytes) -> str:
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ImportParseError("CSV encoding is not supported")

    def _parse_csv(
        self, content: bytes, timezone_name: str, options: dict[str, str]
    ) -> ParsedStatement:
        text = self._decode_csv(content)
        delimiter = options.get("delimiter")
        if delimiter is not None and delimiter not in {",", ";", "\t", "|"}:
            raise ImportParseError("CSV delimiter must be comma, semicolon, tab, or pipe")
        if delimiter is None:
            try:
                delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
            except csv.Error:
                delimiter = ";" if ";" in text.partition("\n")[0] else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if not reader.fieldnames:
            raise ImportParseError("CSV header is missing")
        columns = self._resolve_columns(reader.fieldnames, options)
        date_format = options.get("date_format")
        rows: list[ParsedRow] = []
        for row_number, raw_row in enumerate(reader, start=2):
            if not any(str(value or "").strip() for value in raw_row.values()):
                continue
            try:
                rows.append(
                    self._parse_csv_row(row_number, raw_row, columns, timezone_name, date_format)
                )
            except ImportParseError as exc:
                rows.append(ParsedRow(row_number=row_number, error_message=str(exc)))
        if not rows:
            raise ImportParseError("CSV contains no transaction rows")
        _make_external_ids(rows, "csv")
        return ParsedStatement(rows)

    @staticmethod
    def _resolve_columns(fieldnames: Sequence[str], options: dict[str, str]) -> dict[str, str]:
        normalized = {_normalize_header(name): name for name in fieldnames}
        columns: dict[str, str] = {}
        for field, aliases in _ALIASES.items():
            configured = options.get(field)
            if configured:
                if configured not in fieldnames:
                    raise ImportParseError(f"CSV column not found: {configured}")
                columns[field] = configured
                continue
            for alias in aliases:
                if alias in normalized:
                    columns[field] = normalized[alias]
                    break
        if "date" not in columns:
            raise ImportParseError(
                f"Could not detect the date column. Available columns: {', '.join(fieldnames)}"
            )
        if "amount" not in columns and not ({"debit", "credit"} & columns.keys()):
            raise ImportParseError(
                f"Could not detect amount/debit/credit columns. Available columns: {', '.join(fieldnames)}"
            )
        return columns

    @staticmethod
    def _parse_csv_row(
        row_number: int,
        raw: dict[str, Any],
        columns: dict[str, str],
        timezone_name: str,
        date_format: str | None,
    ) -> ParsedRow:
        occurred_at = _parse_date(str(raw.get(columns["date"], "")), timezone_name, date_format)
        transaction_type: TransactionType
        signed_amount: Decimal
        if "amount" in columns:
            signed_amount = _parse_decimal(str(raw.get(columns["amount"], "")))
            if "type" in columns and str(raw.get(columns["type"], "")).strip():
                transaction_type = _parse_type(str(raw[columns["type"]]))
            else:
                transaction_type = (
                    TransactionType.EXPENSE if signed_amount < 0 else TransactionType.INCOME
                )
        else:
            debit = (
                _parse_decimal(str(raw.get(columns["debit"], "")))
                if "debit" in columns and str(raw.get(columns["debit"], "")).strip()
                else Decimal("0")
            )
            credit = (
                _parse_decimal(str(raw.get(columns["credit"], "")))
                if "credit" in columns and str(raw.get(columns["credit"], "")).strip()
                else Decimal("0")
            )
            if bool(debit) == bool(credit):
                raise ImportParseError("Exactly one of debit or credit must contain a value")
            signed_amount = debit or credit
            transaction_type = TransactionType.EXPENSE if debit else TransactionType.INCOME
        amount = normalize_money(abs(signed_amount))
        if amount <= 0:
            raise ImportParseError("Transaction amount must be greater than zero")
        description = (
            str(raw.get(columns["description"], "")).strip()[:255]
            if "description" in columns
            else "Imported transaction"
        )
        external_id = (str(raw.get(columns["id"], "")).strip() if "id" in columns else None) or None
        return ParsedRow(
            row_number=row_number,
            occurred_at=occurred_at,
            amount=amount,
            transaction_type=transaction_type,
            description=description or "Imported transaction",
            external_id=external_id,
        )

    @staticmethod
    def _parse_ofx(content: bytes, timezone_name: str) -> ParsedStatement:
        try:
            parsed = OfxParser.parse(io.BytesIO(content))
        except Exception as exc:
            raise ImportParseError("OFX file is malformed or unsupported") from exc
        accounts = list(getattr(parsed, "accounts", []))
        if len(accounts) != 1:
            raise ImportParseError("OFX file must contain exactly one bank or credit account")
        statement = getattr(accounts[0], "statement", None)
        if statement is None:
            raise ImportParseError("OFX statement data is missing")
        rows: list[ParsedRow] = []
        for row_number, transaction in enumerate(getattr(statement, "transactions", []), start=1):
            try:
                signed_amount = Decimal(str(transaction.amount))
                amount = normalize_money(abs(signed_amount))
                if amount <= 0:
                    raise ImportParseError("Transaction amount must be greater than zero")
                description_parts = [
                    str(getattr(transaction, field, "") or "").strip()
                    for field in ("payee", "memo")
                ]
                description = " - ".join(dict.fromkeys(part for part in description_parts if part))
                rows.append(
                    ParsedRow(
                        row_number=row_number,
                        occurred_at=normalize_event_datetime(transaction.date, timezone_name),
                        amount=amount,
                        transaction_type=(
                            TransactionType.EXPENSE if signed_amount < 0 else TransactionType.INCOME
                        ),
                        description=(description or "Imported OFX transaction")[:255],
                        external_id=str(getattr(transaction, "id", "") or "").strip() or None,
                    )
                )
            except (AttributeError, InvalidOperation, TypeError, ValueError) as exc:
                rows.append(ParsedRow(row_number=row_number, error_message=str(exc)))
        if not rows:
            raise ImportParseError("OFX contains no transactions")
        _make_external_ids(rows, "ofx")
        currency = str(getattr(statement, "currency", "") or "") or None
        return ParsedStatement(rows, currency)
