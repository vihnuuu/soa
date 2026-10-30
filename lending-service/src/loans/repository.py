class LoanRepository:
    def __init__(self) -> None:
        self._loans_db: dict[str, dict] = {}
        self._active_loans_books: set[str] = set()

    async def get_by_id(self, loan_id: str) -> dict | None:
        record = self._loans_db.get(loan_id)
        return record.copy() if record else None

    async def is_book_active(self, book_id: str) -> bool:
        return book_id in self._active_loans_books

    async def create(self, loan_record: dict) -> dict:
        self._loans_db[loan_record["loan_id"]] = loan_record
        self._active_loans_books.add(loan_record["book_id"])
        return loan_record.copy()

    async def delete(self, loan_id: str, book_id: str) -> None:
        self._loans_db.pop(loan_id, None)
        self._active_loans_books.discard(book_id)

    async def update_status(self, loan_id: str, status: str) -> None:
        if loan_id in self._loans_db:
            self._loans_db[loan_id]["status"] = status

    async def remove_active_book(self, book_id: str) -> None:
        self._active_loans_books.discard(book_id)

    async def add_active_book(self, book_id: str) -> None:
        self._active_loans_books.add(book_id)

    async def get_next_id(self) -> str:
        return str(max((int(k) for k in self._loans_db), default=0) + 1)

    async def list_active(self) -> list[dict]:
        return [
            loan.copy()
            for loan in self._loans_db.values()
            if loan.get("status") == "Active"
        ]


loan_repository = LoanRepository()