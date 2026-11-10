from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import get_artifact_text, get_message_text
from a2a.types import Message, Part, Role, SendMessageRequest, TaskState

COMPLETED = "TASK_STATE_COMPLETED"


class A2ACallError(RuntimeError):
    pass


@dataclass
class AgentReply:
    agent: str
    state: str
    status_text: str = ""
    artifacts: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.state == COMPLETED


async def fetch_card(base_url: str):
    async with httpx.AsyncClient(timeout=10.0) as http:
        return await A2ACardResolver(http, base_url).get_agent_card()


async def call_agent(base_url: str, text: str, *, timeout: float = 60.0) -> AgentReply:
    try:
        card = await fetch_card(base_url)
    except Exception as exc:
        raise A2ACallError(f"agent at {base_url} is unreachable: {type(exc).__name__}") from None

    client = await create_client(card, client_config=ClientConfig(streaming=False))
    reply: AgentReply | None = None

    async def consume() -> None:
        nonlocal reply
        message = Message(role=Role.ROLE_USER, message_id=str(uuid.uuid4()), parts=[Part(text=text)])
        async for event in client.send_message(SendMessageRequest(message=message)):
            if event.HasField("task"):
                task = event.task
                status_text = get_message_text(task.status.message) if task.status.HasField("message") else ""
                reply = AgentReply(
                    card.name,
                    TaskState.Name(task.status.state),
                    status_text,
                    [get_artifact_text(a) for a in task.artifacts],
                )
            elif event.HasField("message"):
                reply = AgentReply(card.name, "MESSAGE", get_message_text(event.message))

    try:
        await asyncio.wait_for(consume(), timeout)
    except asyncio.TimeoutError:
        raise A2ACallError(f"agent {card.name} did not answer within {timeout}s") from None
    finally:
        await client.close()

    if reply is None:
        raise A2ACallError(f"agent {card.name} returned no response")
    return reply