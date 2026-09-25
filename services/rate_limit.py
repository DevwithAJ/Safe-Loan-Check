from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
import time


class FixedWindowRateLimiter:
    """Small process-local limiter for a low-volume deployment.

    The provided Gunicorn configuration intentionally uses one worker with threads,
    which makes this limiter consistent for the process. A larger deployment should
    replace this with a shared Redis-backed limiter.
    """

    def __init__(self):
        self._buckets = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, *, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds
        bucket_key = (key, limit, window_seconds)
        with self._lock:
            bucket = self._buckets[bucket_key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket[0])))
                return False, retry_after
            bucket.append(now)
            return True, 0
