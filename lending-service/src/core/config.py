from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_title: str = "Lending Service"
    root_path: str = "/api/lending"
    catalog_service_url: str = "http://catalog-service:8001"
    rabbit_host: str = "rabbitmq"
    rabbit_queue: str = "loan_notifications"
    environment: str = "development"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()