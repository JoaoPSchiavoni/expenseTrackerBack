"""
Security, Password Hashing, and JWT Management Module.

Why: Isolates cryptographic algorithms and token session issuance
within the infrastructure layer, maintaining Single Responsibility.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str) -> str:
    """Generates a secure hash with a random salt using bcrypt.

    Why: Uses an adaptive work factor that protects against brute-force attacks.

    Args:
        password: Plain text password.

    Returns:
        String containing the generated secure hash.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies whether a plain text password matches the stored bcrypt hash.

    Args:
        plain_password: Plain text password provided by the user.
        hashed_password: Stored bcrypt hash.

    Returns:
        True if matched, False otherwise.
    """
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, email: str, expires_delta: timedelta | None = None) -> str:
    """Generates a signed JWT token containing user ID and email claims.

    Why: Enables stateless authentication between client and API.

    Args:
        user_id: Unique user identifier.
        email: User email address.
        expires_delta: Optional custom validity window.

    Returns:
        JWT string signed with the configured algorithm (HS256).
    """
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "exp": expire,
        "iat": now,
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decodes and validates signature and expiration of a JWT token.

    Args:
        token: JWT string received from Authorization header.

    Returns:
        Payload dictionary if valid, or None if invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
        )
        return payload
    except (jwt.PyJWTError, ValueError):
        return None
