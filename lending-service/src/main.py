import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.config import settings
from src.core.database import Base, engine
from src.loans.models import Loan, OutboxMessage
from src.loans.router import router as loans_router
from src.loans.saga_compensator import run_saga_dlq_consumer
from src.loans.timeout_watcher import run_saga_timeout_watcher
from src.loans.worker import process_outbox_messages


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tasks = [
        asyncio.create_task(process_outbox_messages()),
        asyncio.create_task(run_saga_dlq_consumer()),
        asyncio.create_task(run_saga_timeout_watcher()),
    ]
    yield
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(
    title=settings.app_title,
    root_path=settings.root_path,
    lifespan=lifespan,
)

app.include_router(loans_router)