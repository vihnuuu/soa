
import pytest
from fastapi import HTTPException

from shared.security.principal import (
    Principal,
    resolve_owner,
    require_owner,
)


OWNER_A = "550e8400-e29b-41d4-a716-446655440000"
OWNER_B = "550e8400-e29b-41d4-a716-446655440001"


def make_user():
    return Principal(
        subject=OWNER_A,
        username="test_user",
        scopes=frozenset({"lending:read"}),
        is_trusted_service=False,
    )


def test_user_can_access_own_owner():
    principal = make_user()

    result = resolve_owner(principal, OWNER_A)

    assert result == OWNER_A


def test_user_cannot_access_other_owner():
    principal = make_user()

    with pytest.raises(HTTPException) as exc:
        resolve_owner(principal, OWNER_B)

    assert exc.value.status_code == 403


def test_owner_cannot_be_changed_by_request():
    principal = make_user()

    result = resolve_owner(principal, None)

    assert result == OWNER_A


def test_invalid_owner_uuid_rejected():
    principal = Principal(
        subject="invalid-uuid",
        username="test_user",
    )

    with pytest.raises(HTTPException) as exc:
        require_owner(principal, None)

    assert exc.value.status_code == 422


def test_trusted_service_can_resolve_other_owner():
    principal = Principal(
        subject="service-account",
        username=None,
        is_trusted_service=True,
    )

    result = resolve_owner(principal, OWNER_B)

    assert result == OWNER_B
