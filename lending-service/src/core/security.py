from shared.security import (
    Principal,
    SecurityConfig,
    create_security,
    require_owner,
    resolve_owner,
)
from src.core.config import settings

SCOPES = {
    "lending:read": "Read loans",
    "lending:write": "Create loans and return books",
}

_security = create_security(
    SecurityConfig(
        service_name="lending",
        issuer=settings.oidc_issuer,
        jwks_url=settings.oidc_jwks_url,
        audience=settings.oidc_audience,
        authorization_url=settings.oidc_authorization_url,
        token_url=settings.oidc_public_token_url,
        scopes=SCOPES,
        trusted_clients=frozenset(settings.trusted_service_clients),
        rate_limit_per_minute=settings.rate_limit_per_minute,
        redis_url=settings.redis_url,
    )
)

oauth2_scheme = _security.oauth2_scheme
get_principal = _security.get_principal
decode_token = _security.decode_token

__all__ = [
    "Principal",
    "SCOPES",
    "decode_token",
    "get_principal",
    "oauth2_scheme",
    "require_owner",
    "resolve_owner",
]
