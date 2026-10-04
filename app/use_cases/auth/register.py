"""
Use Case: User Registration.

Why: Encapsulates the business rule for registering a new user,
verifying email uniqueness and applying secure password hashing
before delegating persistence to the repository.
"""

import logging
from collections.abc import Callable

from app.domain.entities import User
from app.domain.exceptions import UserAlreadyExistsError
from app.use_cases.interfaces.user_repository import UserRepositoryInterface

logger = logging.getLogger(__name__)


class RegisterUserUseCase:
    """Use case responsible for onboarding new users into the system.

    Why: Follows Single Responsibility Principle (SRP), isolating user creation
    and validation rules from HTTP transport logic or database specifics.
    """

    def __init__(
        self, user_repository: UserRepositoryInterface, hash_password_fn: Callable[[str], str]
    ) -> None:
        """Initializes the use case with injected dependencies.

        Why: Dependency Inversion (DIP) enables effortless unit testing with mock repositories.

        Args:
            user_repository: Concrete user repository implementation.
            hash_password_fn: Callable for securely hashing plain passwords.
        """
        self.user_repository = user_repository
        self.hash_password = hash_password_fn

    def execute(self, email: str, raw_password: str, full_name: str | None = None) -> User:
        """Executes user registration.

        Args:
            email: Unique email address.
            raw_password: Plain text password provided by the client.
            full_name: Optional full name of the user.

        Returns:
            Created and persisted User entity.

        Raises:
            UserAlreadyExistsError: If the normalized email is already registered.
        """
        # Why: Normalizes email to lowercase to prevent collisions caused by case differences
        clean_email = email.strip().lower()

        # Why: Prior check ensures business integrity before hashing or persisting
        existing_user = self.user_repository.get_by_email(clean_email)
        if existing_user is not None:
            logger.warning("Attempted registration with existing email: %s", clean_email)
            raise UserAlreadyExistsError(clean_email)

        # Why: Never store plain text passwords under any circumstances
        hashed_pw = self.hash_password(raw_password)

        new_user = User(
            email=clean_email, hashed_password=hashed_pw, full_name=full_name, is_active=True
        )

        saved_user = self.user_repository.create(new_user)
        logger.info("User registered successfully with id %s", saved_user.id)
        return saved_user
