from enum import StrEnum
from pydantic import BaseModel, Field


class EventType(StrEnum):
    LOAN_CREATED = "LoanCreated"
    LOAN_RETURNED = "LoanReturned"


class LoanNotificationEvent(BaseModel):
    event_type: EventType
    loan_id: str = Field(..., min_length=1)
    book_id: str = Field(..., min_length=1)
    borrower_name: str = Field(..., min_length=1)
    owner_id: str = Field(..., min_length=1)