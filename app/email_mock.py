"""
Moduł e-mail — w produkcji wysyła przez SMTP (smtplib).
W trybie mock (domyślnym) loguje e-mail do konsoli.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_FROM,
    EMAIL_MOCK,
    SITE_URL,
)

logger = logging.getLogger("servicehub.email")


def send_email(to: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """
    Wysyła e-mail na adres `to` z podanym tematem i treścią HTML.
    W trybie mock tylko loguje.
    Zwraca True jeśli wysłano (lub zamockowano) pomyślnie.
    """
    if not to:
        logger.warning("Próba wysłania e-mail bez adresu")
        return False

    to_clean = to.strip().lower()

    if EMAIL_MOCK:
        logger.info(
            "=== MOCK E-MAIL ===\n"
            f"  Do: {to_clean}\n"
            f"  Temat: {subject}\n"
            f"  Treść HTML: {html_body[:500]}...\n"
            "=== KONIEC ==="
        )
        return True

    if not SMTP_HOST or not SMTP_USER:
        logger.error("SMTP nie skonfigurowane — nie wysłano e-mail do %s", to_clean)
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_FROM
        msg["To"] = to_clean
        msg["Subject"] = subject

        text_part = MIMEText(text_body or html_body.replace("<br>", "\n").replace("</p>", "\n").replace("<[^>]+>", ""), "plain", "utf-8")
        html_part = MIMEText(html_body, "html", "utf-8")
        msg.attach(text_part)
        msg.attach(html_part)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if SMTP_PORT == 587:
                server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        logger.info("E-mail wysłany do %s: %s", to_clean, subject)
        return True
    except Exception as e:
        logger.error("Błąd wysyłki e-mail do %s: %s", to_clean, e)
        return False


def send_booking_confirmation_email(
    to: str,
    client_name: str,
    provider_name: str,
    date: str,
    time: str,
    company_name: str = "",
) -> bool:
    """Wysyła potwierdzenie przyjęcia zlecenia serwisowego e-mailem."""
    biz_name = company_name or provider_name
    subject = f"Potwierdzenie przyjęcia zlecenia – {biz_name}"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
<h2 style="color:#0d6efd;">✅ Zlecenie serwisowe przyjęte</h2>
<p>Dzień dobry, <strong>{client_name}</strong>!</p>
<p>Twoje zlecenie serwisowe w <strong>{biz_name}</strong> zostało przyjęte.</p>
<table style="border-collapse:collapse;margin:16px 0;">
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Data przyjęcia</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{date}</td></tr>
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Godzina</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{time}</td></tr>
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Serwis</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{biz_name}</td></tr>
</table>
<p style="color:#6c757d;font-size:14px;">Poinformujemy Cię o postępie naprawy.<br>— {biz_name}</p></body></html>"""
    return send_email(to, subject, html)


def send_booking_reminder_email(
    to: str,
    client_name: str,
    provider_name: str,
    date: str,
    time: str,
    company_name: str = "",
) -> bool:
    """Wysyła przypomnienie o zleceniu serwisowym (do użycia z harmonogramem)."""
    biz_name = company_name or provider_name
    subject = f"Przypomnienie: zlecenie serwisowe w {biz_name} jutro"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
<h2 style="color:#0d6efd;">⏰ Przypomnienie o zleceniu serwisowym</h2>
<p>Dzień dobry, <strong>{client_name}</strong>!</p>
<p>Przypominamy o Twoim zleceniu serwisowym w <strong>{biz_name}</strong>:</p>
<table style="border-collapse:collapse;margin:16px 0;">
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Data</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{date}</td></tr>
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Godzina</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{time}</td></tr>
</table>
<p style="color:#6c757d;font-size:14px;">Twój sprzęt jest w trakcie naprawy.<br>— {biz_name}</p></body></html>"""
    return send_email(to, subject, html)


def send_new_booking_notification_to_provider(
    to: str,
    provider_name: str,
    client_name: str,
    client_surname: str,
    client_phone: str,
    date: str,
    time: str,
    service_name: str = "",
    company_name: str = "",
) -> bool:
    """Wysyła powiadomienie do serwisu o nowym zleceniu."""
    biz_name = company_name or provider_name
    subject = f"🔔 Nowe zlecenie serwisowe! {date} {time} – {client_name} {client_surname}"
    svc_line = f"<tr><td style=\"padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;\">Usługa</td><td style=\"padding:6px 12px;border:1px solid #dee2e6;\">{service_name}</td></tr>\n" if service_name else ""
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
<h2 style="color:#198754;">🆕 Nowe zlecenie serwisowe</h2>
<p>Dzień dobry, <strong>{biz_name}</strong>!</p>
<p>Masz nowe zlecenie od klienta:</p>
<table style="border-collapse:collapse;margin:16px 0;">
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Imię</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{client_name}</td></tr>
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Nazwisko</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{client_surname}</td></tr>
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Telefon</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{client_phone}</td></tr>
{svc_line}<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Data przyjęcia</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{date}</td></tr>
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Godzina</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{time}</td></tr>
</table>
<p style="margin:24px 0;text-align:center;">
<a href="{SITE_URL}/dashboard/zlecenia" style="display:inline-block;background:#198754;color:#fff;text-decoration:none;padding:12px 32px;border-radius:6px;font-weight:bold;">Zobacz w panelu</a>
</p>
<p style="color:#6c757d;font-size:14px;">— ServiceHub</p></body></html>"""
    return send_email(to, subject, html)


def send_password_reset_email(to: str, reset_url: str) -> bool:
    """Wysyła link do resetu hasła."""
    subject = "Resetowanie hasła — ServiceHub"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
<h2 style="color:#0d6efd;">🔑 Resetowanie hasła</h2>
<p>Otrzymaliśmy prośbę o zresetowanie hasła dla Twojego konta w systemie <strong>ServiceHub</strong>.</p>
<p style="margin:24px 0;text-align:center;">
<a href="{reset_url}" style="display:inline-block;background:#0d6efd;color:#fff;text-decoration:none;padding:12px 32px;border-radius:6px;font-weight:bold;">Zresetuj hasło</a>
</p>
<p style="color:#6c757d;font-size:13px;">Link wygaśnie za 1 godzinę. Jeśli nie prosiłeś o reset hasła, zignoruj tę wiadomość.</p>
<hr style="border:none;border-top:1px solid #dee2e6;margin:16px 0;">
<p style="color:#6c757d;font-size:12px;">ServiceHub — {SITE_URL}</p></body></html>"""
    return send_email(to, subject, html)
