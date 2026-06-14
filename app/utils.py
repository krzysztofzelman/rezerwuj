"""
Funkcje pomocnicze — generowanie dostępnych slotów czasowych.
"""
import datetime
from typing import List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import ServiceProvider, WorkingHour, Order, BlockedSlot


def get_available_slots(
    db: Session, provider: ServiceProvider, target_date: datetime.date, duration: int | None = None
) -> List[str]:
    """
    Zwraca listę dostępnych godzin (HH:MM) dla danego usługodawcy i daty.
    Uwzględnia godziny pracy, przerwę, istniejące rezerwacje i zablokowane sloty.
    `duration` — opcjonalny czas trwania w minutach (np. z wybranej usługi).
    """
    if duration is None:
        duration = provider.service_duration
    if not duration:
        return []

    day_of_week = target_date.weekday()  # 0=Monday

    # 1. Pobierz godziny pracy dla danego dnia
    wh = (
        db.query(WorkingHour)
        .filter(
            WorkingHour.provider_id == provider.id,
            WorkingHour.day_of_week == day_of_week,
        )
        .first()
    )

    if not wh or not wh.is_working or not wh.start_time or not wh.end_time:
        return []

    work_start = wh.start_time
    work_end = wh.end_time
    break_start = wh.break_start
    break_end = wh.break_end

    # 2. Generuj wszystkie potencjalne sloty co `duration` minut
    all_slots = _generate_time_slots(work_start, work_end, duration)

    # 3. Odfiltruj sloty przypadające na przerwę
    if break_start and break_end:
        all_slots = [
            slot for slot in all_slots
            if not _is_time_overlap(slot, duration, break_start, break_end)
        ]

    # 4. Pobierz istniejące zamówienia (potwierdzone) na ten dzień
    existing_bookings = (
        db.query(Order)
        .filter(
            Order.provider_id == provider.id,
            Order.booking_date == target_date,
            Order.status == "confirmed",
        )
        .all()
    )

    for booking in existing_bookings:
        all_slots = [
            slot for slot in all_slots
            if not _is_time_overlap(
                slot, duration, booking.booking_time, booking.duration
            )
        ]

    # 5. Pobierz zablokowane sloty na ten dzień
    blocked = (
        db.query(BlockedSlot)
        .filter(
            BlockedSlot.provider_id == provider.id,
            BlockedSlot.block_date == target_date,
        )
        .all()
    )

    for block in blocked:
        all_slots = [
            slot for slot in all_slots
            if not _is_time_overlap(slot, duration, block.start_time, block.end_time)
        ]

    # 6. Odfiltruj sloty w przeszłości (dla dzisiejszej daty)
    now = datetime.datetime.now()
    if target_date == now.date():
        current_time_minutes = now.hour * 60 + now.minute
        all_slots = [
            slot for slot in all_slots
            if _time_to_minutes(slot) > current_time_minutes
        ]

    return all_slots


def _generate_time_slots(
    start_time: datetime.time, end_time: datetime.time, duration_minutes: int
) -> List[str]:
    """Generuje listę godzin co `duration_minutes` minut między start a end."""
    start_min = _time_to_minutes(start_time)
    end_min = _time_to_minutes(end_time)
    slots = []

    current = start_min
    while current + duration_minutes <= end_min:
        h = current // 60
        m = current % 60
        slots.append(f"{h:02d}:{m:02d}")
        current += duration_minutes

    return slots


def _time_to_minutes(t) -> int:
    """Konwertuje czas na minuty od północy."""
    if isinstance(t, str):
        h, m = t.split(":")
        return int(h) * 60 + int(m)
    return t.hour * 60 + t.minute


def _is_time_overlap(
    slot_start_str: str,
    slot_duration: int,
    other_start,
    other_duration_or_end,
) -> bool:
    """
    Sprawdza, czy slot (slot_start_str + slot_duration) nachodzi na inny przedział.
    `other_duration_or_end` może być:
      - int (duration w minutach) — wtedy traktowane jako czas trwania
      - time / str (czas zakończenia) — wtedy traktowane jako koniec przedziału
    """
    slot_start = _time_to_minutes(slot_start_str)
    slot_end = slot_start + slot_duration

    if isinstance(other_duration_or_end, int):
        other_start_min = _time_to_minutes(other_start)
        other_end_min = other_start_min + other_duration_or_end
    else:
        other_start_min = _time_to_minutes(other_start)
        other_end_min = _time_to_minutes(other_duration_or_end)

    # Nachodzenie: slot_start < other_end AND slot_end > other_start
    return slot_start < other_end_min and slot_end > other_start_min
