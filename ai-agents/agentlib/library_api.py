from __future__ import annotations

from typing import Any

import httpx

from agentlib.exceptions import LibraryAPIError


def _describe_error(res: httpx.Response) -> str:
    detail: Any = None
    try:
        detail = res.json().get("detail")
    except Exception:
        pass
    if isinstance(detail, str):
        text = detail
    elif isinstance(detail, list):
        parts = []
        for item in detail[:3]:
            loc = ".".join(str(p) for p in item.get("loc", [])[1:])
            parts.append(f"{loc}: {item.get('msg')}")
        text = "; ".join(parts) or "validation error"
    else:
        text = "no details"
    return f"HTTP {res.status_code}: {text[:200]}"


class LibraryAPI:
    def __init__(self, gateway_url: str, timeout: float = 5.0, client: httpx.AsyncClient | None = None) -> None:
        self.base = gateway_url.rstrip("/")
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            res = await self._client.request(method, f"{self.base}{path}", **kwargs)
        except httpx.TimeoutException:
            raise LibraryAPIError("API gateway timeout") from None
        except httpx.RequestError:
            raise LibraryAPIError("API gateway is unreachable") from None
        if res.status_code >= 400:
            raise LibraryAPIError(_describe_error(res), res.status_code)
        try:
            return res.json()
        except ValueError:
            raise LibraryAPIError("API returned a non-JSON response", res.status_code) from None

    async def list_books(self, owner_id: str) -> list[dict]:
        return await self._request("GET", "/api/catalog/books", params={"owner_id": owner_id})

    async def get_book(self, book_id: str, owner_id: str) -> dict:
        return await self._request("GET", f"/api/catalog/books/{book_id}", params={"owner_id": owner_id})

    async def create_book(self, payload: dict) -> dict:
        return await self._request("POST", "/api/catalog/books", json=payload)

    async def create_loan(self, book_id: str, owner_id: str, borrower_name: str) -> dict:
        body = {"book_id": book_id, "owner_id": owner_id, "borrower_name": borrower_name}
        return await self._request("POST", "/api/lending/loans", json=body)

    async def get_loan(self, loan_id: str) -> dict:
        return await self._request("GET", f"/api/lending/loans/{loan_id}")

    async def list_loans(self, owner_id: str, active_only: bool = False) -> list[dict]:
        path = "/api/lending/loans/active" if active_only else "/api/lending/loans"
        return await self._request("GET", path, params={"owner_id": owner_id})

    async def return_loan(self, loan_id: str) -> dict:
        return await self._request("POST", f"/api/lending/loans/{loan_id}/return", json={})