import httpx
from src.core.config import settings
from src.loans.exceptions import (
    BookCatalogNotFoundError,
    CatalogServiceBadResponseError,
    CatalogServiceUnavailableError,
)


class CatalogClient:
    def __init__(self, base_url: str = settings.catalog_service_url) -> None:
        self.base_url = base_url.rstrip("/")

    async def verify_book(self, book_id: str, owner_id: str) -> None:
        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(
                    f"{self.base_url}/books/{book_id}",
                    params={"owner_id": owner_id},
                    timeout=3.0,
                )
            except httpx.RequestError as exc:
                raise CatalogServiceUnavailableError() from exc

        if res.status_code == 404:
            raise BookCatalogNotFoundError()

        if res.status_code != 200:
            raise CatalogServiceBadResponseError()


catalog_client = CatalogClient()