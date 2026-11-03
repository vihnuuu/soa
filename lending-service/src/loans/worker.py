import asyncio
import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from src.broker.publisher import event_publisher
from src.core.database import async_session_factory
from src.loans.models import Loan, LoanStatus, OutboxMessage, OutboxStatus

logger = logging.getLogger("outbox_worker")

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
                    return "ok"

            event_data = {
                "event_id": str(msg.id),
                "event_type": msg.event_type,
                "payload": msg.payload,
            }
            try:
                await event_publisher.publish(event_data)
            except Exception as exc:
                msg.retry_count = (msg.retry_count or 0) + 1
                if msg.retry_count >= MAX_RETRIES:
                    msg.status = OutboxStatus.FAILED
                    logger.error(
                        f"Outbox {msg.id} -> FAILED після {msg.retry_count} спроб: {exc}. "
                        f"Позику скасує timeout watcher."
                    )
                else:
                    logger.error(
                        f"Помилка публікації outbox {msg.id} "
                        f"(спроба {msg.retry_count}/{MAX_RETRIES}): {exc}"
                    )
                return "error"

            msg.status = OutboxStatus.PROCESSED
            msg.processed_at = datetime.now(timezone.utc)
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