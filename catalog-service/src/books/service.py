from src.books.exceptions import BookAlreadyExistsError, BookNotFoundError
from src.books.repository import BookRepository
from src.books.schemas import BookCreate


class BookService:

  def __init__(self, repository: BookRepository) -> None:
    self.repository = repository

  async def get_book(self, book_id: str, owner_id: str) -> dict:
    book = await self.repository.get_by_id(book_id)
    if not book or str(book.get("owner_id")) != str(owner_id):
      raise BookNotFoundError()
    return book

  async def get_all_books(self, owner_id: str | None = None) -> list[dict]:
    return await self.repository.list_books(owner_id=owner_id)

  async def create_book(self, book_data: BookCreate) -> dict:
    existing = await self.repository.get_by_id(book_data.id)
    if existing:
      raise BookAlreadyExistsError()
    return await self.repository.create(book_data)