from shared.observability.logging import (
    JsonFormatter,
    configure_logging,
    request_id_var,
)
from shared.observability.metrics import (
    HTTP_LATENCY,
    HTTP_REQUESTS,
    ObservabilityMiddleware,
    metrics_response,
)
from shared.observability.tracing import (
    extract_context,
    get_tracer,
    inject_trace_context,
    setup_tracing,
)

__all__ = [
    "JsonFormatter",
    "configure_logging",
    "request_id_var",
    "HTTP_LATENCY",
    "HTTP_REQUESTS",
    "ObservabilityMiddleware",
    "metrics_response",
    "extract_context",
    "get_tracer",
    "inject_trace_context",
    "setup_tracing",
    "setup_observability",
]


def setup_observability(app, service_name: str, engine=None) -> None:
    from fastapi import Response

    configure_logging(service_name)
    app.add_middleware(ObservabilityMiddleware, service=service_name)

    @app.get("/metrics", include_in_schema=False)
    async def _metrics() -> Response:
        return metrics_response()

    setup_tracing(service_name, app=app, engine=engine)
