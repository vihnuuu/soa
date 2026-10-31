from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class LoanRequest(BaseModel):
  book_id: str = Field(..., min_length=1)
  borrower_name: str = Field(..., min_length=1)
  owner_id: str = Field(..., min_length=1)


class LoanResponse(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  id: UUID
  book_id: UUID
  owner_id: UUID | None = None
  borrower_name: str
  status: str
  due_date: datetime | None = None
  created_at: datetime | None = None


class LoanActionResponse(BaseModel):
  message: str
  loan_id: str