from src.books.schemas import BookCreate


class BookRepository:
    def __init__(self) -> None:
        self._books_db: dict[str, dict] = {}

    async def get_by_id(self, book_id: str) -> dict | None:
        book = self._books_db.get(str(book_id))
        return book.copy() if book else None

    async def list_books(self, owner_id: str | None = None) -> list[dict]:
        if owner_id:
            target_owner = str(owner_id)
            return [
                book.copy()
                for book in self._books_db.values()
                if str(book.get("owner_id")) == target_owner
            ]
        return [book.copy() for book in self._books_db.values()]

    async def create(self, book_data: BookCreate) -> dict:
        book_dict = book_data.model_dump(mode="json")
        key = str(book_dict["id"])
        self._books_db[key] = book_dict
        return book_dict.copy()

book_repository = BookRepository()