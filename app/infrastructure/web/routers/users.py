"""Authenticated user profile management."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.entities import User, require_id
from app.infrastructure.security.jwt_handler import hash_password, verify_password
from app.infrastructure.web.dependencies import (
    get_current_user,
    get_transaction_repository,
    get_user_repository,
)
from app.interfaces.schemas.user import (
    ChangePasswordRequest,
    UserPreferencesUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.use_cases.interfaces.transaction_repository import TransactionRepositoryInterface
from app.use_cases.interfaces.user_repository import UserRepositoryInterface

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_my_profile(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
def update_my_profile(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    repo: UserRepositoryInterface = Depends(get_user_repository),
) -> UserResponse:
    if payload.email is not None:
        email = payload.email.strip().lower()
        duplicate = repo.get_by_email(email)
        if duplicate is not None and duplicate.id != current_user.id:
            raise HTTPException(status_code=409, detail="Email is already registered")
        current_user.email = email
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip() or None
    return UserResponse.model_validate(repo.update(current_user))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    current_user: User = Depends(get_current_user),
    repo: UserRepositoryInterface = Depends(get_user_repository),
) -> None:
    current_user.is_active = False
    repo.update(current_user)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    repo: UserRepositoryInterface = Depends(get_user_repository),
) -> None:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different")
    current_user.hashed_password = hash_password(payload.new_password)
    repo.update(current_user)


@router.patch("/me/preferences", response_model=UserResponse)
def update_my_preferences(
    payload: UserPreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    repo: UserRepositoryInterface = Depends(get_user_repository),
    tx_repo: TransactionRepositoryInterface = Depends(get_transaction_repository),
) -> UserResponse:
    """Update reporting preferences without mixing historical base currencies."""
    if (
        payload.base_currency is not None
        and payload.base_currency != current_user.base_currency
        and tx_repo.exists_for_user(require_id(current_user.id))
    ):
        raise HTTPException(
            status_code=409,
            detail="Base currency cannot be changed after the first transaction",
        )
    if payload.base_currency is not None:
        current_user.base_currency = payload.base_currency
    if payload.timezone is not None:
        current_user.timezone = payload.timezone
    return UserResponse.model_validate(repo.update(current_user))
