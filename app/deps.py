"""Pomocnicze zależności (dependencies) do rate limitingu."""
from fastapi import Request, Depends

from app.ratelimit import strict_limiter, default_limiter, booking_limiter


def rate_limit_strict(request: Request) -> None:
    strict_limiter.check(request)


def rate_limit_default(request: Request) -> None:
    default_limiter.check(request)


def rate_limit_booking(request: Request) -> None:
    booking_limiter.check(request)
