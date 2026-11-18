import json
import uuid

import pytest
import httpx

from agent2agent.common import build_app, make_card
from agent2agent.consumer_agent import SKILLS, ConsumerExecutor
from unittest.mock import AsyncMock


LOAN_ID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_a2a_http_without_auth():
    store = AsyncMock()
    store.by_loan.return_value = [{
        "event_id": "550e8400-e29b-41d4-a716-446655440001",
        "message": "Позика для Іван Петренко",
        "status": "CREATED",
        "created_at": "2026-11-18T10:00:00",
    }]

    consumer = ConsumerExecutor(store=store)
    consumer.llm = None

    card = make_card(
        name="Test Consumer",
        description="A2A security test",
        url="http://testserver/",
        skills=SKILLS,
    )

    app = build_app(card, consumer)

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/.well-known/agent-card.json"
        )

    print("HTTP status:", response.status_code)
    print("Response:", response.text[:500])

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_a2a_jsonrpc_without_token():
    store = AsyncMock()
    store.by_loan.return_value = [
        {
            "event_id": str(uuid.uuid4()),
            "message": "Позика створена для Іван Петренко",
            "status": "CREATED",
            "created_at": "2026-11-18T10:00:00",
        }
    ]

    consumer = ConsumerExecutor(store=store)
    consumer.llm = None

    card = make_card(
        name="Test Consumer",
        description="A2A security test",
        url="http://testserver/",
        skills=SKILLS,
    )

    app = build_app(card, consumer)

    skill_request = {
        "skill": "check_notification",
        "loan_id": LOAN_ID,
        "wait_seconds": 0,
    }

    rpc_request = {
        "jsonrpc": "2.0",
        "id": "test-1",
        "method": "SendMessage",
        "params": {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "ROLE_USER",
                "parts": [
                    {
                        "kind": "text",
                        "text": json.dumps(
                            skill_request,
                            ensure_ascii=False,
                        ),
                    }
                ],
            }
        },
    }

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/",
            json=rpc_request,
            headers={
                "A2A-Version": "1.0",
            },
        )

    print("HTTP status:", response.status_code)
    print("Response:", response.text[:2000])

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"

    store.by_loan.assert_not_awaited()
