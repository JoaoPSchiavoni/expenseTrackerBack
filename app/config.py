"""
Application Configuration Module.

Why: Centralizes environment variable loading and validation using Pydantic Settings,
ensuring no hardcoded credentials exist in source code.
"""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for the Expense Tracker application.

    Why: Uses BaseSettings to strictly type and validate environment variables,
    allowing clean runtime overrides during integration tests.
    """

    APP_NAME: str = "Expense Tracker API"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "test", "production"] = "development"

    # Why: Fallback URL for development; in production this must be overridden via .env
    DATABASE_URL: str = (
        "postgresql://expense_tracker:expense_tracker@localhost:5432/expense_tracker"
    )

    # Security & JWT settings
    SECRET_KEY: str = "local-development-key-change-before-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_ISSUER: str = "expense-tracker-api"
    JWT_AUDIENCE: str = "expense-tracker-client"
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )
    EXCHANGE_RATE_API_URL: str = "https://api.frankfurter.dev/v2"
    EXCHANGE_RATE_TIMEOUT_SECONDS: float = Field(5.0, gt=0, le=30)
    IMPORT_MAX_FILE_SIZE_BYTES: int = Field(5 * 1024 * 1024, gt=0)
    IMPORT_MAX_ROWS: int = Field(5000, gt=0, le=50000)

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Reject development credentials when the application runs in production."""
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY == "local-development-key-change-before-production":
                raise ValueError("SECRET_KEY must be configured in production")
            if "expense_tracker:expense_tracker@localhost" in self.DATABASE_URL:
                raise ValueError("DATABASE_URL must be configured in production")
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
