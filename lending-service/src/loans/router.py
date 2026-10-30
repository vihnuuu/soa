from fastapi import APIRouter, Depends, HTTPException, status
from src.loans.dependencies import get_loan_service
from src.loans.exceptions import (
    BookAlreadyLoanedError,
    BookCatalogNotFoundError,
    CatalogServiceBadResponseError,
    CatalogServiceUnavailableError,
    EventPublishError,
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
        return {"message": "Позику успішно оформлено", "loan_id": loan_id}
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
    except EventPublishError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Не вдалося надіслати подію. Спробуйте пізніше.",
        )


@router.post("/{loan_id}/return", response_model=LoanActionResponse)
async def return_loan(
    loan_id: str,
    service: LoanService = Depends(get_loan_service),
):
    try:
        res_id = await service.return_loan(loan_id)
        return {"message": "Книгу повернено, позику завершено", "loan_id": res_id}
    except LoanNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Позику не знайдено",
        )
    except LoanAlreadyReturnedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Позику вже завершено",
        )
    except EventPublishError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Не вдалося надіслати подію. Спробуйте пізніше.",
        )


@router.get("/active", response_model=list[LoanResponse])
async def get_active_loans(service: LoanService = Depends(get_loan_service)):
    return await service.get_active_loans()


@router.get("/{loan_id}", response_model=LoanResponse)
async def get_loan(
    loan_id: str,
    service: LoanService = Depends(get_loan_service),
):
    try:
        return await service.get_loan(loan_id)
    except LoanNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Позику не знайдено",
        )