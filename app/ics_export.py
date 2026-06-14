"""
Generator plików ICS (iCalendar) do eksportu do Google Calendar, Apple Calendar itp.
Nie wymaga zewnętrznych bibliotek — ICS to czysty tekst.
"""
import uuid
from datetime import date, datetime, time, timedelta, timezone


def _format_dt(d: date, t: time) -> str:
    """Zwraca datetime w formacie ICS: YYYYMMDDTHHMMSS"""
    dt = datetime.combine(d, t, tzinfo=timezone(timedelta(hours=1)))
    return dt.strftime("%Y%m%dT%H%M%S")


def _fold_line(line: str) -> str:
    """ICS wymaga linii nie dłuższych niż 75 znaków (z wyjątkiem initial indent)."""
    if len(line) <= 75:
        return line
    result = []
    while len(line) > 75:
        result.append(line[:75])
        line = " " + line[75:]  # kontynuacja z wcięciem
    result.append(line)
    return "\r\n".join(result)


def generate_booking_ics(
    client_name: str,
    client_surname: str,
    provider_name: str,
    provider_address: str,
    booking_date: date,
    booking_time: time,
    duration_minutes: int,
    service_name: str = "",
    company_name: str = "",
    booking_id: int = 0,
) -> str:
    """
    Generuje zawartość pliku .ics dla pojedynczej rezerwacji.
    Zwraca tekst gotowy do zwrócenia jako plik.
    """
    biz_name = company_name or provider_name
    dt_start = _format_dt(booking_date, booking_time)

    # Czas zakończenia
    end_dt = datetime.combine(booking_date, booking_time) + timedelta(minutes=duration_minutes)
    dt_end = end_dt.strftime("%Y%m%dT%H%M%S")

    summary = f"Wizyta u {biz_name}"
    if service_name:
        summary += f" – {service_name}"
    desc = (
        f"Rezerwacja u {biz_name}\n"
        f"Klient: {client_name} {client_surname}\n"
    )
    if service_name:
        desc += f"Usługa: {service_name}\n"
    if provider_address:
        desc += f"Adres: {provider_address}\n"
    desc += f"\n— System ServiceHub"

    uid = f"{booking_id or uuid.uuid4()}@servicehub.app"
    now = datetime.now(timezone(timedelta(hours=1))).strftime("%Y%m%dT%H%M%S")

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ServiceHub//PL",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        f"DTSTART:{dt_start}",
        f"DTEND:{dt_end}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{desc.replace(chr(10), '\\n')}",
        "TRANSP:OPAQUE",
        "END:VEVENT",
        "END:VCALENDAR",
    ]

    return "\r\n".join(_fold_line(l) for l in ics_lines)
