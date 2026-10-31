from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_title: str = "Catalog Service"
    root_path: str = "/api/catalog"
    environment: str = "development"
    debug: bool = False

    database_url: PostgresDsn = (
        "postgresql+asyncpg://library_user:library_password@postgres:5432/catalog_db"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_title: str = "Catalog Service"
    root_path: str = "/api/catalog"
    environment: str = "development"
    debug: bool = False

    database_url: PostgresDsn = (
        "postgresql+asyncpg://library_user:library_password@postgres:5432/catalog_db"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

settings = Settings()