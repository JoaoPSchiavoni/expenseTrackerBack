from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.domain.entities import User, require_id
from app.infrastructure.web.dependencies import (
    get_category_repository,
    get_current_user,
    get_manage_recurring_transactions_use_case,
)
from app.interfaces.schemas.recurring_transaction import (
    RecurringProcessResponse,
    RecurringTransactionCreateRequest,
    RecurringTransactionResponse,
    RecurringTransactionUpdateRequest,
)
from app.use_cases.interfaces.category_repository import CategoryRepositoryInterface
from app.use_cases.recurring_transactions import ManageRecurringTransactionsUseCase

router = APIRouter(prefix="/recurring-transactions", tags=["Recurring Transactions"])


def _validate_category(
    category_id: int | None,
    user_id: int,
    category_repo: CategoryRepositoryInterface,
) -> None:
    if category_id is not None and category_repo.get_by_id_for_user(category_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Category not found")


@router.post(
    "/",
    response_model=RecurringTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_recurring_transaction(
    payload: RecurringTransactionCreateRequest,
    current_user: User = Depends(get_current_user),
    use_case: ManageRecurringTransactionsUseCase = Depends(
        get_manage_recurring_transactions_use_case
    ),
    category_repo: CategoryRepositoryInterface = Depends(get_category_repository),
) -> RecurringTransactionResponse:
    user_id = require_id(current_user.id)
    _validate_category(payload.category_id, user_id, category_repo)
    recurring = use_case.create(
        user_id=user_id,
        wallet_id=payload.wallet_id,
        category_id=payload.category_id,
        amount=payload.amount,
        transaction_type=payload.transaction_type,
        description=payload.description,
        frequency=payload.frequency,
        interval_count=payload.interval_count,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    return RecurringTransactionResponse.model_validate(recurring)


@router.get("/", response_model=list[RecurringTransactionResponse])
def list_recurring_transactions(
    current_user: User = Depends(get_current_user),
    use_case: ManageRecurringTransactionsUseCase = Depends(
        get_manage_recurring_transactions_use_case
    ),
) -> list[RecurringTransactionResponse]:
    return [
        RecurringTransactionResponse.model_validate(item)
        for item in use_case.list_for_user(require_id(current_user.id))
    ]


@router.post("/process-due", response_model=RecurringProcessResponse)
def process_due_recurring_transactions(
    through_date: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    use_case: ManageRecurringTransactionsUseCase = Depends(
        get_manage_recurring_transactions_use_case
    ),
) -> RecurringProcessResponse:
    selected_date = through_date or datetime.now(UTC).astimezone(
        ZoneInfo(current_user.timezone)
    ).date()
    transaction_ids = use_case.process_due(
        user_id=require_id(current_user.id),
        through_date=selected_date,
        base_currency=current_user.base_currency,
        timezone_name=current_user.timezone,
    )
    return RecurringProcessResponse(
        generated=len(transaction_ids),
        transaction_ids=transaction_ids,
        processed_through=selected_date,
    )


@router.get("/{id}", response_model=RecurringTransactionResponse)
def get_recurring_transaction(
    id: int,
    current_user: User = Depends(get_current_user),
    use_case: ManageRecurringTransactionsUseCase = Depends(
        get_manage_recurring_transactions_use_case
    ),
) -> RecurringTransactionResponse:
    try:
        recurring = use_case.get(id, require_id(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RecurringTransactionResponse.model_validate(recurring)


@router.put("/{id}", response_model=RecurringTransactionResponse)
def update_recurring_transaction(
    id: int,
    payload: RecurringTransactionUpdateRequest,
    current_user: User = Depends(get_current_user),
    use_case: ManageRecurringTransactionsUseCase = Depends(
        get_manage_recurring_transactions_use_case
    ),
    category_repo: CategoryRepositoryInterface = Depends(get_category_repository),
) -> RecurringTransactionResponse:
    user_id = require_id(current_user.id)
    changes = payload.model_dump(exclude_unset=True)
    if "category_id" in changes:
        _validate_category(payload.category_id, user_id, category_repo)
    try:
        recurring = use_case.update(id, user_id, changes)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return RecurringTransactionResponse.model_validate(recurring)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring_transaction(
    id: int,
    current_user: User = Depends(get_current_user),
    use_case: ManageRecurringTransactionsUseCase = Depends(
        get_manage_recurring_transactions_use_case
    ),
) -> None:
    try:
        use_case.delete(id, require_id(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
