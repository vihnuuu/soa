from fastapi import FastAPI
from src.core.config import settings
from src.loans.router import router as loans_router

app = FastAPI(
    title=settings.app_title,
    root_path=settings.root_path,
)

app.include_router(loans_router)