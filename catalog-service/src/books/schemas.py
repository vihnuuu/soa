from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from shared.security import clean_text


class BookBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    author: str = Field(..., min_length=1, max_length=255)
    owner_id: UUID
    is_available: bool = True


class BookCreate(BookBase):
    model_config = ConfigDict(extra="forbid")

    id: UUID

    @field_validator("title", "author")
    @classmethod
    def _guard_text(cls, v: str, info) -> str:
        return clean_text(v, field=info.field_name)


class BookResponse(BookBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)
