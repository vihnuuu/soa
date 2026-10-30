from fastapi import Depends
from src.broker.publisher import EventPublisher, event_publisher
from src.clients.catalog_client import CatalogClient, catalog_client
from src.loans.repository import LoanRepository, loan_repository
from src.loans.service import LoanService


def get_loan_repository() -> LoanRepository:
    return loan_repository


def get_catalog_client() -> CatalogClient:
    return catalog_client


def get_event_publisher() -> EventPublisher:
    return event_publisher


def get_loan_service(
    repo: LoanRepository = Depends(get_loan_repository),
    client: CatalogClient = Depends(get_catalog_client),
    pub: EventPublisher = Depends(get_event_publisher),
) -> LoanService:
    return LoanService(repository=repo, catalog_client=client, publisher=pub)