from src.broker.publisher import EventPublisher
from src.clients.catalog_client import CatalogClient
from src.loans.exceptions import (
    BookAlreadyLoanedError,
    EventPublishError,
    LoanAlreadyReturnedError,
    LoanNotFoundError,
)
from src.loans.repository import LoanRepository
from src.loans.schemas import LoanRequest


class LoanService:
    def __init__(
        self,
        repository: LoanRepository,
        catalog_client: CatalogClient,
        publisher: EventPublisher,
    ) -> None:
        self.repository = repository
        self.catalog_client = catalog_client
        self.publisher = publisher

    async def get_loan(self, loan_id: str) -> dict:
        loan = await self.repository.get_by_id(loan_id)
        if not loan:
            raise LoanNotFoundError()
        return loan

    async def get_active_loans(self) -> list[dict]:
        return await self.repository.list_active()

    async def create_loan(self, loan_in: LoanRequest) -> str:
        await self.catalog_client.verify_book(
            book_id=loan_in.book_id,
            owner_id=loan_in.owner_id,
        )

        if await self.repository.is_book_active(loan_in.book_id):
            raise BookAlreadyLoanedError()

        loan_id = await self.repository.get_next_id()
        record = {
            "loan_id": loan_id,
            "book_id": loan_in.book_id,
            "borrower_name": loan_in.borrower_name,
            "owner_id": loan_in.owner_id,
            "status": "Active",
        }
        await self.repository.create(record)

        event_payload = {
            "event_type": "LoanCreated",
            "loan_id": loan_id,
            "book_id": loan_in.book_id,
            "borrower_name": loan_in.borrower_name,
            "owner_id": loan_in.owner_id,
        }
        try:
            await self.publisher.publish(event_payload)
        except EventPublishError:
            await self.repository.delete(loan_id=loan_id, book_id=loan_in.book_id)
            raise

        return loan_id

    async def return_loan(self, loan_id: str) -> str:
        record = await self.repository.get_by_id(loan_id)
        if not record:
            raise LoanNotFoundError()

        if record["status"] != "Active":
            raise LoanAlreadyReturnedError()

        await self.repository.update_status(loan_id, "Returned")
        await self.repository.remove_active_book(record["book_id"])

        event_payload = {
            "event_type": "LoanReturned",
            "loan_id": record["loan_id"],
            "book_id": record["book_id"],
            "borrower_name": record["borrower_name"],
            "owner_id": record["owner_id"],
        }
        try:
            await self.publisher.publish(event_payload)
        except EventPublishError:
            await self.repository.update_status(loan_id, "Active")
            await self.repository.add_active_book(record["book_id"])
            raise

        return loan_id