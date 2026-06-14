"""
Moduł SMS — w produkcji obsługuje SMSAPI.pl.
W trybie mock (domyślnym) loguje SMS do konsoli.
"""
import logging

import httpx

from app.config import SMS_API_KEY, SMS_SENDER, SMS_MOCK

logger = logging.getLogger("napraw_mnie.sms")

SMSAPI_URL = "https://api.smsapi.pl/sms.do"


def send_sms(phone: str, message: str) -> bool:
    """
    Wysyła SMS o treści `message` na numer `phone`.
    W trybie mock tylko loguje.
    Zwraca True jeśli wysłano (lub zamockowano) pomyślnie.
    """
    if not phone:
        logger.warning("Próba wysłania SMS bez numeru telefonu")
        return False

    phone_clean = phone.strip()

    if SMS_MOCK:
        logger.info(
            "=== MOCK SMS ===\n"
            f"  Do: {phone_clean}\n"
            f"  Nadawca: {SMS_SENDER}\n"
            f"  Treść: {message}\n"
            "=== KONIEC ==="
        )
        return True

    if not SMS_API_KEY:
        logger.error("SMS_API_KEY nie skonfigurowane — nie wysłano SMS do %s", phone_clean)
        return False

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                SMSAPI_URL,
                data={
                    "to": phone_clean,
                    "from": SMS_SENDER,
                    "message": message,
                    "format": "json",
                },
                headers={"Authorization": f"Bearer {SMS_API_KEY}"},
            )
        if resp.status_code == 200:
            logger.info("SMS wysłany do %s: %s", phone_clean, message[:50])
            return True
        else:
            logger.error(
                "SMSAPI błąd (%d) dla %s: %s",
                resp.status_code,
                phone_clean,
                resp.text,
            )
            return False
    except Exception as e:
        logger.error("Błąd wysyłki SMS do %s: %s", phone_clean, e)
        return False


def send_booking_confirmation(phone: str, provider_name: str, date: str, time: str) -> bool:
    """Wysyła potwierdzenie przyjęcia zlecenia serwisowego SMS-em do klienta."""
    message = (
        f"Potwierdzenie przyjęcia zlecenia serwisowego – {provider_name}.\n"
        f"Data: {date}\n"
        f"Godzina: {time}\n"
        f"Skontaktujemy się po diagnozie."
    )
    return send_sms(phone, message)


def send_booking_reminder(phone: str, provider_name: str, date: str, time: str) -> bool:
    """Wysyła przypomnienie o zleceniu serwisowym SMS-em do klienta."""
    message = (
        f"Przypomnienie: Twoje zlecenie serwisowe w {provider_name}\n"
        f"Data: {date}\n"
        f"Godzina: {time}\n"
        f"Status naprawy możesz sprawdzić online."
    )
    return send_sms(phone, message)


def send_new_booking_notification_to_provider_sms(
    phone: str,
    provider_name: str,
    client_name: str,
    client_surname: str,
    date: str,
    time: str,
    company_name: str = "",
) -> bool:
    """Wysyła SMS do serwisu o nowym zleceniu."""
    biz_name = company_name or provider_name
    message = (
        f"Nowe zlecenie serwisowe!\n"
        f"Klient: {client_name} {client_surname}\n"
        f"Data: {date}\n"
        f"Godzina: {time}\n"
        f"— {biz_name}"
    )
    return send_sms(phone, message)
