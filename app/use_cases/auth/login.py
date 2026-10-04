"""
Use Case: User Authentication (Login).

Why: Encapsulates credential verification rules and JWT token generation,
guaranteeing security logic does not leak into HTTP controllers.
"""

import logging
from collections.abc import Callable

from app.domain.entities import User, require_id
from app.domain.exceptions import InvalidCredentialsError
from app.use_cases.interfaces.user_repository import UserRepositoryInterface

logger = logging.getLogger(__name__)


class AuthenticateUserUseCase:
    """Use case responsible for validating credentials and issuing access tokens.

    Why: Follows SRP by isolating the user credential verification flow.
    """

    def __init__(
        self,
        user_repository: UserRepositoryInterface,
        verify_password_fn: Callable[[str, str], bool],
        create_token_fn: Callable[[int, str], str],
    ) -> None:
        """Initializes the use case with its dependencies.

        Args:
            user_repository: Repository to lookup user by email.
            verify_password_fn: Function that compares plain text against secure hash.
            create_token_fn: Function that encodes the JWT token string.
        """
        self.user_repository = user_repository
        self.verify_password = verify_password_fn
        self.create_token = create_token_fn

    def execute(self, email: str, raw_password: str) -> tuple[str, User]:
        """Validates credentials and returns generated token with user entity.

        Args:
            email: User email to authenticate.
            raw_password: Plain text password.

        Returns:
            Tuple containing (access_token, user_entity).

        Raises:
            InvalidCredentialsError: If the user does not exist or password mismatch occurs.
        """
        clean_email = email.strip().lower()
        user = self.user_repository.get_by_email(clean_email)

        # Why: Generic error prevents user enumeration attacks
        if user is None or not user.is_active:
            logger.warning("Authentication failed: user not found for %s", clean_email)
            raise InvalidCredentialsError()

        is_valid = self.verify_password(raw_password, user.hashed_password)
        if not is_valid:
            logger.warning("Authentication failed: invalid password for user id %s", user.id)
            raise InvalidCredentialsError()

        # Why: Issues JWT token encoding user identity claims
        token = self.create_token(require_id(user.id), user.email)
        logger.info("User authenticated successfully with id %s", user.id)

        return token, user
