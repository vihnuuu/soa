from fastapi import Depends
from src.books.repository import BookRepository, book_repository
from src.books.service import BookService


def get_book_repository() -> BookRepository:
    return book_repository


def get_book_service(
    repo: BookRepository = Depends(get_book_repository),
) -> BookService:
    return BookService(repository=repo)