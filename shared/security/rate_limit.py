import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

logger = logging.getLogger("shared.security.rate_limit")

_HIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
local ttl = redis.call('TTL', KEYS[1])
if ttl < 0 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
  ttl = tonumber(ARGV[1])
end
return {count, ttl}
"""


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int = 0


class RateLimiter(Protocol):
    def hit(self, key: str) -> RateLimitDecision: ...


class InMemoryRateLimiter:
    def __init__(self, limit: int, window: int = 60) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key: str) -> RateLimitDecision:
        now = time.monotonic()
        with self._lock:
            queue = self._hits[key]
            while queue and now - queue[0] > self.window:
                queue.popleft()
            if len(queue) >= self.limit:
                retry_after = max(1, int(self.window - (now - queue[0])))
                return RateLimitDecision(False, retry_after)
            queue.append(now)
            return RateLimitDecision(True)


class RedisRateLimiter:
    def __init__(
        self,
        url: str,
        limit: int,
        window: int = 60,
        prefix: str = "rl",
        fallback: RateLimiter | None = None,
    ) -> None:
        import redis

        self.limit = limit
        self.window = window
        self.prefix = prefix
        self._redis_error = redis.RedisError
        self._client = redis.Redis.from_url(
            url,
            socket_timeout=0.3,
            socket_connect_timeout=0.3,
            decode_responses=True,
        )
        self._script = self._client.register_script(_HIT_SCRIPT)
        self._fallback = fallback or InMemoryRateLimiter(limit, window)

    def hit(self, key: str) -> RateLimitDecision:
        redis_key = f"{self.prefix}:{key}"
        try:
            count, ttl = self._script(keys=[redis_key], args=[self.window])
        except self._redis_error as exc:
            logger.warning("redis rate limiter unavailable, using local fallback: %s", type(exc).__name__)
            return self._fallback.hit(key)
        if int(count) > self.limit:
            return RateLimitDecision(False, max(1, int(ttl)))
        return RateLimitDecision(True)


def build_rate_limiter(
    *,
    limit: int,
    window: int = 60,
    redis_url: str | None = None,
    prefix: str = "rl",
) -> RateLimiter:
    if redis_url:
        return RedisRateLimiter(redis_url, limit, window, prefix)
    return InMemoryRateLimiter(limit, window)