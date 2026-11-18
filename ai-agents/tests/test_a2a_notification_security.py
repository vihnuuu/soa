
import json
from unittest.mock import AsyncMock

import pytest

from agent2agent.consumer_agent import ConsumerExecutor


LOAN_ID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_notification_read_by_loan_id():
    store = AsyncMock()
    store.by_loan.return_value = [
        {
            "event_id": "550e8400-e29b-41d4-a716-446655440001",
            "message": "Позика створена для Іван Петренко",
            "status": "CREATED",
            "created_at": "2026-11-18T10:00:00",
        }
    ]

    consumer = ConsumerExecutor(store=store)
    consumer.llm = None

    request = {
        "skill": "check_notification",
        "loan_id": LOAN_ID,
        "wait_seconds": 0,
    }

    response = await consumer.handle(
        json.dumps(request)
    )

    result = json.loads(response)

    assert result["notification_received"] is True
    assert "Іван Петренко" in json.dumps(
        result, ensure_ascii=False
    )

    store.by_loan.assert_awaited_once_with(LOAN_ID)
