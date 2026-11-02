from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.books.repository import BookRepository
from src.books.service import BookService
from src.core.database import get_db_session


def get_book_repository(
    session: AsyncSession = Depends(get_db_session),
) -> BookRepository:
    return BookRepository(session)


def get_book_service(
    repo: BookRepository = Depends(get_book_repository),
) -> BookService:
    return BookService(repository=repo)