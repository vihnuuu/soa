import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.books.models import Book
from src.books.schemas import BookCreate


def _to_uuid(value) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _to_dict(book: Book) -> dict:
    return {
        "id": str(book.id),
        "title": book.title,
        "author": book.author,
        "owner_id": str(book.owner_id),
    }


class BookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, book_id) -> dict | None:
        uid = _to_uuid(book_id)
        if uid is None:
            return None
        book = await self.session.get(Book, uid)
        return _to_dict(book) if book else None

    async def list_books(self, owner_id: str | None = None) -> list[dict]:
        query = select(Book)
        if owner_id:
            uid = _to_uuid(owner_id)
            if uid is None:
                return []
            query = query.where(Book.owner_id == uid)
        result = await self.session.execute(query)
        return [_to_dict(b) for b in result.scalars().all()]

    async def create(self, book_data: BookCreate) -> dict:
        book = Book(
            id=book_data.id,
            title=book_data.title,
            author=book_data.author,
            owner_id=book_data.owner_id,
        )
        self.session.add(book)
        await self.session.commit()
        return _to_dict(book)