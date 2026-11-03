from datetime import datetime
import uuid
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.loans.models import Loan, LoanStatus, OutboxMessage
from sqlalchemy.exc import IntegrityError
from src.loans.exceptions import BookAlreadyLoanedError


class LoanRepository:

  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def get_by_id(self, loan_id: str | uuid.UUID) -> Loan | None:
    if isinstance(loan_id, str):
      loan_id = uuid.UUID(loan_id)
    query = select(Loan).where(Loan.id == loan_id)
    result = await self.session.execute(query)
    return result.scalar_one_or_none()

  async def is_book_active(self, book_id: str | uuid.UUID) -> bool:
    if isinstance(book_id, str):
      book_id = uuid.UUID(book_id)
    query = select(Loan).where(
        Loan.book_id == book_id,
        Loan.status.in_([LoanStatus.PENDING, LoanStatus.ACTIVE]),
    )
    result = await self.session.execute(query)
    return result.scalar_one_or_none() is not None

  async def create_with_outbox(
          self, record: dict, outbox_event: OutboxMessage
  ) -> None:
      raw_due = record.get("due_date")
      loan = Loan(
          id=uuid.UUID(str(record["loan_id"])),
          book_id=uuid.UUID(str(record["book_id"])),
          owner_id=uuid.UUID(str(record["owner_id"])),
          borrower_name=record["borrower_name"],
          status=LoanStatus(record["status"]),
          due_date=(
              datetime.fromisoformat(raw_due) if isinstance(raw_due, str) else raw_due
          ),
      )
      self.session.add(loan)
      self.session.add(outbox_event)

      try:
          await self.session.commit()
      except IntegrityError:
          await self.session.rollback()
          raise BookAlreadyLoanedError()

  async def update_status_with_outbox(
          self, loan_id: str | uuid.UUID, status: str, outbox_event: OutboxMessage
  ) -> None:
      if isinstance(loan_id, str):
          loan_id = uuid.UUID(loan_id)

      query = (
          update(Loan)
          .where(Loan.id == loan_id)
          .values(status=LoanStatus(status))
      )
      await self.session.execute(query)
      self.session.add(outbox_event)
      await self.session.commit()


  async def get_next_id(self) -> str:
    return str(uuid.uuid4())

  async def list_active(
      self, owner_id: str | uuid.UUID | None = None
  ) -> list[Loan]:
    query = select(Loan).where(Loan.status == LoanStatus.ACTIVE)
    if owner_id:
      if isinstance(owner_id, str):
        owner_id = uuid.UUID(owner_id)
      query = query.where(Loan.owner_id == owner_id)
    result = await self.session.execute(query)
    return list(result.scalars().all())

  async def list_all(
      self, owner_id: str | uuid.UUID | None = None
  ) -> list[Loan]:
    query = select(Loan)
    if owner_id:
      if isinstance(owner_id, str):
        owner_id = uuid.UUID(owner_id)
      query = query.where(Loan.owner_id == owner_id)
    result = await self.session.execute(query)
    return list(result.scalars().all())