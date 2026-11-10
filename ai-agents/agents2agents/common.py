from __future__ import annotations

import json
import logging
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Part,
    Task,
    TaskState,
    TaskStatus,
)
from starlette.applications import Starlette

logger = logging.getLogger("a2a")

MAX_INPUT_CHARS = 4000


class SkillRejected(Exception):
    pass


def parse_json_request(text: str) -> dict | None:
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        raise SkillRejected("Некоректний JSON у запиті") from None
    if not isinstance(obj, dict):
        raise SkillRejected("Очікується JSON-об'єкт")
    return obj


def make_card(*, name: str, description: str, url: str, skills: list[AgentSkill]) -> AgentCard:
    return AgentCard(
        name=name,
        description=description,
        version="1.0.0",
        supported_interfaces=[AgentInterface(protocol_binding="JSONRPC", protocol_version="1.0", url=url)],
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=skills,
    )


def build_app(card: AgentCard, executor: AgentExecutor) -> Starlette:
    handler = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore(), agent_card=card)
    return Starlette(
        routes=[
            *create_agent_card_routes(card),
            *create_jsonrpc_routes(handler, rpc_url="/"),
        ]
    )


class SkillExecutor(AgentExecutor):
    working_text = "Працюю над запитом..."
    artifact_name = "result"

    async def handle(self, text: str) -> str:
        raise NotImplementedError

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        if context.current_task is None:
            await event_queue.enqueue_event(
                Task(
                    id=context.task_id,
                    context_id=context.context_id,
                    status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                    history=[context.message],
                )
            )

        def say(text: str) -> Any:
            return updater.new_agent_message([Part(text=text)])

        text = context.get_user_input()
        if len(text) > MAX_INPUT_CHARS:
            await updater.reject(say(f"Запит завеликий (>{MAX_INPUT_CHARS} символів)"))
            return

        await updater.start_work(say(self.working_text))
        try:
            result = await self.handle(text)
        except SkillRejected as exc:
            await updater.reject(say(str(exc)))
            return
        except Exception:
            logger.exception("skill crashed")
            fail = getattr(updater, "failed", None) or updater.reject
            await fail(say("Внутрішня помилка агента"))
            return

        await updater.add_artifact([Part(text=result)], name=self.artifact_name)
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await TaskUpdater(event_queue, context.task_id, context.context_id).cancel()


__all__ = ["SkillExecutor", "SkillRejected", "build_app", "make_card", "parse_json_request"]