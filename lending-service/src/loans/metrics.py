import asyncio
import logging
from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import func, select

from src.core.database import async_session_factory
from src.loans.models import Loan, LoanStatus, OutboxMessage, OutboxStatus

logger = logging.getLogger("metrics_collector")

LOANS_CREATED = Counter("loans_created_total", "Позики, прийняті в обробку (SAGA запущено)")
LOANS_RETURNED = Counter("loans_returned_total", "Повернені позики")
SAGA_CONFIRMED = Counter("saga_confirmed_total", "SAGA завершено підтвердженням (PENDING → ACTIVE)")
SAGA_COMPENSATIONS = Counter(
    "saga_compensations_total", "Компенсації SAGA (скасування позики)", ["reason"]
)
OUTBOX_PUBLISHED = Counter(
    "outbox_publish_total", "Спроби публікації outbox-повідомлень", ["result"]
)
OUTBOX_PUBLISH_SECONDS = Histogram(
    "outbox_publish_duration_seconds",
    "Тривалість публікації повідомлення в RabbitMQ",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
SAGA_CONFIRMATION_SECONDS = Histogram(
    "saga_confirmation_seconds",
    "Час від створення позики до підтвердження (end-to-end SAGA)",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60),
)

OUTBOX_OLDEST_NEW_AGE = Gauge(
    "outbox_oldest_new_age_seconds",
    "Вік найстарішого outbox-повідомлення зі статусом NEW (відставання доставки)",
)
OUTBOX_MESSAGES = Gauge("outbox_messages", "Outbox-повідомлення за статусом", ["status"])
LOANS_BY_STATUS = Gauge("loans_by_status", "Позики за статусом", ["status"])
SAGA_PENDING_OLDEST_AGE = Gauge(
    "saga_pending_oldest_age_seconds", "Вік найстарішої позики в статусі PENDING"
)


def _age(ts: datetime | None) -> float:
    if ts is None:
        return 0.0
    return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())


async def collect_once() -> None:
    async with async_session_factory() as session:
        outbox = dict(
            (
                await session.execute(
                    select(OutboxMessage.status, func.count()).group_by(OutboxMessage.status)
                )
            ).all()
        )
        for st in OutboxStatus:
            OUTBOX_MESSAGES.labels(st.value).set(outbox.get(st, 0))

        oldest_new = await session.scalar(
            select(func.min(OutboxMessage.created_at)).where(
                OutboxMessage.status == OutboxStatus.NEW
            )
        )
        OUTBOX_OLDEST_NEW_AGE.set(_age(oldest_new))

        loans = dict(
            (await session.execute(select(Loan.status, func.count()).group_by(Loan.status))).all()
        )
        for st in LoanStatus:
            LOANS_BY_STATUS.labels(st.value).set(loans.get(st, 0))

        oldest_pending = await session.scalar(
            select(func.min(Loan.created_at)).where(Loan.status == LoanStatus.PENDING)
        )
        SAGA_PENDING_OLDEST_AGE.set(_age(oldest_pending))


async def run_metrics_collector(interval: float = 5.0) -> None:
    while True:
        try:
            await collect_once()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("metrics_collect_failed", extra={"error": str(exc)})
        await asyncio.sleep(interval)
