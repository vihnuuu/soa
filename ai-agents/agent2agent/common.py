from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from collections import deque
from typing import Any, Callable

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
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger("a2a")

MAX_INPUT_CHARS = 4000
MAX_REQUEST_BYTES = 64 * 1024
RATE_LIMIT = 60
RATE_WINDOW_SECONDS = 60.0

TokenVerifier = Callable[[str], Any]


class SkillRejected(Exception):
    pass


class A2AAuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        token_verifier: TokenVerifier | None = None,
        rate_limit: int = RATE_LIMIT,
        rate_window: float = RATE_WINDOW_SECONDS,
        max_request_bytes: int = MAX_REQUEST_BYTES,
    ) -> None:
        super().__init__(app)
        if rate_limit <= 0 or rate_window <= 0 or max_request_bytes <= 0:
            raise ValueError("A2A middleware limits must be positive")
        self.token_verifier = token_verifier
        self.rate_limit = rate_limit
        self.rate_window = rate_window
        self.max_request_bytes = max_request_bytes
        self._requests: dict[str, deque[float]] = {}
        self._rate_lock = asyncio.Lock()

    async def _check_rate_limit(self, subject: str) -> int | None:
        now = time.monotonic()
        async with self._rate_lock:
            for key, history in list(self._requests.items()):
                while history and now - history[0] >= self.rate_window:
                    history.popleft()
                if not history:
                    del self._requests[key]

            history = self._requests.setdefault(subject, deque())
            if len(history) >= self.rate_limit:
                remaining = self.rate_window - (now - history[0])
                return max(1, int(remaining) + 1)
            history.append(now)
        return None

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        if request.method != "POST":
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not token.strip():
            return JSONResponse(
                {"detail": "Authentication required"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        if self.token_verifier is None:
            logger.error("A2A token verifier is not configured")
            return JSONResponse(
                {"detail": "Authentication unavailable"}, status_code=503
            )

        try:
            claims = self.token_verifier(token.strip())
            if inspect.isawaitable(claims):
                claims = await claims
            if not isinstance(claims, dict) or not claims.get("sub"):
                raise ValueError("Invalid token claims")
        except HTTPException as exc:
            if exc.status_code == 503:
                return JSONResponse({"detail": "Authorization server is unavailable"}, status_code=503)
            return JSONResponse(
                {"detail": "Invalid or expired token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception:
            logger.warning("A2A token verification failed", exc_info=True)
            return JSONResponse(
                {"detail": "Invalid or expired token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        request.state.claims = claims

        retry_after = await self._check_rate_limit(str(claims["sub"]))
        if retry_after is not None:
            return JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
            if declared_length < 0:
                return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
            if declared_length > self.max_request_bytes:
                return JSONResponse({"detail": "Request too large"}, status_code=413)

        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > self.max_request_bytes:
                return JSONResponse({"detail": "Request too large"}, status_code=413)


        try:
            rpc = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"detail": "Invalid JSON-RPC body"}, status_code=400)
        if not isinstance(rpc, dict):
            return JSONResponse({"detail": "JSON-RPC object required"}, status_code=400)

        method = str(rpc.get("method", ""))
        required_scope = "loans:read"
        if method in ("message/send", "message/stream", "SendMessage", "SendStreamingMessage"):
            required_scope = "loans:write"
            params = rpc.get("params")
            message = params.get("message") if isinstance(params, dict) else None
            parts = message.get("parts") if isinstance(message, dict) else None
            if isinstance(parts, list) and len(parts) == 1 and isinstance(parts[0], dict):
                part = parts[0]
                content = part.get("text")
                if isinstance(content, str):
                    try:
                        skill_request = json.loads(content)
                    except ValueError:
                        skill_request = None
                    if isinstance(skill_request, dict) and skill_request.get("skill") == "check_notification":
                        required_scope = "loans:read"
        granted = set(str(claims.get("scope", "")).split())
        if required_scope not in granted:
            return JSONResponse(
                {"detail": f"Insufficient scope. Required: {required_scope}"},
                status_code=403,
                headers={"WWW-Authenticate": f'Bearer error="insufficient_scope", scope="{required_scope}"'},
            )

        request._body = bytes(body)
        return await call_next(request)


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


def make_card(
    *, name: str, description: str, url: str, skills: list[AgentSkill]
) -> AgentCard:
    return AgentCard(
        name=name,
        description=description,
        version="1.0.0",
        supported_interfaces=[
            AgentInterface(protocol_binding="JSONRPC", protocol_version="1.0", url=url)
        ],
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=skills,
    )


def build_app(
    card: AgentCard,
    executor: AgentExecutor,
    *,
    token_verifier: TokenVerifier | None = None,
) -> Starlette:
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    app = Starlette(
        routes=[
            *create_agent_card_routes(card),
            *create_jsonrpc_routes(handler, rpc_url="/"),
        ]
    )
    app.add_middleware(A2AAuthMiddleware, token_verifier=token_verifier)
    return app


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


__all__ = [
    "A2AAuthMiddleware",
    "SkillExecutor",
    "SkillRejected",
    "build_app",
    "make_card",
    "parse_json_request",
]
