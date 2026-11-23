import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from src.broker.publisher import event_publisher
from src.core.database import async_session_factory
from src.loans.models import Loan, LoanStatus, OutboxMessage, OutboxStatus
from src.loans.metrics import OUTBOX_PUBLISH_SECONDS, OUTBOX_PUBLISHED
from shared.observability import extract_context, get_tracer, inject_trace_context

logger = logging.getLogger("outbox_worker")
tracer = get_tracer("outbox_worker")

MAX_RETRIES = 5


async def _process_one() -> str:
    async with async_session_factory() as session:
        async with session.begin():
            msg = (
                await session.execute(
                    select(OutboxMessage)
                    .where(OutboxMessage.status == OutboxStatus.NEW)
                    .order_by(OutboxMessage.created_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).scalar_one_or_none()

            if msg is None:
                return "empty"

            if msg.event_type == "LoanCreated":
                loan_status = await session.scalar(
                    select(Loan.status).where(
                        Loan.id == uuid.UUID(msg.payload["loan_id"])
                    )
                )
                if loan_status != LoanStatus.PENDING:
                    logger.warning(
                        f"Outbox {msg.id}: позика не PENDING ({loan_status}), публікацію пропущено"
                    )
                    msg.status = OutboxStatus.PROCESSED
                    msg.processed_at = datetime.now(timezone.utc)
                    OUTBOX_PUBLISHED.labels("skipped").inc()
                    return "ok"

            payload = dict(msg.payload)
            trace_ctx = payload.pop("_trace", {}) or {}
            parent = extract_context(trace_ctx)

            with tracer.start_as_current_span(
                "outbox.publish", context=parent, attributes={"messaging.destination": "loan_notifications"}
            ):
                event_data = {
                    "event_id": str(msg.id),
                    "event_type": msg.event_type,
                    "payload": payload,
                    "trace_context": inject_trace_context(),
                }
                started = time.perf_counter()
                try:
                    await event_publisher.publish(event_data)
                except Exception as exc:
                    OUTBOX_PUBLISH_SECONDS.observe(time.perf_counter() - started)
                    msg.retry_count = (msg.retry_count or 0) + 1
                    if msg.retry_count >= MAX_RETRIES:
                        msg.status = OutboxStatus.FAILED
                        OUTBOX_PUBLISHED.labels("failed").inc()
                        logger.error(
                            "outbox_failed",
                            extra={"outbox_id": str(msg.id), "retries": msg.retry_count, "error": str(exc)},
                        )
                    else:
                        OUTBOX_PUBLISHED.labels("error").inc()
                        logger.error(
                            "outbox_publish_error",
                            extra={"outbox_id": str(msg.id), "attempt": msg.retry_count, "error": str(exc)},
                        )
                    return "error"

                OUTBOX_PUBLISH_SECONDS.observe(time.perf_counter() - started)
                OUTBOX_PUBLISHED.labels("ok").inc()
                msg.status = OutboxStatus.PROCESSED
                msg.processed_at = datetime.now(timezone.utc)
                logger.info(
                    "outbox_published",
                    extra={"outbox_id": str(msg.id), "event_type": msg.event_type},
                )
                return "ok"


async def process_outbox_messages() -> None:
    while True:
        result = "empty"
        try:
            result = await _process_one()
        except asyncio.CancelledError:
            break
        except Exception as err:
            logger.error(f"Error in outbox worker loop: {err}")
            result = "error"

        if result != "ok":
            await asyncio.sleep(2)