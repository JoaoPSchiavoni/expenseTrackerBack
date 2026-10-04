"""Financial report endpoints backed by aggregate database queries."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query

from app.domain.entities import User, require_id
from app.infrastructure.web.dependencies import get_current_user, get_report_repository
from app.interfaces.repositories.sql_report_repository import SqlReportRepository
from app.interfaces.schemas.report import (
    CategorySummaryItem,
    CategorySummaryResponse,
    MonthlyReportResponse,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


def _month_range(value: str, timezone_name: str = "UTC") -> tuple[datetime, datetime]:
    try:
        year_text, month_text = value.split("-", maxsplit=1)
        year, month = int(year_text), int(month_text)
        timezone = ZoneInfo(timezone_name)
        local_start = datetime(year, month, 1, tzinfo=timezone)
        if month == 12:
            local_end = datetime(year + 1, 1, 1, tzinfo=timezone)
        else:
            local_end = datetime(year, month + 1, 1, tzinfo=timezone)
        return local_start.astimezone(UTC), local_end.astimezone(UTC)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Month must use YYYY-MM format") from exc


@router.get("/monthly", response_model=MonthlyReportResponse)
def get_monthly_report(
    month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    current_user: User = Depends(get_current_user),
    repo: SqlReportRepository = Depends(get_report_repository),
) -> MonthlyReportResponse:
    start, end = _month_range(month, current_user.timezone)
    income, expense = repo.monthly_totals(require_id(current_user.id), start, end)
    return MonthlyReportResponse(
        month=month,
        currency=current_user.base_currency,
        total_income=income,
        total_expense=expense,
        net_savings=income - expense,
    )


@router.get("/category-summary", response_model=CategorySummaryResponse)
def get_category_summary(
    period: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    current_user: User = Depends(get_current_user),
    repo: SqlReportRepository = Depends(get_report_repository),
) -> CategorySummaryResponse:
    start, end = _month_range(period, current_user.timezone)
    items = [
        CategorySummaryItem(category_id=category_id, category_name=name, total_spent=total)
        for category_id, name, total in repo.category_expenses(
            require_id(current_user.id), start, end
        )
    ]
    return CategorySummaryResponse(period=period, currency=current_user.base_currency, items=items)
