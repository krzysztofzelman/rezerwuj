"""Metryki Prometheus dla systemu Napraw Mnie.

Liczniki i wskaźniki dostępne na endpointcie GET /metrics.
"""
import time
import logging

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("napraw_mnie.metrics")

# === Liczniki ===

orders_total = Counter(
    "napraw_mnie_orders_total",
    "Łączna liczba zleceń",
    ["status", "provider_id"],
)

rate_limit_hits = Counter(
    "napraw_mnie_rate_limit_hits_total",
    "Liczba odrzuconych żądań (429)",
)

emails_sent = Counter(
    "napraw_mnie_emails_sent_total",
    "Liczba wysłanych e-maili",
)

password_resets = Counter(
    "napraw_mnie_password_resets_total",
    "Liczba wysłanych linków do resetu hasła",
)

# === Wskaźniki ===

active_providers = Gauge(
    "napraw_mnie_active_providers",
    "Liczba aktywnych usługodawców (can_accept_orders)",
)

total_orders_gauge = Gauge(
    "napraw_mnie_total_orders",
    "Łączna liczba zleceń w systemie",
)

# === Histogramy ===

request_duration = Histogram(
    "napraw_mnie_request_duration_seconds",
    "Czas trwania żądań HTTP",
    ["method", "path", "status_code"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware mierzący czas trwania żądań HTTP."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        status_code = str(response.status_code)
        request_duration.labels(method=method, path=path, status_code=status_code).observe(duration)

        return response


def metrics_endpoint() -> Response:
    """Zwraca metryki w formacie Prometheus."""
    from app.database import SessionLocal
    from app.models import Order, ServiceProvider

    db = SessionLocal()
    try:
        # Aktualizuj wskaźniki
        active_count = (
            db.query(ServiceProvider)
            .filter(ServiceProvider.is_active == True)  # noqa: E712
            .count()
        )
        active_providers.set(active_count)

        order_count = db.query(Order).count()
        total_orders_gauge.set(order_count)
    except Exception as e:
        logger.error("Błąd podczas zbierania metryk: %s", e)
    finally:
        db.close()

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
