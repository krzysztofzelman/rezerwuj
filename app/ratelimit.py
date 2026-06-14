"""Limitator żądań z opcjonalnym Redis i automatycznym przełączaniem na RAM.

Gdy REDIS_URL jest skonfigurowany w .env, używa Redis (INCR + EXPIRE).
Przy błędzie połączenia Redis automatycznie przełącza się na pamięć RAM.
"""
import logging
import time
from collections import defaultdict
from typing import Dict, Optional

from fastapi import HTTPException, Request

from app.config import REDIS_URL

logger = logging.getLogger("servicehub.ratelimit")


class RateLimiter:
    """Limitator żądań — weryfikuje liczbę zapytań w oknie czasowym.

    Args:
        max_requests: Maksymalna liczba żądań w oknie.
        window_seconds: Długość okna w sekundach.
    """

    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Pamięć RAM (fallback)
        self._memory_store: Dict[str, list] = defaultdict(list)
        # Redis
        self._redis_client: Optional[object] = None
        self._redis_available = False

        if REDIS_URL:
            self._init_redis()

    def _init_redis(self):
        """Próbuje połączyć się z Redis."""
        try:
            import redis as redis_mod
            self._redis_client = redis_mod.from_url(
                REDIS_URL,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            self._redis_client.ping()
            self._redis_available = True
            logger.info("Redis rate limiting: połączono z %s", REDIS_URL)
        except Exception as e:
            logger.warning("Redis niedostępny (%s) — używam pamięci RAM", e)
            self._redis_client = None
            self._redis_available = False

    # ---- Redis ----

    def _redis_check(self, key: str) -> Optional[int]:
        """Sprawdza limit przez Redis (INCR + EXPIRE). Zwraca None przy błędzie."""
        try:
            redis_key = f"rl:{key}"
            count = self._redis_client.incr(redis_key)
            if count == 1:
                self._redis_client.expire(redis_key, self.window_seconds)
            return count
        except Exception as e:
            logger.warning("Redis błąd: %s — przełączam na RAM", e)
            self._redis_available = False
            return None

    def _redis_reset(self, key: str):
        """Resetuje licznik w Redis."""
        try:
            self._redis_client.delete(f"rl:{key}")
        except Exception:
            pass

    # ---- Pamięć RAM (fallback) ----

    def _memory_cleanup(self, key: str, now: float):
        """Usuwa wpisy starsze niż okno czasowe z pamięci RAM."""
        cutoff = now - self.window_seconds
        self._memory_store[key] = [
            (ts, c) for ts, c in self._memory_store[key] if ts > cutoff
        ]
        if not self._memory_store[key]:
            del self._memory_store[key]

    def _memory_check(self, key: str, now: float) -> int:
        """Sprawdza limit w pamięci RAM (rolling window)."""
        self._memory_cleanup(key, now)
        total = sum(c for _, c in self._memory_store.get(key, []))
        self._memory_store[key].append((now, 1))
        return total + 1

    def _memory_reset(self, key: str):
        """Resetuje licznik w pamięci RAM."""
        self._memory_store.pop(key, None)

    # ---- Publiczne API ----

    def check(self, request: Request) -> None:
        """Sprawdza czy żądanie mieści się w limicie. Rzuca HTTPException 429, jeśli nie."""
        ip = request.client.host if request.client else "unknown"
        key = f"{ip}:{request.url.path}"

        now = time.time()

        # Próbuj Redis
        if self._redis_available and self._redis_client:
            count = self._redis_check(key)
            if count is not None:
                if count > self.max_requests:
                    raise HTTPException(
                        status_code=429,
                        detail="Zbyt wiele żądań. Spróbuj ponownie za chwilę.",
                        headers={"Retry-After": str(self.window_seconds)},
                    )
                return  # Redis obsłużył

        # Fallback do pamięci RAM
        count = self._memory_check(key, now)
        if count > self.max_requests:
            raise HTTPException(
                status_code=429,
                detail="Zbyt wiele żądań. Spróbuj ponownie za chwilę.",
                headers={"Retry-After": str(self.window_seconds)},
            )

    def reset(self, key: str):
        """Resetuje licznik dla danego klucza (np. po udanym logowaniu)."""
        self._memory_reset(key)
        self._redis_reset(key)


# Globalne instancje dla różnych endpointów (API niezmienione)
strict_limiter = RateLimiter(max_requests=5, window_seconds=60)
default_limiter = RateLimiter(max_requests=30, window_seconds=60)
booking_limiter = RateLimiter(max_requests=10, window_seconds=60)
