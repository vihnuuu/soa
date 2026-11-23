import asyncio
import time

import httpx

from src.core.config import settings


class TokenProviderError(Exception):
    pass


class ServiceTokenProvider:

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        async with self._lock:
            if self._token and time.monotonic() < self._expires_at - 30:
                return self._token
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.post(
                        settings.oidc_token_url,
                        data={"grant_type": "client_credentials"},
                        auth=(settings.oidc_client_id, settings.oidc_client_secret),
                        timeout=3.0,
                    )
            except httpx.RequestError as exc:
                raise TokenProviderError("Authorization server unreachable") from exc
            if res.status_code != 200:
                raise TokenProviderError(f"Token request failed: {res.status_code}")
            data = res.json()
            self._token = data["access_token"]
            self._expires_at = time.monotonic() + int(data.get("expires_in", 60))
            return self._token

    async def auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self.get_token()}"}


token_provider = ServiceTokenProvider()
