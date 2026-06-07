"""Application configuration via Pydantic Settings — reads from env vars."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = Field(default="python-fastapi-service", alias="SERVICE_NAME")
    service_version: str = Field(default="1.0.0", alias="APP_VERSION")
    environment: str = Field(default="production", alias="ENVIRONMENT")
    port: int = Field(default=8080, alias="PORT")
    workers: int = Field(default=4, alias="WORKERS")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    # Observability
    otel_endpoint: str = Field(default="", alias="OTEL_EXPORTER_OTLP_ENDPOINT")

    # Security
    allowed_origins: list[str] = Field(default=["*"], alias="ALLOWED_ORIGINS")
    api_key_header: str = Field(default="X-API-Key", alias="API_KEY_HEADER")

    # Database
    database_url: str = Field(default="", alias="DATABASE_URL")
    db_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")

    # Redis
    redis_url: str = Field(default="", alias="REDIS_URL")

    class Config:
        env_file = ".env"
        case_sensitive = False
