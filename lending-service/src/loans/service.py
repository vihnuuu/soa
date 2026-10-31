from datetime import datetime, timedelta, timezone
from src.clients.catalog_client import CatalogClient
from src.loans.exceptions import (
    BookAlreadyLoanedError,
    LoanAlreadyReturnedError,
    LoanNotFoundError,
)
from src.loans.models import Loan, OutboxMessage, OutboxStatus
from src.loans.repository import LoanRepository
from src.loans.schemas import LoanRequest


class LoanService:

    def __init__(
        self,
        repository: LoanRepository,
        catalog_client: CatalogClient,
    ) -> None:
        self.repository = repository
        self.catalog_client = catalog_client

    async def get_loan(self, loan_id: str) -> Loan:
        loan = await self.repository.get_by_id(loan_id)
        if not loan:
            raise LoanNotFoundError()
        return loan

    async def get_active_loans(
        self, owner_id: str | None = None
    ) -> list[Loan]:
        return await self.repository.list_active(owner_id)

    async def get_loans(self, owner_id: str | None = None) -> list[Loan]:
        return await self.repository.list_all(owner_id)

    async def create_loan(self, loan_in: LoanRequest) -> str:
        await self.catalog_client.verify_book(
            book_id=loan_in.book_id,
            owner_id=loan_in.owner_id,
        )

        if await self.repository.is_book_active(loan_in.book_id):
            raise BookAlreadyLoanedError()

        loan_id = await self.repository.get_next_id()
        now = datetime.now(timezone.utc)
        due_date = now + timedelta(days=14)

        record = {
            "loan_id": str(loan_id),
            "book_id": str(loan_in.book_id),
            "borrower_name": loan_in.borrower_name,
            "owner_id": str(loan_in.owner_id),
            "status": "PENDING",
            "loan_date": now.isoformat(),
            "due_date": due_date.isoformat(),
        }

        outbox_event = OutboxMessage(
            event_type="LoanCreated",
            payload=record,
            status=OutboxStatus.NEW,
        )

        await self.repository.create_with_outbox(record, outbox_event)
        return str(loan_id)

    async def return_loan(self, loan_id: str) -> str:
        record = await self.repository.get_by_id(loan_id)
        if not record:
            raise LoanNotFoundError()

        current_status = getattr(record, "status", None)
        status_str = (
            current_status.value
            if hasattr(current_status, "value")
            else str(current_status)
        )

        if status_str.upper() != "ACTIVE":
            raise LoanAlreadyReturnedError()

        actual_loan_id = getattr(record, "id", None) or getattr(
            record, "loan_id", loan_id
        )

        outbox_event = OutboxMessage(
            event_type="LoanReturned",
            payload={
                "loan_id": str(actual_loan_id),
                "book_id": str(record.book_id),
                "borrower_name": record.borrower_name,
                "owner_id": (
                    str(record.owner_id) if hasattr(record, "owner_id") else ""
                ),
            },
            status=OutboxStatus.NEW,
        )
        await self.repository.update_status_with_outbox(
            str(actual_loan_id), "RETURNED", outbox_event
        )
        await self.repository.remove_active_book(str(record.book_id))

        return str(actual_loan_id)