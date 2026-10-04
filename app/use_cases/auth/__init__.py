"""Auth use cases initialization."""

from app.use_cases.auth.login import AuthenticateUserUseCase
from app.use_cases.auth.register import RegisterUserUseCase

__all__ = ["AuthenticateUserUseCase", "RegisterUserUseCase"]
