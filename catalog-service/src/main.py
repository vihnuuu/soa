import socket
from fastapi import FastAPI
from src.books.router import router as books_router

app = FastAPI(
    title="Catalog Service",
    root_path="/api/catalog",
)

app.include_router(books_router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "instance": socket.gethostname()}