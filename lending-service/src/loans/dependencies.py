from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.clients.catalog_client import CatalogClient, catalog_client
from src.core.database import get_db_session
from src.loans.repository import LoanRepository
from src.loans.service import LoanService


def get_loan_repository(
    session: AsyncSession = Depends(get_db_session),
) -> LoanRepository:
  return LoanRepository(session=session)


def get_catalog_client() -> CatalogClient:
  return catalog_client


def get_loan_service(
    repo: LoanRepository = Depends(get_loan_repository),
    client: CatalogClient = Depends(get_catalog_client),
) -> LoanService:
  return LoanService(repository=repo, catalog_client=client)