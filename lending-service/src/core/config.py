from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_title: str = "Lending Service"
    root_path: str = "/api/lending"
    catalog_service_url: str = "http://catalog-service:8001"
    rabbit_host: str = "rabbitmq"
    rabbit_queue: str = "loan_notifications"
    rabbit_dlq: str = "loan_notifications_dlq"
    rabbit_dlx: str = "dlx_exchange"
    rabbit_reply_queue: str = "loan_saga_replies"
    environment: str = "development"
    debug: bool = False
    saga_timeout_seconds: int = 30

    database_url: PostgresDsn

    oidc_issuer: str = "http://localhost:8180/realms/library"
    oidc_audience: str = "lending-service"
    oidc_jwks_url: str = (
        "http://keycloak:8080/realms/library/protocol/openid-connect/certs"
    )
    oidc_authorization_url: str = (
        "http://localhost:8180/realms/library/protocol/openid-connect/auth"
    )
    oidc_public_token_url: str = (
        "http://localhost:8180/realms/library/protocol/openid-connect/token"
    )
    oidc_swagger_client_id: str = "library-web"

    trusted_service_clients: list[str] = []
    rate_limit_per_minute: int = 120
    redis_url: str | None = None

    oidc_token_url: str = (
        "http://keycloak:8080/realms/library/protocol/openid-connect/token"
    )
    oidc_client_id: str = "lending-service"
    oidc_client_secret: str

    cors_allowed_origins: list[str] = [
        "https://cad.kpi.ua",
        "http://cad.kpi.ua",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()