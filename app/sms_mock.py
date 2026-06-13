"""
Moduł SMS — w produkcji obsługuje SMSAPI.pl lub Twilio.
W trybie mock (domyślnym) loguje SMS do konsoli.
"""
import logging
from app.config import SMS_API_KEY, SMS_SENDER, SMS_MOCK

logger = logging.getLogger("rezerwuj.sms")


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

    # W produkcji tutaj byłoby wywołanie API SMSAPI.pl lub Twilio
    # Przykład dla SMSAPI.pl:
    # import requests
    # resp = requests.post(
    #     "https://api.smsapi.pl/sms.do",
    #     data={
    #         "to": phone_clean,
    #         "from": SMS_SENDER,
    #         "message": message,
    #         "format": "json",
    #     },
    #     auth=(SMS_API_KEY, ""),
    # )
    # return resp.status_code == 200

    logger.error(f"SMS API nie skonfigurowane — nie wysłano SMS do {phone_clean}")
    return False


def send_booking_confirmation(phone: str, provider_name: str, date: str, time: str) -> bool:
    """Wysyła potwierdzenie rezerwacji SMS-em."""
    message = (
        f"Potwierdzenie rezerwacji u {provider_name}.\n"
        f"Data: {date}\n"
        f"Godzina: {time}\n"
        f"Dziękujemy!"
    )
    return send_sms(phone, message)


def send_booking_reminder(phone: str, provider_name: str, date: str, time: str) -> bool:
    """Wysyła przypomnienie o rezerwacji (do użycia z harmonogramem)."""
    message = (
        f"Przypomnienie: masz rezerwację u {provider_name}\n"
        f"Data: {date}\n"
        f"Godzina: {time}\n"
        f"Do zobaczenia!"
    )
    return send_sms(phone, message)
