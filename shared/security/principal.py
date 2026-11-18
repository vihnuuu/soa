from dataclasses import dataclass, field
from uuid import UUID

from fastapi import HTTPException, status


@dataclass(frozen=True)
class Principal:
    subject: str
    username: str | None
    scopes: frozenset[str] = field(default_factory=frozenset)
    client_id: str | None = None
    is_trusted_service: bool = False


def resolve_owner(principal: Principal, requested: str | UUID | None) -> str | None:
    if principal.is_trusted_service:
        return str(requested) if requested else None
    if requested is not None and str(requested).lower() != principal.subject.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="owner_id does not match the authenticated user",
        )
    return principal.subject


def require_owner(principal: Principal, requested: str | UUID | None) -> UUID:
    owner = resolve_owner(principal, requested)
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="owner_id is required",
        )
    try:
        return UUID(owner)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="owner_id must be a valid UUID",
        ) from None
