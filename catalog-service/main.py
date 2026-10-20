import socket

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(
    title="Catalog Service",
    root_path="/api/catalog",
)

books_db = {
    "1": {
        "id": "1",
        "title": "Макова війна",
        "author": "Ребекка Кван",
        "owner_id": "owner_1",
    },
    "2": {
        "id": "2",
        "title": "Заковані",
        "author": "Лія Арден",
        "owner_id": "owner_1",
    },
    "3": {
        "id": "3",
        "title": "Кульбабове вино",
        "author": "Рей Бредбері",
        "owner_id": "owner_1",
    },
}


class BookCreate(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)


@app.post("/books", status_code=201)
def create_book(book: BookCreate):
    if book.id in books_db:
        raise HTTPException(
            status_code=400,
            detail="Книга з таким ID вже існує",
        )

    books_db[book.id] = book.model_dump()
    return books_db[book.id]


@app.get("/books")
def get_books(owner_id: str | None = Query(default=None)):
    if owner_id:
        return [
            book
            for book in books_db.values()
            if book["owner_id"] == owner_id
        ]

    return list(books_db.values())

@app.get("/books/{book_id}")
def get_book(book_id: str, owner_id: str = Query(..., min_length=1)):
    book = books_db.get(book_id)

    if not book or book["owner_id"] != owner_id:
        raise HTTPException(
            status_code=404,
            detail="Книга не знайдена або доступ обмежений",
        )

    return book


@app.get("/health")
def health():
    return {"status": "ok", "instance": socket.gethostname()}