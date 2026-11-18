from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from src.core.security import Principal, get_principal, require_owner, resolve_owner
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


def _check_owner(loan, principal: Principal) -> None:
    if not principal.is_trusted_service and str(loan.owner_id).lower() != principal.subject.lower():
        raise LoanNotFoundError()


async def _ensure_loan_owner(service: LoanService, loan_id: UUID, principal: Principal) -> None:
    _check_owner(await service.get_loan(str(loan_id)), principal)


@router.post(
    "",
    response_model=LoanActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_loan(
    loan_in: LoanRequest,
    principal: Principal = Security(get_principal, scopes=["lending:write"]),
    service: LoanService = Depends(get_loan_service),
):
    owner = require_owner(principal, loan_in.owner_id)
    verified = loan_in.model_copy(update={"owner_id": owner})
    try:
        loan_id = await service.create_loan(verified)
        return {"message": "Запит на оформлення позики прийнято в обробку", "loan_id": str(loan_id)}
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
    principal: Principal = Security(get_principal, scopes=["lending:read"]),
    service: LoanService = Depends(get_loan_service),
):
    return await service.get_loans(resolve_owner(principal, owner_id))


@router.get("/active", response_model=list[LoanResponse])
async def get_active_loans(
    owner_id: UUID | None = Query(default=None),
    principal: Principal = Security(get_principal, scopes=["lending:read"]),
    service: LoanService = Depends(get_loan_service),
):
    return await service.get_active_loans(resolve_owner(principal, owner_id))


@router.post(
    "/{loan_id}/return",
    response_model=LoanActionResponse,
)
async def return_loan(
    loan_id: UUID,
    principal: Principal = Security(get_principal, scopes=["lending:write"]),
    service: LoanService = Depends(get_loan_service),
):
    try:
        await _ensure_loan_owner(service, loan_id, principal)
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
    principal: Principal = Security(get_principal, scopes=["lending:read"]),
    service: LoanService = Depends(get_loan_service),
):
    try:
        loan = await service.get_loan(str(loan_id))
        _check_owner(loan, principal)
        return loan
    except LoanNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Позику не знайдено",
        )