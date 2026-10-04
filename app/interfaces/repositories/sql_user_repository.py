"""
SQLAlchemy Implementation of User Repository.

Why: Acts as an Interface Adapter in Clean Architecture,
mapping UserModel database records to pure User domain entities and vice-versa.
"""

from sqlalchemy.orm import Session

from app.domain.entities import User
from app.infrastructure.database.models import UserModel
from app.use_cases.interfaces.user_repository import UserRepositoryInterface


class SqlUserRepository(UserRepositoryInterface):
    """User persistence adapter using SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """Injects active SQLAlchemy session.

        Args:
            session: Active database session.
        """
        self.session = session

    def _to_entity(self, model: UserModel) -> User:
        """Converts database ORM model to a pure domain entity."""
        return User(
            id=model.id,
            email=model.email,
            hashed_password=model.hashed_password,
            full_name=model.full_name,
            base_currency=model.base_currency,
            timezone=model.timezone,
            is_active=model.is_active,
            created_at=model.created_at,
        )

    def get_by_id(self, user_id: int) -> User | None:
        """Finds a user by primary key."""
        model = self.session.query(UserModel).filter(UserModel.id == user_id).first()
        return self._to_entity(model) if model else None

    def get_by_email(self, email: str) -> User | None:
        """Finds a user by unique email address."""
        model = self.session.query(UserModel).filter(UserModel.email == email).first()
        return self._to_entity(model) if model else None

    def create(self, user: User) -> User:
        """Stage a new user entity in the request transaction."""
        model = UserModel(
            email=user.email,
            hashed_password=user.hashed_password,
            full_name=user.full_name,
            base_currency=user.base_currency,
            timezone=user.timezone,
            is_active=user.is_active,
        )
        self.session.add(model)
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)

    def update(self, user: User) -> User:
        model = self.session.get(UserModel, user.id)
        if model is None:
            raise ValueError("User not found")
        model.email = user.email
        model.full_name = user.full_name
        model.base_currency = user.base_currency
        model.timezone = user.timezone
        model.hashed_password = user.hashed_password
        model.is_active = user.is_active
        self.session.flush()
        self.session.refresh(model)
        return self._to_entity(model)
