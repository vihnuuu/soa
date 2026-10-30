from fastapi import APIRouter, Depends, HTTPException, Query, status
from src.books.dependencies import get_book_service
from src.books.exceptions import BookAlreadyExistsError, BookNotFoundError
from src.books.schemas import BookCreate, BookResponse
from src.books.service import BookService

router = APIRouter(prefix="/books", tags=["Books"])


@router.post(
    "",
    response_model=BookResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_book(
    book_in: BookCreate,
    service: BookService = Depends(get_book_service),
):
    try:
        return await service.create_book(book_in)
    except BookAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Книга з таким ID вже існує",
        )


@router.get("", response_model=list[BookResponse])
async def get_books(
    owner_id: str | None = Query(default=None),
    service: BookService = Depends(get_book_service),
):
    return await service.get_all_books(owner_id=owner_id)


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(
    book_id: str,
    owner_id: str = Query(..., min_length=1),
    service: BookService = Depends(get_book_service),
):
    try:
        return await service.get_book(book_id=book_id, owner_id=owner_id)
    except BookNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Книга не знайдена або доступ обмежений",
        )