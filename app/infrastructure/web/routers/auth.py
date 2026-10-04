"""
API Authentication Router.

Endpoints:
1. POST /api/auth/register (Creates a new user in the system)
2. POST /api/auth/login (Generates and returns JWT token for valid credentials)
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.domain.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from app.infrastructure.web.dependencies import (
    get_authenticate_user_use_case,
    get_register_user_use_case,
)
from app.interfaces.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.interfaces.schemas.user import UserResponse
from app.use_cases.auth.login import AuthenticateUserUseCase
from app.use_cases.auth.register import RegisterUserUseCase

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register_user(
    payload: RegisterRequest,
    use_case: RegisterUserUseCase = Depends(get_register_user_use_case),
) -> UserResponse:
    """Registers a new user by delegating to the corresponding use case.

    Why: Controller acts strictly as an HTTP adapter; it does not contain
    business validation or direct database queries.
    """
    try:
        user = use_case.execute(
            email=payload.email,
            raw_password=payload.password,
            full_name=payload.full_name,
        )
        return UserResponse.model_validate(user)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and obtain JWT token",
)
def login_user(
    payload: LoginRequest,
    use_case: AuthenticateUserUseCase = Depends(get_authenticate_user_use_case),
) -> TokenResponse:
    """Validates user credentials and generates a signed JWT token.

    Why: Catches domain InvalidCredentialsError and maps to HTTP 401
    without exposing internal database structure.
    """
    try:
        token, _ = use_case.execute(
            email=payload.email,
            raw_password=payload.password,
        )
        return TokenResponse(access_token=token, token_type="bearer")
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
