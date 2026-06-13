"""Prosty limitator żądań w pamięci (In-memory Rate Limiter).

Przechowuje liczniki żądań w słowniku z oknami czasowymi.
Okresowe czyszczenie starych wpisów przy każdej kontroli.
"""

import time
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import HTTPException, Request


class RateLimiter:
    """Limitator żądań — weryfikuje liczbę zapytań w oknie czasowym.

    Args:
        max_requests: Maksymalna liczba żądań w oknie.
        window_seconds: Długość okna w sekundach.
    """

    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # {key: [(timestamp, count), ...]}  — rolling window
        self._store: Dict[str, list] = defaultdict(list)

    def _cleanup(self, key: str, now: float):
        """Usuwa wpisy starsze niż okno czasowe."""
        cutoff = now - self.window_seconds
        self._store[key] = [
            (ts, c) for ts, c in self._store[key] if ts > cutoff
        ]
        if not self._store[key]:
            del self._store[key]

    def check(self, request: Request) -> None:
        """Sprawdza czy żądanie mieści się w limicie. Rzuca HTTPException 429, jeśli nie."""
        # Klucz: IP + ścieżka
        ip = request.client.host if request.client else "unknown"
        key = f"{ip}:{request.url.path}"

        now = time.time()
        self._cleanup(key, now)

        # Oblicz aktualną liczbę żądań w oknie
        total = sum(c for _, c in self._store.get(key, []))
        if total >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail="Zbyt wiele żądań. Spróbuj ponownie za chwilę.",
                headers={"Retry-After": str(self.window_seconds)},
            )

        # Dodaj bieżące żądanie
        self._store[key].append((now, 1))

    def reset(self, key: str):
        """Resetuje licznik dla danego klucza (np. po udanym logowaniu)."""
        self._store.pop(key, None)


# Globalne instancje dla różnych endpointów
strict_limiter = RateLimiter(max_requests=5, window_seconds=60)  # 5 req/min — logowanie, rejestracja
default_limiter = RateLimiter(max_requests=30, window_seconds=60)  # 30 req/min — pozostałe API
booking_limiter = RateLimiter(max_requests=10, window_seconds=60)  # 10 req/min — składanie rezerwacji
