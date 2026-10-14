"""Small in-process token-bucket rate limiter.

Scope note: this is per-process. With multiple uvicorn workers or replicas,
enforce limits at the reverse proxy or use a shared store (Redis). For a single
process it is exact, allocation-free in the common path, and needs no
infrastructure.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from time import monotonic

MAX_TRACKED_KEYS = 20_000
EVICTION_BATCH = 4_000


@dataclass(slots=True)
class _Bucket:
    hits: deque[float] = field(default_factory=deque)


class RateLimiter:
    """Sliding-window limiter: at most ``limit`` events per ``window`` seconds."""

    def __init__(self, limit: int, window: int, *, name: str = "default") -> None:
        if limit < 1 or window < 1:
            raise ValueError("limit and window must be >= 1")
        self.limit = limit
        self.window = window
        self.name = name
        self._buckets: dict[str, _Bucket] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> tuple[bool, int]:
        """Consume one slot.

        Returns ``(allowed, retry_after_seconds)``.
        """
        now = monotonic()
        cutoff = now - self.window

        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket()
                self._buckets[key] = bucket

            hits = bucket.hits
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.limit:
                retry_after = max(1, int(hits[0] + self.window - now) + 1)
                return False, retry_after

            hits.append(now)

            if len(self._buckets) > MAX_TRACKED_KEYS:
                self._evict(cutoff)

            return True, 0

    async def allow(self, key: str) -> bool:
        allowed, _ = await self.check(key)
        return allowed

    def _evict(self, cutoff: float) -> None:
        """Drop idle buckets so long-running processes stay bounded."""
        stale = [k for k, b in self._buckets.items() if not b.hits or b.hits[-1] <= cutoff]
        for key in stale[:EVICTION_BATCH]:
            self._buckets.pop(key, None)

        if len(self._buckets) > MAX_TRACKED_KEYS:
            # Still oversized: drop the oldest-touched buckets outright.
            ordered = sorted(
                self._buckets.items(),
                key=lambda kv: kv[1].hits[-1] if kv[1].hits else 0.0,
            )
            for key, _ in ordered[:EVICTION_BATCH]:
                self._buckets.pop(key, None)

    def reset(self) -> None:
        self._buckets.clear()

    @property
    def tracked_keys(self) -> int:
        return len(self._buckets)
