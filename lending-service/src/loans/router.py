from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from src.loans.dependencies import get_loan_service
from src.loans.exceptions import (
    BookAlreadyLoanedError,
    BookCatalogNotFoundError,
    CatalogServiceBadResponseError,
    CatalogServiceUnavailableError,
    LoanAlreadyReturnedError,
    LoanNotFoundError,
)
from src.loans.schemas import LoanActionResponse, LoanRequest, LoanResponse
from src.loans.service import LoanService

router = APIRouter(prefix="/loans", tags=["Loans"])


@router.post(
    "",
    response_model=LoanActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_loan(
    loan_in: LoanRequest,
    service: LoanService = Depends(get_loan_service),
):
    try:
        loan_id = await service.create_loan(loan_in)
        return {"message": "Позику успішно оформлено", "loan_id": str(loan_id)}
    except CatalogServiceUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Catalog Service недоступний",
        )
    except BookCatalogNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Книгу не знайдено в каталозі",
        )
    except CatalogServiceBadResponseError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Помилка відповіді Catalog Service",
        )
    except BookAlreadyLoanedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Книга вже видана (активна позика вже існує)",
        )


@router.get("", response_model=list[LoanResponse])
@router.get("/", response_model=list[LoanResponse], include_in_schema=False)
async def get_loans(
    owner_id: UUID | None = Query(default=None),
    service: LoanService = Depends(get_loan_service),
):
    if hasattr(service, "get_loans"):
        return await service.get_loans(str(owner_id) if owner_id else None)
    return await service.get_active_loans()


@router.get("/active", response_model=list[LoanResponse])
async def get_active_loans(
    owner_id: UUID | None = Query(default=None),
    service: LoanService = Depends(get_loan_service),
):
  return await service.get_active_loans(str(owner_id) if owner_id else None)


@router.post("/{loan_id}/return", response_model=LoanActionResponse)
async def return_loan(
    loan_id: UUID,
    service: LoanService = Depends(get_loan_service),
):
    try:
        res_id = await service.return_loan(str(loan_id))
        return {"message": "Книгу повернено, позику завершено", "loan_id": str(res_id)}
    except LoanNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Позику не знайдено",
        )
    except LoanAlreadyReturnedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Позику вже завершено або вона не є активною",
        )


@router.get("/{loan_id}", response_model=LoanResponse)
async def get_loan(
    loan_id: UUID,
    service: LoanService = Depends(get_loan_service),
):
    try:
        return await service.get_loan(str(loan_id))
    except LoanNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Позику не знайдено",
        )