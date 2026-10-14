"""Application configuration.

All settings come from environment variables (or the local .env file) and are
validated on startup, so a misconfigured deployment fails immediately instead
of breaking at the first request.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ app
    APP_NAME: str = "Smart Supply Lists API"
    APP_VERSION: str = "3.0.0"
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    LOG_LEVEL: str = "INFO"

    HOST: str = "127.0.0.1"
    PORT: int = 8000
    UVICORN_RELOAD: bool = False
    TRUST_PROXY_HEADERS: bool = False

    # ------------------------------------------------------------- database
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 5432
    DB_NAME: str = "smart_supply_list"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = Field(min_length=1)
    DB_MIN_CONNECTIONS: int = Field(default=1, ge=1, le=100)
    DB_MAX_CONNECTIONS: int = Field(default=10, ge=1, le=200)
    DB_CONNECT_TIMEOUT: int = Field(default=5, ge=1, le=60)
    DB_STATEMENT_TIMEOUT_MS: int = Field(default=10_000, ge=100, le=600_000)
    RUN_MIGRATIONS_ON_STARTUP: bool = True

    # ------------------------------------------------------------------ auth
    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    JWT_EXPIRE_MINUTES: int = Field(default=30, ge=1, le=1440)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, ge=1, le=365)
    PASSWORD_MIN_LENGTH: int = Field(default=8, ge=8, le=128)
    PBKDF2_ITERATIONS: int = Field(default=600_000, ge=310_000, le=5_000_000)

    # ---------------------------------------------------------------- limits
    MAX_BODY_BYTES: int = Field(default=1_048_576, ge=1024)
    RATE_LIMIT_WINDOW: int = Field(default=60, ge=1)
    RATE_LIMIT_REQUESTS: int = Field(default=120, ge=1)
    AUTH_RATE_LIMIT_REQUESTS: int = Field(default=10, ge=1)
    DB_THREAD_POOL_SIZE: int = Field(default=16, ge=2, le=128)

    MAX_LISTS_PER_USER: int = Field(default=200, ge=1)
    MAX_ITEMS_PER_LIST: int = Field(default=1000, ge=1)
    MAX_MEMBERS_PER_LIST: int = Field(default=50, ge=1)

    # ------------------------------------------------------------------ cors
    CORS_ORIGINS: str = "http://localhost:3000"

    # ----------------------------------------------------------- suggestions
    AI_SUGGESTIONS_ENABLED: bool = True
    SUGGESTIONS_DEFAULT_LIMIT: int = Field(default=5, ge=1, le=50)
    SUGGESTIONS_MAX_LIMIT: int = Field(default=20, ge=1, le=100)
    SUGGESTIONS_CACHE_TTL_SECONDS: int = Field(default=86_400, ge=0)
    SUGGESTIONS_MIN_SCORE: float = Field(default=0.05, ge=0.0, le=1.0)
    SUGGESTIONS_PROVIDER: Literal["statistical", "llm", "hybrid"] = "statistical"
    # NOTE (legacy, for compatibility): values "llm"/"hybrid" are still accepted
    # but always resolve to the statistical engine — LLM integration removed.

    # ------------------------------------------------------------ validators
    @field_validator("LOG_LEVEL")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        upper = value.strip().upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}")
        return upper

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _validate_secret(cls, value: str) -> str:
        weak = {
            "my_super_secret_jwt_key",
            "change_me",
            "secret",
            "changeme",
        }
        if value.strip().lower() in weak:
            raise ValueError("JWT_SECRET_KEY is a well-known placeholder, generate a new one")
        return value

    @model_validator(mode="after")
    def _validate_pool(self) -> "Settings":
        if self.DB_MAX_CONNECTIONS < self.DB_MIN_CONNECTIONS:
            raise ValueError("DB_MAX_CONNECTIONS must be >= DB_MIN_CONNECTIONS")
        if self.SUGGESTIONS_MAX_LIMIT < self.SUGGESTIONS_DEFAULT_LIMIT:
            raise ValueError("SUGGESTIONS_MAX_LIMIT must be >= SUGGESTIONS_DEFAULT_LIMIT")
        return self

    # --------------------------------------------------------------- helpers
    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def llm_configured(self) -> bool:
        """Legacy compatibility flag. LLM integration removed, always False."""
        return False

    @property
    def migrations_dir(self) -> Path:
        return PROJECT_ROOT / "migrations"

    def conninfo_kwargs(self) -> dict[str, object]:
        return {
            "host": self.DB_HOST,
            "port": self.DB_PORT,
            "dbname": self.DB_NAME,
            "user": self.DB_USER,
            "password": self.DB_PASSWORD,
            "connect_timeout": self.DB_CONNECT_TIMEOUT,
            "application_name": "smart_supply_api",
            "options": f"-c statement_timeout={self.DB_STATEMENT_TIMEOUT_MS}",
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
