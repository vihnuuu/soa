import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer, SecurityScopes
from jwt import PyJWKClient

from shared.security.principal import Principal
from shared.security.rate_limit import RateLimiter, build_rate_limiter

logger = logging.getLogger("shared.security.auth")


@dataclass(frozen=True)
class SecurityConfig:
    service_name: str
    issuer: str
    jwks_url: str
    audience: str
    authorization_url: str
    token_url: str
    scopes: dict[str, str]
    trusted_clients: frozenset[str] = field(default_factory=frozenset)
    rate_limit_per_minute: int = 120
    redis_url: str | None = None
    algorithms: tuple[str, ...] = ("RS256",)
    leeway_seconds: int = 0


@dataclass(frozen=True)
class Security:
    oauth2_scheme: OAuth2AuthorizationCodeBearer
    get_principal: Callable[..., Principal]
    decode_token: Callable[[str], dict]
    rate_limiter: RateLimiter


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def create_security(config: SecurityConfig) -> Security:
    oauth2_scheme = OAuth2AuthorizationCodeBearer(
        authorizationUrl=config.authorization_url,
        tokenUrl=config.token_url,
        scopes=config.scopes,
    )
    jwks_client = PyJWKClient(config.jwks_url, cache_keys=True, lifespan=3600)
    rate_limiter = build_rate_limiter(
        limit=config.rate_limit_per_minute,
        window=60,
        redis_url=config.redis_url,
        prefix=f"rl:{config.service_name}",
    )

    def decode_token(token: str) -> dict:
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=list(config.algorithms),
                issuer=config.issuer,
                audience=config.audience,
                leeway=config.leeway_seconds,
                options={"require": ["exp", "iss", "sub", "aud"]},
            )
        except jwt.PyJWKClientConnectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authorization server is unavailable",
            ) from exc
        except jwt.PyJWTError as exc:
            raise _unauthorized("Invalid or expired token") from exc

    def get_principal(
        security_scopes: SecurityScopes,
        token: str = Depends(oauth2_scheme),
    ) -> Principal:
        claims = decode_token(token)
        granted = frozenset(str(claims.get("scope", "")).split())
        required = " ".join(security_scopes.scopes)
        if any(s not in granted for s in security_scopes.scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient scope. Required: {required}",
                headers={
                    "WWW-Authenticate": f'Bearer error="insufficient_scope", scope="{required}"'
                },
            )
        client_id = claims.get("azp")
        is_trusted = client_id in config.trusted_clients
        if not is_trusted:
            decision = rate_limiter.hit(claims["sub"])
            if not decision.allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(decision.retry_after)},
                )
        return Principal(
            subject=claims["sub"],
            username=claims.get("preferred_username"),
            scopes=granted,
            client_id=client_id,
            is_trusted_service=is_trusted,
        )

    return Security(
        oauth2_scheme=oauth2_scheme,
        get_principal=get_principal,
        decode_token=decode_token,
        rate_limiter=rate_limiter,
    )