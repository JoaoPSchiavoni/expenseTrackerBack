"""
Abstract Interface for User Repository.

Why: Adheres to the Dependency Inversion Principle (DIP) of SOLID.
Use Cases depend on this abstraction rather than a concrete database or SQLAlchemy.
"""

from abc import ABC, abstractmethod

from app.domain.entities import User


class UserRepositoryInterface(ABC):
    """Contract for user persistence and retrieval adapters."""

    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None:
        """Retrieves a user by their unique primary key identifier.

        Args:
            user_id: Unique integer identifier.

        Returns:
            User entity instance or None if not found.
        """
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        """Retrieves a user by their email address.

        Args:
            email: Email address to search for.

        Returns:
            User entity instance or None if not found.
        """
        pass

    @abstractmethod
    def create(self, user: User) -> User:
        """Persists a new user in the storage mechanism.

        Args:
            user: User domain entity to create.

        Returns:
            Persisted User entity with assigned ID.
        """
        pass

    @abstractmethod
    def update(self, user: User) -> User:
        """Persist changes to an existing user."""
        pass
