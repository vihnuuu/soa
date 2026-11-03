from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class BookBase(BaseModel):
    title: str = Field(..., min_length=1)
    author: str = Field(..., min_length=1)
    owner_id: UUID
    is_available: bool = True


class BookCreate(BookBase):
    id: UUID


class BookResponse(BookBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)