import argparse
import json
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter

OWNER_ID = "00000000-0000-0000-0000-000000000002"


def call(method, url, token=None, body=None, timeout=10):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def get_token(kc_url, password):
    form = urllib.parse.urlencode(
        {"grant_type": "password", "client_id": "library-cli", "username": "student", "password": password}
    ).encode()
    req = urllib.request.Request(f"{kc_url}/realms/library/protocol/openid-connect/token", data=form)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["access_token"]


def worker(args, stats, stop_at):
    base = args.base_url
    token = get_token(args.keycloak_url, args.password)
    token_born = time.time()
    while time.time() < stop_at:
        if time.time() - token_born > 240:
            token = get_token(args.keycloak_url, args.password)
            token_born = time.time()
        book_id = str(uuid.uuid4())
        steps = [
            ("POST", f"{base}/api/catalog/books", {"id": book_id, "title": f"Книга {book_id[:6]}", "author": "Load", "owner_id": OWNER_ID, "is_available": True}),
            ("GET", f"{base}/api/catalog/books?owner_id={OWNER_ID}", None),
            ("GET", f"{base}/api/catalog/books/{book_id}?owner_id={OWNER_ID}", None),
        ]
        for m, u, b in steps:
            code, _ = call(m, u, token, b)
            stats[code] += 1
        code, resp = call("POST", f"{base}/api/lending/loans", token, {"book_id": book_id, "owner_id": OWNER_ID, "borrower_name": "Load Test"})
        stats[code] += 1
        if code == 202 and resp:
            loan_id = resp["loan_id"]
            for _ in range(8):
                time.sleep(0.5)
                code, loan = call("GET", f"{base}/api/lending/loans/{loan_id}", token)
                stats[code] += 1
                if loan and loan.get("status") == "ACTIVE":
                    code, _ = call("POST", f"{base}/api/lending/loans/{loan_id}/return", token)
                    stats[code] += 1
                    break
        code, _ = call("GET", f"{base}/api/lending/loans?owner_id={OWNER_ID}", token)
        stats[code] += 1
        time.sleep(random.uniform(0.4, 1.0) * args.workers)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    ap.add_argument("--keycloak-url", default="http://localhost:8180")
    ap.add_argument("--password", default=os.getenv("STUDENT_PASSWORD"))
    ap.add_argument("--duration", type=int, default=60, help="секунд")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    if not args.password:
        ap.error("задайте STUDENT_PASSWORD (як у .env) або --password")

    stats: Counter = Counter()
    stop_at = time.time() + args.duration
    threads = [threading.Thread(target=worker, args=(args, stats, stop_at), daemon=True) for _ in range(args.workers)]
    for t in threads:
        t.start()
    while any(t.is_alive() for t in threads):
        time.sleep(5)
        print(f"[{time.strftime('%H:%M:%S')}] статуси: {dict(sorted(stats.items()))}", flush=True)
    print("Готово:", dict(sorted(stats.items())))


if __name__ == "__main__":
    main()
