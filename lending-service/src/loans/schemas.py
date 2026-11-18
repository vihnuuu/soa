from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from shared.security import clean_text


class LoanRequest(BaseModel):
  model_config = ConfigDict(extra="forbid")

  book_id: UUID
  borrower_name: str = Field(..., min_length=1, max_length=255)
  owner_id: UUID

  @field_validator("borrower_name")
  @classmethod
  def _guard_text(cls, v: str) -> str:
    return clean_text(v, field="borrower_name")


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