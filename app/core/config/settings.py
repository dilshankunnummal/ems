"""
Centralized application configuration.

All environment-driven settings live here and nowhere else. Every other
module reads configuration through the `get_settings()` accessor so that
settings are loaded once, validated once, and cached for the lifetime of
the process.
"""
from functools import lru_cache
from typing import List
from urllib.parse import quote_plus

from pydantic import EmailStr, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_SECRETS = {
    "change-this-to-a-64-char-random-secret-in-production",
    "secret",
    "changeme",
}


class Settings(BaseSettings):
    """Strongly-typed application settings sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "Enterprise Employee Management System"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # --- Server ---
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # --- Security / JWT ---
    SECRET_KEY: str = Field(..., min_length=16)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24

    # --- Database ---
    # Only DB_HOST/PORT/USER/PASSWORD/NAME are configured via environment.
    # DATABASE_URL / DATABASE_URL_SYNC below are *derived* from these —
    # never set independently, so there is exactly one source of truth
    # for where the database lives.
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "ems_user"
    DB_PASSWORD: str = ""
    DB_NAME: str = "ems_db"
    DB_ECHO: bool = False

    @property
    def DATABASE_URL(self) -> str:
        """Async SQLAlchemy DSN (asyncpg), built from DB_* settings."""
        return self._build_db_url("postgresql+asyncpg")

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Sync SQLAlchemy DSN (psycopg2), used by Alembic's sync fallback
        and any tooling that doesn't support async."""
        return self._build_db_url("postgresql+psycopg2")

    def _build_db_url(self, driver: str) -> str:
        auth = quote_plus(self.DB_USER)
        if self.DB_PASSWORD:
            auth = f"{auth}:{quote_plus(self.DB_PASSWORD)}"
        return f"{driver}://{auth}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # --- Redis ---
    # Same principle: REDIS_URL is derived from REDIS_HOST/PORT/DB/PASSWORD,
    # never configured as a separate literal.
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    CACHE_TTL_SECONDS: int = 300

    @property
    def REDIS_URL(self) -> str:
        auth = f":{quote_plus(self.REDIS_PASSWORD)}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # --- Rate limiting ---
    RATE_LIMIT_TIMES: int = 100
    RATE_LIMIT_SECONDS: int = 60

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # --- Email / SMTP ---
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: EmailStr = "noreply@ems.com"
    SMTP_FROM_NAME: str = "EMS Notifications"
    SMTP_USE_TLS: bool = True
    FRONTEND_URL: str = "http://localhost:3000"

    # --- File uploads ---
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_EXTENSIONS: str = ".jpg,.jpeg,.png,.webp"
    ALLOWED_DOCUMENT_EXTENSIONS: str = ".pdf,.doc,.docx"

    @property
    def allowed_image_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_IMAGE_EXTENSIONS.split(",")]

    @property
    def allowed_document_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_DOCUMENT_EXTENSIONS.split(",")]

    # --- Pagination ---
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # --- Logging ---
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    # --- Superuser seed ---
    FIRST_SUPERUSER_EMAIL: EmailStr = "admin@ems.com"
    FIRST_SUPERUSER_PASSWORD: str = "ChangeMe123!"
    FIRST_SUPERUSER_FULL_NAME: str = "System Administrator"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @model_validator(mode="after")
    def _guard_production_secrets(self) -> "Settings":
        """Fail fast at startup if production is about to run with a
        placeholder secret — better a crash on boot than a silently
        forgeable JWT in a live environment.
        """
        if self.is_production:
            if self.SECRET_KEY.lower() in _INSECURE_DEFAULT_SECRETS or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY must be a unique, randomly generated value of at "
                    "least 32 characters when APP_ENV=production."
                )
            if self.APP_DEBUG:
                raise ValueError("APP_DEBUG must be false when APP_ENV=production.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached, process-wide Settings instance."""
    return Settings()
