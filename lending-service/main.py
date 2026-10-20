import asyncio
import os
import json
import httpx
import pika

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Lending Service",
    root_path="/api/lending",
)

CATALOG_SERVICE_URL = os.getenv(
    "CATALOG_SERVICE_URL",
    "http://catalog-service:8001"
)
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")

loans_db = {}
active_loans_books = set()


class LoanRequest(BaseModel):
    book_id: str
    borrower_name: str
    owner_id: str


def publish_event(event_data: dict):
    connection = None

    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                connection_attempts=3,
                retry_delay=1,
                socket_timeout=3,
                blocked_connection_timeout=5,
            )
        )

        channel = connection.channel()
        channel.queue_declare(
            queue="loan_notifications",
            durable=True
        )

        channel.basic_publish(
            exchange="",
            routing_key="loan_notifications",
            body=json.dumps(event_data, ensure_ascii=False),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
            mandatory=True,
        )

    except (pika.exceptions.AMQPError, OSError, ValueError) as exc:
        raise RuntimeError("Не вдалося опублікувати подію в RabbitMQ") from exc

    finally:
        if connection is not None and connection.is_open:
            connection.close()


@app.post("/loans/{loan_id}/return")
async def return_loan(loan_id: str):
    record = loans_db.get(loan_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Позику не знайдено")

    if record["status"] != "Active":
        raise HTTPException(status_code=409, detail="Позику вже завершено")

    record["status"] = "Returned"
    active_loans_books.discard(record["book_id"])

    event_payload = {
        "event_type": "LoanReturned",
        "loan_id": record["loan_id"],
        "book_id": record["book_id"],
        "borrower_name": record["borrower_name"],
        "owner_id": record["owner_id"],
    }

    try:
        await asyncio.to_thread(publish_event, event_payload)
    except RuntimeError:
        record["status"] = "Active"
        active_loans_books.add(record["book_id"])
        raise HTTPException(
            status_code=503,
            detail="Не вдалося надіслати подію. Спробуйте пізніше.",
        )

    return {"message": "Книгу повернено, позику завершено", "loan_id": loan_id}

@app.post("/loans", status_code=201)
async def create_loan(loan: LoanRequest):
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(
                f"{CATALOG_SERVICE_URL}/books/{loan.book_id}",
                params={"owner_id": loan.owner_id},
                timeout=3.0,
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Catalog Service недоступний",
            )

    if res.status_code == 404:
        raise HTTPException(
            status_code=404,
            detail="Книгу не знайдено в каталозі",
        )

    if res.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Помилка відповіді Catalog Service",
        )

    if loan.book_id in active_loans_books:
        raise HTTPException(
            status_code=409,
            detail="Книга вже видана (активна позика вже існує)",
        )

    loan_id = str(max((int(key) for key in loans_db), default=0) + 1)

    record = {
        "loan_id": loan_id,
        "book_id": loan.book_id,
        "borrower_name": loan.borrower_name,
        "owner_id": loan.owner_id,
        "status": "Active",
    }

    event_payload = {
        "event_type": "LoanCreated",
        "loan_id": loan_id,
        "book_id": loan.book_id,
        "borrower_name": loan.borrower_name,
        "owner_id": loan.owner_id,
    }

    loans_db[loan_id] = record
    active_loans_books.add(loan.book_id)

    try:
        await asyncio.to_thread(publish_event, event_payload)
    except RuntimeError:
        loans_db.pop(loan_id, None)
        active_loans_books.discard(loan.book_id)
        raise HTTPException(
            status_code=503,
            detail="Не вдалося надіслати подію. Спробуйте пізніше.",
        )

    return {
        "message": "Позику успішно оформлено",
        "loan_id": loan_id,
    }

@app.get("/loans/active")
def get_active_loans():
    return [loan for loan in loans_db.values() if loan.get("status") == "Active"]

@app.get("/loans/{loan_id}")
def get_loan(loan_id: str):
    record = loans_db.get(loan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Позику не знайдено")
    return record

