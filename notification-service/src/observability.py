import contextvars
import json
import logging
import os
import sys
from datetime import datetime, timezone

from opentelemetry import propagate, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Gauge, Histogram, start_http_server

SERVICE = "notification-service"

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

EVENTS = Counter(
    "notification_events_total",
    "Оброблені події з RabbitMQ",
    ["event_type", "result"],
)
PROCESSING_SECONDS = Histogram(
    "notification_processing_seconds",
    "Тривалість обробки події (від отримання до ack/nack)",
    ["event_type"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
REPLIES = Counter("notification_replies_total", "Reply-повідомлення SAGA", ["result"])
CONSUMER_UP = Gauge("notification_consumer_connected", "1, якщо консьюмер підключений до RabbitMQ")

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "service": SERVICE,
            "logger": record.name,
            "message": record.getMessage(),
        }
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            payload["trace_id"] = format(ctx.trace_id, "032x")
            payload["span_id"] = format(ctx.span_id, "016x")
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_observability(metrics_port: int | None = None) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for name in ("pika", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)

    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE}))
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    port = metrics_port or int(os.getenv("METRICS_PORT", "9102"))
    start_http_server(port)
    logging.getLogger("observability").info("metrics_server_started", extra={"port": port})


def get_tracer():
    return trace.get_tracer(SERVICE)


def extract_context(carrier: dict | None):
    return propagate.extract(carrier or {})


def inject_trace_context() -> dict[str, str]:
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier
