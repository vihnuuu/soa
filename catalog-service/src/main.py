import socket
from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.config import settings
from src.core.database import engine, Base
from src.books.router import router as books_router
from src.books.models import Book  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Catalog Service",
    root_path="/api/catalog",
    lifespan=lifespan,
)

app.include_router(books_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "instance": socket.gethostname()}