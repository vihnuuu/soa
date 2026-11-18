from __future__ import annotations

import asyncio
import uuid
from typing import Any

from agentlib.guardrails import require_uuid


class NotificationStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._pool: Any = None

    async def _get_pool(self) -> Any:
        if self._pool is None:
            import asyncpg

            self._pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=3, command_timeout=5)
        return self._pool

    async def by_loan(self, loan_id: str) -> list[dict]:
        lid = uuid.UUID(require_uuid(loan_id, "loan_id"))
        pool = await self._get_pool()
        rows = await pool.fetch(
            "SELECT event_id, message, status::text AS status, created_at "
            "FROM notification WHERE loan_id = $1 ORDER BY created_at LIMIT 20",
            lid,
        )
        return [
            {
                "event_id": str(r["event_id"]),
                "message": r["message"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]

    async def wait_for_loan(self, loan_id: str, timeout: float = 20.0, interval: float = 1.0) -> list[dict]:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            rows = await self.by_loan(loan_id)
            if rows or loop.time() >= deadline:
                return rows
            await asyncio.sleep(interval)