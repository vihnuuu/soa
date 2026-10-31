from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_title: str = "Notification Service"
    rabbit_host: str = "rabbitmq"
    rabbit_queue: str = "loan_notifications"
    rabbit_dlq: str = "loan_notifications_dlq"
    environment: str = "development"
    simulate_saga_fault: bool = False

    database_url: PostgresDsn = (
        "postgresql+asyncpg://library_user:library_password@postgres:5432/notification_db"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()