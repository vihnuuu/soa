from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from src.core.security import Principal, get_principal, require_owner, resolve_owner
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
    principal: Principal = Security(get_principal, scopes=["catalog:write"]),
    service: BookService = Depends(get_book_service),
):
    owner = require_owner(principal, book_in.owner_id)
    book = book_in.model_copy(update={"owner_id": owner})
    try:
        return await service.create_book(book)
    except BookAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Книга з таким ID вже існує",
        )


@router.get(
    "",
    response_model=list[BookResponse],
)
async def get_books(
    owner_id: str | None = Query(default=None),
    principal: Principal = Security(get_principal, scopes=["catalog:read"]),
    service: BookService = Depends(get_book_service),
):
    return await service.get_all_books(owner_id=resolve_owner(principal, owner_id))


@router.get(
    "/{book_id}",
    response_model=BookResponse,
)
async def get_book(
    book_id: str,
    owner_id: str = Query(..., min_length=1),
    principal: Principal = Security(get_principal, scopes=["catalog:read"]),
    service: BookService = Depends(get_book_service),
):
    owner = require_owner(principal, owner_id)
    try:
        return await service.get_book(book_id=book_id, owner_id=str(owner))
    except BookNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Книга не знайдена або доступ обмежений",
        )


@router.patch(
    "/{book_id}/availability",
    response_model=BookResponse,
)
async def update_book_availability(
    book_id: str,
    is_available: bool,
    principal: Principal = Security(get_principal, scopes=["catalog:write"]),
    service: BookService = Depends(get_book_service),
):
    if not principal.is_trusted_service:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Endpoint is available only for internal services",
        )
    try:
        return await service.update_availability(book_id, is_available)
    except BookNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Книга не знайдена",
        )