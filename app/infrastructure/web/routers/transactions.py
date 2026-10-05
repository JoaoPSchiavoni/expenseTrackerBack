"""Financial transaction endpoints with ownership and balance guarantees."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.domain.entities import User, require_id
from app.domain.exceptions import (
    UnauthorizedWalletAccessError,
    WalletNotFoundError,
)
from app.infrastructure.web.dependencies import (
    get_category_repository,
    get_create_transaction_use_case,
    get_current_user,
    get_manage_transaction_use_case,
    get_transaction_repository,
    get_wallet_repository,
)
from app.interfaces.schemas.transaction import (
    TransactionBulkCreateRequest,
    TransactionBulkCreateResponse,
    TransactionCreateRequest,
    TransactionResponse,
    TransactionUpdateRequest,
    TransactionWithWalletResponse,
)
from app.use_cases.interfaces.category_repository import CategoryRepositoryInterface
from app.use_cases.interfaces.transaction_repository import TransactionRepositoryInterface
from app.use_cases.interfaces.wallet_repository import WalletRepositoryInterface
from app.use_cases.transactions.create_transaction import CreateTransactionUseCase
from app.use_cases.transactions.manage_transaction import ManageTransactionUseCase

router = APIRouter(prefix="/transactions", tags=["Transactions"])


def _validate_category(
    category_id: int | None,
    user_id: int,
    category_repo: CategoryRepositoryInterface,
) -> None:
    if category_id is not None and category_repo.get_by_id_for_user(category_id, user_id) is None:
        raise HTTPException(status_code=404, detail="Category not found")


@router.post(
    "/",
    response_model=TransactionWithWalletResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(
    payload: TransactionCreateRequest,
    current_user: User = Depends(get_current_user),
    use_case: CreateTransactionUseCase = Depends(get_create_transaction_use_case),
    category_repo: CategoryRepositoryInterface = Depends(get_category_repository),
) -> TransactionWithWalletResponse:
    user_id = require_id(current_user.id)
    _validate_category(payload.category_id, user_id, category_repo)
    try:
        transaction, wallet = use_case.execute(
            user_id=user_id,
            wallet_id=payload.wallet_id,
            amount=payload.amount,
            transaction_type=payload.transaction_type,
            category_id=payload.category_id,
            description=payload.description,
            occurred_at=payload.occurred_at,
            base_currency=current_user.base_currency,
            timezone_name=current_user.timezone,
        )
    except WalletNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except UnauthorizedWalletAccessError as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc
    return TransactionWithWalletResponse(
        transaction=TransactionResponse.model_validate(transaction),
        updated_wallet_balance=wallet.balance,
    )


@router.get("/", response_model=list[TransactionResponse])
def list_transactions(
    wallet_id: int = Query(..., gt=0),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    wallet_repo: WalletRepositoryInterface = Depends(get_wallet_repository),
    tx_repo: TransactionRepositoryInterface = Depends(get_transaction_repository),
) -> list[TransactionResponse]:
    wallet = wallet_repo.get_by_id(wallet_id)
    if wallet is None or wallet.user_id != current_user.id or not wallet.is_active:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return [
        TransactionResponse.model_validate(item)
        for item in tx_repo.list_by_wallet(wallet_id, limit, offset)
    ]


@router.post(
    "/bulk",
    response_model=TransactionBulkCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def bulk_create_transactions(
    payload: TransactionBulkCreateRequest,
    current_user: User = Depends(get_current_user),
    use_case: CreateTransactionUseCase = Depends(get_create_transaction_use_case),
    category_repo: CategoryRepositoryInterface = Depends(get_category_repository),
) -> TransactionBulkCreateResponse:
    user_id = require_id(current_user.id)
    created = []
    for item in payload.transactions:
        _validate_category(item.category_id, user_id, category_repo)
        transaction, _ = use_case.execute(
            user_id=user_id,
            wallet_id=item.wallet_id,
            amount=item.amount,
            transaction_type=item.transaction_type,
            category_id=item.category_id,
            description=item.description,
            occurred_at=item.occurred_at,
            base_currency=current_user.base_currency,
            timezone_name=current_user.timezone,
        )
        created.append(TransactionResponse.model_validate(transaction))
    return TransactionBulkCreateResponse(transactions=created, processed=len(created))


@router.get("/{id}", response_model=TransactionResponse)
def get_transaction_detail(
    id: int,
    current_user: User = Depends(get_current_user),
    tx_repo: TransactionRepositoryInterface = Depends(get_transaction_repository),
) -> TransactionResponse:
    transaction = tx_repo.get_by_id_for_user(id, require_id(current_user.id))
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionResponse.model_validate(transaction)


@router.put("/{id}", response_model=TransactionWithWalletResponse)
def update_transaction(
    id: int,
    payload: TransactionUpdateRequest,
    current_user: User = Depends(get_current_user),
    use_case: ManageTransactionUseCase = Depends(get_manage_transaction_use_case),
    category_repo: CategoryRepositoryInterface = Depends(get_category_repository),
) -> TransactionWithWalletResponse:
    user_id = require_id(current_user.id)
    category_was_set = "category_id" in payload.model_fields_set
    if category_was_set:
        _validate_category(payload.category_id, user_id, category_repo)
    try:
        transaction, wallet = use_case.update(
            transaction_id=id,
            user_id=user_id,
            amount=payload.amount,
            transaction_type=payload.transaction_type,
            category_id=payload.category_id,
            description=payload.description,
            occurred_at=payload.occurred_at,
            category_was_set=category_was_set,
            description_was_set="description" in payload.model_fields_set,
            occurred_at_was_set="occurred_at" in payload.model_fields_set,
            timezone_name=current_user.timezone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TransactionWithWalletResponse(
        transaction=TransactionResponse.model_validate(transaction),
        updated_wallet_balance=wallet.balance,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    id: int,
    current_user: User = Depends(get_current_user),
    use_case: ManageTransactionUseCase = Depends(get_manage_transaction_use_case),
) -> None:
    try:
        use_case.delete(
            transaction_id=id,
            user_id=require_id(current_user.id),
            timezone_name=current_user.timezone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
