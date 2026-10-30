from src.books.schemas import BookCreate


class BookRepository:
    def __init__(self) -> None:
        self._books_db: dict[str, dict] = {
            "1": {
                "id": "1",
                "title": "Макова війна",
                "author": "Ребекка Кван",
                "owner_id": "owner_1",
            },
            "2": {
                "id": "2",
                "title": "Заковані",
                "author": "Сенлін Юй",
                "owner_id": "owner_1",
            },
            "3": {
                "id": "3",
                "title": "Кульбабове вино",
                "author": "Рей Бредбері",
                "owner_id": "owner_1",
            },
        }

    async def get_by_id(self, book_id: str) -> dict | None:
        book = self._books_db.get(book_id)
        return book.copy() if book else None

    async def list_books(self, owner_id: str | None = None) -> list[dict]:
        if owner_id:
            return [
                book.copy()
                for book in self._books_db.values()
                if book["owner_id"] == owner_id
            ]
        return [book.copy() for book in self._books_db.values()]

    async def create(self, book_data: BookCreate) -> dict:
        book_dict = book_data.model_dump()
        self._books_db[book_data.id] = book_dict
        return book_dict.copy()


book_repository = BookRepository()