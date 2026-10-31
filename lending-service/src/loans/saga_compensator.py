import asyncio
import json
import logging
import uuid
import aio_pika
from sqlalchemy import update
from src.core.config import settings
from src.core.database import async_session_factory
from src.loans.models import Loan, LoanStatus

logger = logging.getLogger("saga_compensator")


async def compensate_loan(loan_id: str) -> None:
    async with async_session_factory() as session:
        async with session.begin():
            stmt = (
                update(Loan)
                .where(
                    Loan.id == uuid.UUID(loan_id),
                    Loan.status.in_([LoanStatus.PENDING, LoanStatus.ACTIVE]),
                )
                .values(status=LoanStatus.CANCELLED)
            )
            res = await session.execute(stmt)
            if res.rowcount > 0:
                logger.warning(
                    f"[SAGA COMPENSATION] Позику {loan_id} успішно СКАСОВАНО (відкат через DLQ)"
                )
            else:
                logger.info(
                    f"[SAGA COMPENSATION] Позика {loan_id} не в статусі PENDING або не знайдена"
                )


async def run_saga_dlq_consumer() -> None:
    while True:
        try:
            connection = await aio_pika.connect_robust(
                f"amqp://guest:guest@{settings.rabbit_host}:5672/"
            )
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=1)

                queue = await channel.declare_queue(
                    settings.rabbit_dlq,
                    durable=True,
                )

                logger.info(
                    f"[SAGA Compensator] Слухає DLQ-чергу: {settings.rabbit_dlq}"
                )

                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        async with message.process():
                            try:
                                data = json.loads(message.body.decode("utf-8"))
                                loan_id = data.get("payload", {}).get("loan_id")
                                if loan_id:
                                    logger.warning(
                                        f"[SAGA Compensator] Отримано повідомлення з DLQ для позики {loan_id}"
                                    )
                                    await compensate_loan(loan_id)
                            except Exception as err:
                                logger.error(
                                    f"[SAGA Compensator] Помилка обробки повідомлення з DLQ: {err}"
                                )

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(f"[SAGA Compensator] Втрата з'єднання з RabbitMQ: {exc}. Спроба через 3 сек...")
            await asyncio.sleep(3)