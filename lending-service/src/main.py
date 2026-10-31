import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.config import settings
from src.core.database import Base, engine
from src.loans.models import Loan, OutboxMessage
from src.loans.router import router as loans_router
from src.loans.saga_compensator import run_saga_dlq_consumer
from src.loans.worker import process_outbox_messages


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    outbox_task = asyncio.create_task(process_outbox_messages())
    compensator_task = asyncio.create_task(run_saga_dlq_consumer())
    yield
    outbox_task.cancel()
    compensator_task.cancel()
    try:
        await asyncio.gather(
            outbox_task, compensator_task, return_exceptions=True
        )
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=settings.app_title,
    root_path=settings.root_path,
    lifespan=lifespan,
)

app.include_router(loans_router)