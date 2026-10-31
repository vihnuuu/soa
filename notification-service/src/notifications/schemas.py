from enum import StrEnum
from pydantic import BaseModel, Field


class EventType(StrEnum):
  LOAN_CREATED = "LoanCreated"
  LOAN_RETURNED = "LoanReturned"


class LoanPayload(BaseModel):
  loan_id: str = Field(..., min_length=1)
  book_id: str = Field(..., min_length=1)
  borrower_name: str = Field(..., min_length=1)
  owner_id: str | None = None
  loan_date: str | None = None
  due_date: str | None = None


class LoanNotificationEvent(BaseModel):
  event_id: str
  event_type: EventType
  payload: LoanPayload