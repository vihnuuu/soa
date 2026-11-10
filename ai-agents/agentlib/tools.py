from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from agentlib.config import Settings
from agentlib.exceptions import LibraryAPIError, ToolInputError, ToolPermissionError
from agentlib.guardrails import require_text, require_uuid, validate_args

logger = logging.getLogger("agentlib.tools")

Handler = Callable[[dict], Awaitable[Any]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Handler
    is_write: bool = False

    def openai_spec(self) -> dict:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


async def safe_call(tool: Tool, args: Any) -> dict:
    try:
        validate_args(tool.parameters, args)
        return {"ok": True, "data": await tool.handler(args)}
    except ToolInputError as exc:
        return {"ok": False, "error": f"invalid arguments: {exc}"}
    except ToolPermissionError as exc:
        return {"ok": False, "error": f"permission denied: {exc}"}
    except LibraryAPIError as exc:
        return {"ok": False, "error": f"API error: {exc}"}
    except Exception:
        logger.exception("tool %s crashed", tool.name)
        return {"ok": False, "error": "internal tool error"}


def resolve_owner(settings: Settings, owner_id: Any) -> str:
    if owner_id in (None, ""):
        if not settings.default_owner_id:
            raise ToolInputError("owner_id is required")
        return settings.default_owner_id
    oid = require_uuid(owner_id, "owner_id")
    if oid not in settings.allowed_owner_ids:
        raise ToolPermissionError("this owner_id is not permitted for the agent")
    return oid


_UUID = {"type": "string", "minLength": 36, "maxLength": 36}
_OWNER = {**_UUID, "description": "Owner UUID. Optional: defaults to the configured owner."}


def _schema(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


class LibraryTools:
    def __init__(self, api: Any, settings: Settings, poll_interval: float = 1.0) -> None:
        self.api = api
        self.s = settings
        self.poll_interval = poll_interval

    def _limit(self, items: list) -> dict:
        n = self.s.max_list_items
        return {"total": len(items), "items": items[:n], "truncated": len(items) > n}

    def _check_loan_owner(self, loan: dict) -> None:
        owner = str(loan.get("owner_id") or "").lower()
        if owner not in self.s.allowed_owner_ids:
            raise ToolPermissionError("loan not found or not permitted")

    @staticmethod
    def _slim_book(b: dict) -> dict:
        return {k: b.get(k) for k in ("id", "title", "author", "is_available")}

    @staticmethod
    def _slim_loan(x: dict) -> dict:
        return {k: x.get(k) for k in ("id", "book_id", "borrower_name", "status", "due_date")}

    async def list_books(self, a: dict) -> dict:
        owner = resolve_owner(self.s, a.get("owner_id"))
        books = await self.api.list_books(owner)
        needle = (a.get("title_contains") or "").strip().lower()
        if needle:
            books = [b for b in books if needle in str(b.get("title", "")).lower()]
        return self._limit([self._slim_book(b) for b in books])

    async def get_book(self, a: dict) -> dict:
        owner = resolve_owner(self.s, a.get("owner_id"))
        return self._slim_book(await self.api.get_book(require_uuid(a["book_id"], "book_id"), owner))

    async def create_book(self, a: dict) -> dict:
        owner = resolve_owner(self.s, a.get("owner_id"))
        title = require_text(a["title"], "title", max_len=255)
        author = require_text(a["author"], "author", max_len=255)
        for b in await self.api.list_books(owner):
            if str(b.get("title", "")).lower() == title.lower() and str(b.get("author", "")).lower() == author.lower():
                return {"created": False, "note": "book already exists", "book": self._slim_book(b)}
        book = await self.api.create_book(
            {"id": str(uuid.uuid4()), "title": title, "author": author, "owner_id": owner, "is_available": True}
        )
        return {"created": True, "book": self._slim_book(book)}

    async def create_loan(self, a: dict) -> dict:
        owner = resolve_owner(self.s, a.get("owner_id"))
        book_id = require_uuid(a["book_id"], "book_id")
        borrower = require_text(a["borrower_name"], "borrower_name", max_len=128)
        res = await self.api.create_loan(book_id, owner, borrower)
        return {
            "loan_id": res.get("loan_id"),
            "status": "PENDING",
            "note": "asynchronous (SAGA): status becomes ACTIVE after confirmation; check with get_loan(wait_seconds)",
        }

    async def get_loan(self, a: dict) -> dict:
        loan_id = require_uuid(a["loan_id"], "loan_id")
        wait = int(a.get("wait_seconds", 0))
        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait
        while True:
            loan = await self.api.get_loan(loan_id)
            self._check_loan_owner(loan)
            if loan.get("status") != "PENDING" or loop.time() >= deadline:
                return self._slim_loan(loan)
            await asyncio.sleep(self.poll_interval)

    async def list_loans(self, a: dict) -> dict:
        owner = resolve_owner(self.s, a.get("owner_id"))
        loans = await self.api.list_loans(owner, bool(a.get("active_only", False)))
        return self._limit([self._slim_loan(x) for x in loans])

    async def return_loan(self, a: dict) -> dict:
        loan_id = require_uuid(a["loan_id"], "loan_id")
        self._check_loan_owner(await self.api.get_loan(loan_id))
        res = await self.api.return_loan(loan_id)
        return {"loan_id": res.get("loan_id", loan_id), "status": "RETURNED"}

    def tools(self, *, names: list[str] | None = None, read_only: bool = False) -> list[Tool]:
        all_tools = [
            Tool(
                "list_books",
                "List the owner's books in the catalog (id, title, author, is_available). "
                "Use it to check whether a book exists before creating it.",
                _schema(
                    {
                        "owner_id": _OWNER,
                        "title_contains": {
                            "type": "string",
                            "maxLength": 100,
                            "description": "Case-insensitive title filter",
                        },
                    }
                ),
                self.list_books,
            ),
            Tool(
                "get_book",
                "Get one book by its UUID.",
                _schema(
                    {
                        "book_id": {**_UUID, "description": "Book UUID from a previous tool result"},
                        "owner_id": _OWNER,
                    },
                    ["book_id"],
                ),
                self.get_book,
            ),
            Tool(
                "create_book",
                "Create a book in the catalog. The ID is generated by the tool. Idempotent: "
                "returns the existing book if the same title+author already exists.",
                _schema(
                    {
                        "title": {"type": "string", "minLength": 1, "maxLength": 255},
                        "author": {"type": "string", "minLength": 1, "maxLength": 255},
                        "owner_id": _OWNER,
                    },
                    ["title", "author"],
                ),
                self.create_book,
                is_write=True,
            ),
            Tool(
                "create_loan",
                "Lend a book to a borrower. Asynchronous: returns loan_id with status PENDING; "
                "it becomes ACTIVE after the notification service confirms. Call get_loan afterwards.",
                _schema(
                    {
                        "book_id": {**_UUID, "description": "Book UUID from list_books/create_book"},
                        "borrower_name": {"type": "string", "minLength": 1, "maxLength": 128},
                        "owner_id": _OWNER,
                    },
                    ["book_id", "borrower_name"],
                ),
                self.create_loan,
                is_write=True,
            ),
            Tool(
                "get_loan",
                "Get a loan status (PENDING, ACTIVE, CANCELLED, RETURNED). With wait_seconds>0 the tool "
                "polls while the status is PENDING (saves round-trips).",
                _schema(
                    {
                        "loan_id": {**_UUID, "description": "Loan UUID from create_loan/list_loans"},
                        "wait_seconds": {"type": "integer", "minimum": 0, "maximum": 10},
                    },
                    ["loan_id"],
                ),
                self.get_loan,
            ),
            Tool(
                "list_loans",
                "List the owner's loans (history, or only active ones).",
                _schema({"owner_id": _OWNER, "active_only": {"type": "boolean"}}),
                self.list_loans,
            ),
            Tool(
                "return_loan",
                "Mark a loan as returned. Works only for ACTIVE loans.",
                _schema({"loan_id": {**_UUID, "description": "Loan UUID"}}, ["loan_id"]),
                self.return_loan,
                is_write=True,
            ),
        ]
        if names is not None:
            all_tools = [t for t in all_tools if t.name in names]
        if read_only:
            all_tools = [t for t in all_tools if not t.is_write]
        return all_tools