from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid

from agents2agents.a2a_client import call_agent, fetch_card
from agentlib.config import get_settings
from agentlib.library_api import LibraryAPI

CONSUMER_URL = os.getenv("CONSUMER_URL", "http://127.0.0.1:9102")
PRODUCER_URL = os.getenv("PRODUCER_URL", "http://127.0.0.1:9101")


async def main(natural: bool) -> None:
    for url in (PRODUCER_URL, CONSUMER_URL):
        card = await fetch_card(url)
        print(f"Картка {card.name}: {[sk.id for sk in card.skills]}")

    s = get_settings()
    api = LibraryAPI(s.gateway_url, s.http_timeout)
    try:
        book = await api.create_book(
            {
                "id": str(uuid.uuid4()),
                "title": f"A2A demo {uuid.uuid4().hex[:6]}",
                "author": "Demo",
                "owner_id": s.default_owner_id,
                "is_available": True,
            }
        )
    finally:
        await api.aclose()
    print(f"\nСтворено книгу {book['id']}")

    if natural:
        request = f"Видай книгу {book['id']} позичальнику Степан Радченко і переконайся, що сповіщення отримано."
    else:
        request = json.dumps(
            {"skill": "lend_and_confirm", "book_id": book["id"], "borrower_name": "Степан Радченко"},
            ensure_ascii=False,
        )
    print(f"\nКористувач -> consumer-агент: {request}\n")
    reply = await call_agent(CONSUMER_URL, request, timeout=90)
    print(f"Агент {reply.agent}: {reply.state}")
    for artifact in reply.artifacts:
        try:
            print(json.dumps(json.loads(artifact), ensure_ascii=False, indent=2))
        except json.JSONDecodeError:
            print(artifact)
    if reply.status_text:
        print(f"(status: {reply.status_text})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nl", action="store_true", help="запит природною мовою")
    asyncio.run(main(parser.parse_args().nl))