import asyncio
from datetime import datetime, timezone
import logging
import uuid
from sqlalchemy import select, update
from src.broker.publisher import event_publisher
from src.core.database import async_session_factory
from src.loans.exceptions import EventPublishError
from src.loans.models import Loan, LoanStatus, OutboxMessage, OutboxStatus

logger = logging.getLogger("outbox_worker")


async def process_outbox_messages() -> None:
    while True:
        try:
            async with async_session_factory() as session:
                query = (
                    select(
                        OutboxMessage.id,
                        OutboxMessage.event_type,
                        OutboxMessage.payload,
                        OutboxMessage.retry_count,
                    )
                    .where(OutboxMessage.status == OutboxStatus.NEW)
                    .order_by(OutboxMessage.created_at)
                    .limit(10)
                )
                result = await session.execute(query)
                records = result.all()

            for msg_id, event_type, payload, retry_count in records:
                event_data = {
                    "event_id": str(msg_id),
                    "event_type": event_type,
                    "payload": payload,
                }

                try:
                    res = event_publisher.publish(event_data)
                    if asyncio.iscoroutine(res):
                        await res

                    async with async_session_factory() as session:
                        await session.execute(
                            update(OutboxMessage)
                            .where(OutboxMessage.id == msg_id)
                            .values(
                                status=OutboxStatus.PROCESSED,
                                processed_at=datetime.now(timezone.utc),
                            )
                        )

                        if event_type == "LoanCreated":
                            target_loan_id = payload.get("loan_id")
                            if target_loan_id:
                                await session.execute(
                                    update(Loan)
                                    .where(
                                        Loan.id == uuid.UUID(target_loan_id),
                                        Loan.status == LoanStatus.PENDING,
                                    )
                                    .values(status=LoanStatus.ACTIVE)
                                )

                        await session.commit()
                except Exception as exc:
                    logger.error(f"Error publishing outbox event {msg_id}: {exc}")
                    new_retry = (retry_count or 0) + 1
                    new_status = (
                        OutboxStatus.FAILED if new_retry >= 3 else OutboxStatus.NEW
                    )

                    async with async_session_factory() as session:
                        await session.execute(
                            update(OutboxMessage)
                            .where(OutboxMessage.id == msg_id)
                            .values(
                                retry_count=new_retry,
                                status=new_status,
                            )
                        )
                        await session.commit()

        except asyncio.CancelledError:
            break
        except Exception as err:
            logger.error(f"Error in outbox worker loop: {err}")

        await asyncio.sleep(2)