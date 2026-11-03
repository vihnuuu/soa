from src.books.exceptions import BookAlreadyExistsError, BookNotFoundError
from src.books.repository import BookRepository
from src.books.schemas import BookCreate


class BookService:

    def __init__(self, repository: BookRepository) -> None:
        self.repository = repository

    async def get_book(self, book_id: str, owner_id: str) -> dict:
        book = await self.repository.get_by_id(book_id)
        if not book or str(book.get("owner_id")).lower() != str(owner_id).lower():
            raise BookNotFoundError()
        return book

    async def get_all_books(self, owner_id: str | None = None) -> list[dict]:
        return await self.repository.list_books(owner_id=owner_id)

    async def create_book(self, book_data: BookCreate) -> dict:
        return await self.repository.create(book_data)

    async def update_availability(
        self,
        book_id: str,
        is_available: bool,
    ) -> dict:
        book = await self.repository.update_availability(
            book_id,
            is_available,
        )
        if not book:
            raise BookNotFoundError()
        return book