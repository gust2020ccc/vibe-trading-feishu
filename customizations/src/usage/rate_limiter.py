"""In-memory rate limiter and concurrent session tracker.

These are intentionally in-memory (not persisted) because:
- Rate limiting windows are short (60s) — process restart naturally resets.
- Concurrent session counts are process-local state.
- For a private assistant with <10 users, this is perfectly adequate.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """Sliding-window rate limiter (requests per minute)."""

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def acquire(self, user_id: str, limit_per_min: int) -> bool:
        """Record a request timestamp and return whether it's within the limit.

        Args:
            user_id: The user identifier.
            limit_per_min: Maximum requests per minute. 0 means unlimited.

        Returns:
            True if the request is allowed, False if rate-limited.
        """
        if limit_per_min <= 0:
            return True

        now = time.monotonic()
        cutoff = now - 60.0  # 1 minute window

        with self._lock:
            window = self._windows[user_id]
            # Purge expired entries
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= limit_per_min:
                return False
            window.append(now)
            return True


class ConcurrencyTracker:
    """Per-user concurrent session (in-flight attempt) counter."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def try_acquire(self, user_id: str, limit: int) -> bool:
        """Atomically check and increment the concurrent session count.

        Args:
            user_id: The user identifier.
            limit: Maximum concurrent sessions. 0 means unlimited.

        Returns:
            True if the slot was acquired, False if the limit is exceeded
            (count is NOT incremented in that case).
        """
        if limit <= 0:
            return True

        with self._lock:
            current = self._counts[user_id]
            if current >= limit:
                return False
            self._counts[user_id] = current + 1
            return True

    def release(self, user_id: str) -> None:
        """Decrement the concurrent session count for a user.

        Safe to call even if the count is already 0 (no-op).
        """
        with self._lock:
            current = self._counts.get(user_id, 0)
            if current > 0:
                self._counts[user_id] = current - 1
                if self._counts[user_id] == 0:
                    del self._counts[user_id]

    def current(self, user_id: str) -> int:
        """Return the current concurrent session count for a user."""
        with self._lock:
            return self._counts.get(user_id, 0)
