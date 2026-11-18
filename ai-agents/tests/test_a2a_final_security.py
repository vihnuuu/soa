import json
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from agent2agent.common import build_app, make_card
from agent2agent.consumer_agent import ConsumerExecutor, SKILLS


LOAN_ID = "550e8400-e29b-41d4-a716-446655440000"


def rpc(skill):
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "SendMessage",
        "params": {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "ROLE_USER",
                "parts": [
                    {
                        "kind": "text",
                        "text": json.dumps(skill),
                    }
                ],
            }
        },
    }


def app_for(scope, *, unavailable=False):
    store = AsyncMock()
    store.by_loan.return_value = []

    executor = ConsumerExecutor(store=store)
    executor.llm = None

    card = make_card(
        name="Security test",
        description="Local A2A test",
        url="http://testserver/",
        skills=SKILLS,
    )

    def verify(token):
        if unavailable:
            raise HTTPException(
                status_code=503,
                detail="JWKS unavailable",
            )

        if token != "test-token":
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
            )

        return {
            "sub": "security-test-user",
            "scope": scope,
        }

    return build_app(
        card,
        executor,
        token_verifier=verify,
    ), store


@pytest.mark.asyncio
async def test_read_only_token_can_read():
    app, store = app_for("loans:read")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/",
            json=rpc({
                "skill": "check_notification",
                "loan_id": LOAN_ID,
            }),
            headers={
                "Authorization": "Bearer test-token",
                "A2A-Version": "1.0",
            },
        )

    assert response.status_code == 200, response.text
    store.by_loan.assert_awaited()


@pytest.mark.asyncio
async def test_read_only_token_cannot_write():
    app, store = app_for("loans:read")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/",
            json=rpc({
                "skill": "lend_and_confirm",
                "book_id": LOAN_ID,
                "borrower_name": "Test",
            }),
            headers={
                "Authorization": "Bearer test-token",
                "A2A-Version": "1.0",
            },
        )

    assert response.status_code == 403, response.text
    store.by_loan.assert_not_awaited()


@pytest.mark.asyncio
async def test_rate_limit_after_60_requests():
    app, _ = app_for("loans:read")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        for i in range(60):
            response = await client.post(
                "/",
                json=rpc({
                    "skill": "check_notification",
                    "loan_id": LOAN_ID,
                }),
                headers={
                    "Authorization": "Bearer test-token",
                    "A2A-Version": "1.0",
                },
            )

            assert response.status_code == 200, (
                f"Attempt {i + 1}: "
                f"{response.status_code} {response.text}"
            )

        response = await client.post(
            "/",
            json=rpc({
                "skill": "check_notification",
                "loan_id": LOAN_ID,
            }),
            headers={
                "Authorization": "Bearer test-token",
                "A2A-Version": "1.0",
            },
        )

    assert response.status_code == 429, response.text
    assert int(response.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_jwks_outage_returns_503():
    app, _ = app_for("loans:read", unavailable=True)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/",
            json=rpc({
                "skill": "check_notification",
                "loan_id": LOAN_ID,
            }),
            headers={
                "Authorization": "Bearer test-token",
                "A2A-Version": "1.0",
            },
        )

    assert response.status_code == 503, response.text
