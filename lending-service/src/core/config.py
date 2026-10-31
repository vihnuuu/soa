from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_title: str = "Lending Service"
    root_path: str = "/api/lending"
    catalog_service_url: str = "http://catalog-service:8001"
    rabbit_host: str = "rabbitmq"
    rabbit_queue: str = "loan_notifications"
    rabbit_dlq: str = "loan_notifications_dlq"
    environment: str = "development"
    debug: bool = False
    saga_timeout_seconds: int = 30

    database_url: PostgresDsn = (
        "postgresql+asyncpg://library_user:library_password@postgres:5432/lending_db"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()