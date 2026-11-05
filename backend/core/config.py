from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore"
    )
    postgres_url: str
    jwt_secret: str = Field(min_length=32)
    jwt_issuer: str = "hotel-booking"
    jwt_audience: str = "hotel-api"
    access_token_minutes: int = Field(default=30, ge=1, le=1440)
    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"

    @field_validator("jwt_secret")
    @classmethod
    def reject_placeholder(cls, value: str) -> str:
        if value.startswith("replace-"):
            raise ValueError("Generate a private JWT_SECRET before starting")
        return value

    @field_validator("postgres_url")
    @classmethod
    def require_postgres(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("PostgreSQL with asyncpg is required")
        return value


conf = Settings()
