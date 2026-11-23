import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from shared.observability import (
    extract_context,
    inject_trace_context,
    get_tracer,
    setup_observability,
)


@pytest.fixture(scope="module")
def client():
    app = FastAPI()

    @app.get("/items/{item_id}")
    async def item(item_id: int):
        logging.getLogger("demo").info("handling item", extra={"item_id": item_id})
        return {"id": item_id}

    @app.get("/boom")
    async def boom():
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="down")

    setup_observability(app, "test-svc")
    return TestClient(app)


def _sample(name, **labels):
    return REGISTRY.get_sample_value(name, labels)


def test_metrics_use_route_template_and_count_errors(client):
    client.get("/items/1")
    client.get("/items/2")
    client.get("/boom")
    assert _sample(
        "http_requests_total",
        service="test-svc", method="GET", path="/items/{item_id}", status="200",
    ) == 2
    assert _sample(
        "http_requests_total",
        service="test-svc", method="GET", path="/boom", status="503",
    ) == 1
    body = client.get("/metrics").text
    assert "http_request_duration_seconds_bucket" in body
    assert "process_cpu_seconds_total" in body


def test_response_carries_correlation_headers(client):
    r = client.get("/items/5", headers={"X-Request-ID": "req-123"})
    assert r.headers["x-request-id"] == "req-123"
    assert len(r.headers["x-trace-id"]) == 32


def test_logs_are_json_with_trace_id(client):
    import io

    from shared.observability import JsonFormatter

    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter("test-svc"))
    logging.getLogger().addHandler(handler)
    try:
        r = client.get("/items/7", headers={"X-Request-ID": "req-777"})
    finally:
        logging.getLogger().removeHandler(handler)
    lines = [json.loads(l) for l in buf.getvalue().splitlines() if l.startswith("{")]
    demo = next(l for l in lines if l["message"] == "handling item")
    access = next(l for l in lines if l["message"] == "http_request")
    assert demo["trace_id"] == r.headers["x-trace-id"] == access["trace_id"]
    assert demo["request_id"] == "req-777"
    assert demo["item_id"] == 7
    assert access["status"] == 200 and access["service"] == "test-svc"


def test_trace_context_roundtrip_through_message_headers(client):
    tracer = get_tracer("test")
    with tracer.start_as_current_span("producer") as span:
        carrier = inject_trace_context()
        trace_id = span.get_span_context().trace_id
    assert "traceparent" in carrier
    with tracer.start_as_current_span("consumer", context=extract_context(carrier)) as child:
        assert child.get_span_context().trace_id == trace_id
