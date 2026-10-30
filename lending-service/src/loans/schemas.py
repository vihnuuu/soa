from pydantic import BaseModel, Field


class LoanRequest(BaseModel):
    book_id: str = Field(..., min_length=1)
    borrower_name: str = Field(..., min_length=1)
    owner_id: str = Field(..., min_length=1)


class LoanResponse(BaseModel):
    loan_id: str
    book_id: str
    borrower_name: str
    owner_id: str
    status: str


class LoanActionResponse(BaseModel):
    message: str
    loan_id: str