import asyncio
import json
import logging
import uuid
import aio_pika
from sqlalchemy import update
from src.core.config import settings
from src.core.database import async_session_factory
from src.loans.models import Loan, LoanStatus

logger = logging.getLogger("saga_confirmer")


async def confirm_loan(loan_id: str) -> None:
    async with async_session_factory() as session:
        async with session.begin():
            res = await session.execute(
                update(Loan)
                .where(
                    Loan.id == uuid.UUID(loan_id),
                    Loan.status == LoanStatus.PENDING,
                )
                .values(status=LoanStatus.ACTIVE)
            )
            if res.rowcount > 0:
                logger.info(f"[SAGA CONFIRM] Позику {loan_id} підтверджено (ACTIVE)")
            else:
                logger.warning(
                    f"[SAGA CONFIRM] Позика {loan_id} вже не PENDING "
                    f"(скасована за таймаутом/DLQ або вже підтверджена) — reply проігноровано"
                )


async def run_saga_confirmer() -> None:
    while True:
        try:
            connection = await aio_pika.connect_robust(
                f"amqp://guest:guest@{settings.rabbit_host}:5672/"
            )
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=1)
                queue = await channel.declare_queue(
                    settings.rabbit_reply_queue, durable=True
                )
                logger.info(
                    f"[SAGA Confirmer] Слухає reply-чергу: {settings.rabbit_reply_queue}"
                )

                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        try:
                            data = json.loads(message.body.decode("utf-8"))
                            loan_id = data.get("payload", {}).get("loan_id")
                            event_type = data.get("event_type")
                        except Exception as parse_err:
                            logger.error(f"[SAGA Confirmer] Некоректне reply: {parse_err}")
                            await message.ack()
                            continue

                        if event_type != "LoanConfirmed" or not loan_id:
                            await message.ack()
                            continue

                        try:
                            await confirm_loan(loan_id)
                            await message.ack()
                        except Exception as err:
                            logger.error(f"[SAGA Confirmer] Помилка підтвердження: {err}")
                            await message.nack(requeue=True)
                            await asyncio.sleep(1)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(
                f"[SAGA Confirmer] Втрата з'єднання з RabbitMQ: {exc}. Спроба через 3 сек..."
            )
            await asyncio.sleep(3)