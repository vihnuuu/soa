from pydantic import BaseModel, Field


class BookBase(BaseModel):
    title: str = Field(..., min_length=1)
    author: str = Field(..., min_length=1)
    owner_id: str = Field(..., min_length=1)


class BookCreate(BookBase):
    id: str = Field(..., min_length=1)


class BookResponse(BookBase):
    id: str