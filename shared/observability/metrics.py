import asyncio
import logging
import os
import random
import time
import uuid

from fastapi import Response
from opentelemetry import trace
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import JSONResponse

from shared.observability.logging import request_id_var

logger = logging.getLogger("http")

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Кількість HTTP-запитів",
    ["service", "method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Тривалість обробки HTTP-запиту",
    ["service", "method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
HTTP_IN_PROGRESS = Gauge(
    "http_requests_in_progress", "Запити в обробці", ["service"]
)

_SKIP = ("/health", "/metrics")


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class ObservabilityMiddleware:

    def __init__(self, app, service: str) -> None:
        self.app = app
        self.service = service

        self.fault_latency = float(os.getenv("FAULT_LATENCY_MS", "0")) / 1000.0
        self.fault_error_rate = float(os.getenv("FAULT_ERROR_RATE", "0"))

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        if path.endswith(_SKIP):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        request_id = headers.get(b"x-request-id", b"").decode() or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        method = scope["method"]
        status_holder = {"code": 500}
        start = time.perf_counter()
        HTTP_IN_PROGRESS.labels(self.service).inc()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
                extra = [(b"x-request-id", request_id.encode())]
                ctx = trace.get_current_span().get_span_context()
                if ctx.is_valid:
                    extra.append((b"x-trace-id", format(ctx.trace_id, "032x").encode()))
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        try:
            if self.fault_latency:
                await asyncio.sleep(self.fault_latency)
            if self.fault_error_rate and random.random() < self.fault_error_rate:
                await JSONResponse({"detail": "injected fault"}, status_code=500)(
                    scope, receive, send_wrapper
                )
            else:
                await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception("unhandled_exception", extra={"method": method, "path": path})
            raise
        finally:
            elapsed = time.perf_counter() - start
            route = scope.get("route")
            template = getattr(route, "path", None) or "unmatched"
            code = status_holder["code"]
            HTTP_REQUESTS.labels(self.service, method, template, str(code)).inc()
            HTTP_LATENCY.labels(self.service, method, template).observe(elapsed)
            HTTP_IN_PROGRESS.labels(self.service).dec()
            logger.log(
                logging.ERROR if code >= 500 else logging.INFO,
                "http_request",
                extra={
                    "method": method,
                    "path": path,
                    "route": template,
                    "status": code,
                    "duration_ms": round(elapsed * 1000, 2),
                },
            )
            request_id_var.reset(token)
