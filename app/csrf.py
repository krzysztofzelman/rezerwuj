"""Ochrona CSRF — Double Submit Cookie Pattern.

Token CSRF jest przechowywany w ciasteczku (odczytywalnym przez JS)
i przesyłany jako nagłówek X-CSRF-Token przy każdym formularzu POST.

Schemat:
1. GET: middleware generuje token, zapisuje w request.state.csrf_token (dla szablonu),
   a po wygenerowaniu odpowiedzi ustawia podpisany token jako ciasteczko
2. POST: middleware odczytuje ciasteczko, weryfikuje podpis, porównuje z nagłówkiem
3. JS na każdej stronie odczytuje ciasteczko i dodaje jako nagłówek do formularzy
"""

import hmac
import secrets
import time
from typing import Optional

from fastapi import Request, HTTPException
from starlette.responses import Response

from app.config import SECRET_KEY

CSRF_COOKIE_NAME = "csrf_token"
CSRF_FIELD_NAME = "_csrf_token"
CSRF_TOKEN_TTL = 7200  # 2 godziny


def generate_raw_token() -> str:
    """Generuje losowy token CSRF."""
    return secrets.token_hex(32)


def sign_token(raw_token: str) -> str:
    """Podpisuje token HMAC-SHA256 z timestamp window."""
    window = int(time.time()) // CSRF_TOKEN_TTL
    msg = f"{raw_token}:{window}"
    sig = hmac.new(SECRET_KEY.encode(), msg.encode(), "sha256").hexdigest()[:16]
    return f"{raw_token}.{sig}"


def unsign_token(signed: str) -> Optional[str]:
    """Weryfikuje podpis i zwraca surowy token lub None."""
    try:
        raw, sig = signed.split(".", 1)
    except ValueError:
        return None

    for offset in (0, 1):  # bieżące i poprzednie okno czasowe
        window = int(time.time()) // CSRF_TOKEN_TTL - offset
        expected = hmac.new(
            SECRET_KEY.encode(),
            f"{raw}:{window}".encode(),
            "sha256",
        ).hexdigest()[:16]
        if hmac.compare_digest(expected, sig):
            return raw
    return None


def verify_csrf(request: Request) -> None:
    """Weryfikuje token CSRF z nagłówka względem ciasteczka.

    Wywoływana w middleware dla POST/PUT/DELETE.
    """
    if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
        return

    # Pomiń dla webhooka Stripe (zewnętrzne żądanie)
    if request.url.path.startswith("/stripe/"):
        return

    # Pobierz podpisany token z ciasteczka
    signed_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    if not signed_cookie:
        raise HTTPException(status_code=403, detail="Brak ciasteczka CSRF")

    # Wyciągnij surowy token z podpisanego ciasteczka
    expected_raw = unsign_token(signed_cookie)
    if not expected_raw:
        raise HTTPException(status_code=403, detail="Nieprawidłowy lub wygasły token CSRF")

    # Pobierz token z nagłówka (ustawiany przez JS)
    form_token = request.headers.get("X-CSRF-Token", "")

    if not form_token:
        raise HTTPException(status_code=403, detail="Brak tokenu CSRF w nagłówku X-CSRF-Token")

    # Porównaj bezpiecznie
    if not hmac.compare_digest(expected_raw, form_token):
        raise HTTPException(status_code=403, detail="Nieprawidłowy token CSRF")

    # Zachowaj token w stanie na wypadek potrzeby
    request.state.csrf_verified = True
