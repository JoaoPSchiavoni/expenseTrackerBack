"""Wallet and bank account management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.entities import User, Wallet, require_id
from app.infrastructure.web.dependencies import get_current_user, get_wallet_repository
from app.interfaces.schemas.wallet import (
    WalletCreateRequest,
    WalletResponse,
    WalletUpdateRequest,
)
from app.use_cases.interfaces.wallet_repository import WalletRepositoryInterface

router = APIRouter(prefix="/wallets", tags=["Wallets"])


@router.post(
    "/",
    response_model=WalletResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new wallet",
)
def create_wallet(
    payload: WalletCreateRequest,
    current_user: User = Depends(get_current_user),
    wallet_repo: WalletRepositoryInterface = Depends(get_wallet_repository),
) -> WalletResponse:
    """Creates a new wallet associated with the authenticated user."""
    new_wallet = Wallet(
        user_id=require_id(current_user.id),
        name=payload.name.strip(),
        currency=payload.currency.upper(),
        balance=payload.initial_balance,
    )
    saved = wallet_repo.create(new_wallet)
    return WalletResponse.model_validate(saved)


@router.get(
    "/",
    response_model=list[WalletResponse],
    status_code=status.HTTP_200_OK,
    summary="List user wallets",
)
def list_wallets(
    current_user: User = Depends(get_current_user),
    wallet_repo: WalletRepositoryInterface = Depends(get_wallet_repository),
) -> list[WalletResponse]:
    """Returns all wallets belonging to the logged-in user."""
    wallets = wallet_repo.list_by_user(require_id(current_user.id))
    return [WalletResponse.model_validate(w) for w in wallets]


@router.get(
    "/{id}",
    response_model=WalletResponse,
    status_code=status.HTTP_200_OK,
    summary="Get wallet detail and current balance",
)
def get_wallet_detail(
    id: int,
    current_user: User = Depends(get_current_user),
    wallet_repo: WalletRepositoryInterface = Depends(get_wallet_repository),
) -> WalletResponse:
    """Retrieves data and current balance of a specific wallet."""
    wallet = wallet_repo.get_by_id(id)
    if not wallet or wallet.user_id != current_user.id or not wallet.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet with ID {id} not found.",
        )
    return WalletResponse.model_validate(wallet)


@router.put(
    "/{id}",
    response_model=WalletResponse,
    status_code=status.HTTP_200_OK,
    summary="Update wallet data",
)
def update_wallet(
    id: int,
    payload: WalletUpdateRequest,
    current_user: User = Depends(get_current_user),
    wallet_repo: WalletRepositoryInterface = Depends(get_wallet_repository),
) -> WalletResponse:
    """Update wallet metadata while preserving its financial balance."""
    wallet = wallet_repo.get_by_id(id)
    if not wallet or wallet.user_id != current_user.id or not wallet.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet with ID {id} not found.",
        )
    if payload.name is not None:
        wallet.name = payload.name.strip()
    if payload.currency is not None:
        if payload.currency != wallet.currency and wallet_repo.has_transactions(id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Wallet currency cannot be changed after the first transaction",
            )
        wallet.currency = payload.currency.upper()
    return WalletResponse.model_validate(wallet_repo.update(wallet))


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive wallet",
)
def delete_wallet(
    id: int,
    current_user: User = Depends(get_current_user),
    wallet_repo: WalletRepositoryInterface = Depends(get_wallet_repository),
) -> None:
    """Archive a wallet without erasing its financial history."""
    wallet = wallet_repo.get_by_id(id)
    if not wallet or wallet.user_id != current_user.id or not wallet.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet with ID {id} not found.",
        )
    wallet.is_active = False
    wallet_repo.update(wallet)
