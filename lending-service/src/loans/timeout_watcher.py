import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import update
from src.clients.catalog_client import catalog_client
from src.core.config import settings
from src.core.database import async_session_factory
from src.loans.models import Loan, LoanStatus

logger = logging.getLogger("saga_timeout")


async def cancel_timed_out_pending_loans() -> int:
    threshold = datetime.now(timezone.utc) - timedelta(
        seconds=settings.saga_timeout_seconds
    )
    async with async_session_factory() as session:
        async with session.begin():
            result = await session.execute(
                update(Loan)
                .where(
                    Loan.status == LoanStatus.PENDING,
                    Loan.created_at < threshold,
                )
                .values(status=LoanStatus.CANCELLED)
                .returning(Loan.book_id)
            )
            book_ids = result.scalars().all()

    for book_id in book_ids:
        try:
            await catalog_client.update_book_availability(str(book_id), True)
        except Exception as exc:
            logger.warning(
                f"[SAGA TIMEOUT] Не вдалося повернути доступність книги {book_id}: "
                f"{type(exc).__name__}"
            )
    return len(book_ids)


async def run_saga_timeout_watcher() -> None:
    while True:
        try:
            count = await cancel_timed_out_pending_loans()
            if count:
                logger.warning(
                    f"[SAGA TIMEOUT] Скасовано позик за таймаутом: {count}"
                )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(f"[SAGA TIMEOUT] Помилка: {exc}")
        await asyncio.sleep(10)