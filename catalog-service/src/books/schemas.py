from uuid import UUID
from pydantic import BaseModel, Field


class BookBase(BaseModel):
    title: str = Field(..., min_length=1)
    author: str = Field(..., min_length=1)
    owner_id: UUID


class BookCreate(BookBase):
    id: UUID


class BookResponse(BookBase):
    id: UUID