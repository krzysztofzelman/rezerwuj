import datetime
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import rate_limit_default, rate_limit_booking
from app.models import ServiceProvider, Order, Service
from app.schemas import BookRequest
from app.utils import get_available_slots
from app.sms_mock import (
    send_booking_confirmation,
    send_new_booking_notification_to_provider_sms,
)
from app.email_mock import (
    send_booking_confirmation_email,
    send_new_booking_notification_to_provider,
)
from app.payments import create_deposit_checkout
from app.config import SITE_URL, RECAPTCHA_SITE_KEY, RECAPTCHA_SECRET_KEY

logger = logging.getLogger("napraw_mnie.public")
router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/{slug}")
def public_booking_page(slug: str, request: Request, db: Session = Depends(get_db)):
    """Publiczna strona rezerwacji dla danego usługodawcy."""
    # Zastrzeżone slugi — nie mogą kolidować z systemowymi ścieżkami
    RESERVED_SLUGS = {"dashboard", "admin", "auth", "static", "api", "stripe", "health"}
    if slug in RESERVED_SLUGS:
        return templates.TemplateResponse(
            "public/not_found.html",
            {"request": request},
            status_code=404,
        )

    provider = db.query(ServiceProvider).filter(ServiceProvider.slug == slug).first()
    if not provider:
        return templates.TemplateResponse(
            "public/not_found.html",
            {"request": request},
            status_code=404,
        )

    # Sprawdź czy serwis może przyjmować zlecenia
    if not provider.can_accept_bookings:
        return templates.TemplateResponse(
            "public/booking_closed.html",
            {"request": request, "provider": provider},
        )

    # Pobierz dni pracujące (dla oznaczenia w kalendarzu)
    working_days = []
    for wh in provider.working_hours:
        if wh.is_working:
            working_days.append(str(wh.day_of_week))

    return templates.TemplateResponse(
        "public/booking.html",
        {
            "request": request,
            "provider": provider,
            "working_days_json": json.dumps(working_days),
            "service_duration": provider.service_duration,
            "require_deposit": provider.require_deposit and provider.deposit_amount > 0,
            "deposit_amount_pln": (provider.deposit_amount or 0) / 100,
            "stripe_key": "",  # Frontend nie potrzebuje — używamy Checkout Session
            "site_url": SITE_URL,
            "recaptcha_site_key": RECAPTCHA_SITE_KEY,
        },
    )


@router.get("/api/{slug}/slots")
def get_slots(
    slug: str,
    date: str,
    service_id: int = 0,
    _rl: None = Depends(rate_limit_default),
    db: Session = Depends(get_db),
):
    """Zwraca dostępne sloty dla podanej daty (AJAX). Opcjonalnie `service_id` dla czasu trwania usługi."""
    provider = db.query(ServiceProvider).filter(ServiceProvider.slug == slug).first()
    if not provider or not provider.can_accept_bookings:
        return JSONResponse(content={"slots": [], "error": "Brak dostępnych terminów"})

    # Określ czas trwania: z usługi lub domyślny providera
    duration = provider.service_duration
    if service_id:
        svc = (
            db.query(Service)
            .filter(Service.id == service_id, Service.provider_id == provider.id, Service.is_active == True)  # noqa: E712
            .first()
        )
        if svc:
            duration = svc.duration

    try:
        target_date = datetime.date.fromisoformat(date)
    except ValueError:
        return JSONResponse(
            content={"slots": [], "error": "Nieprawidłowy format daty"},
            status_code=400,
        )

    # Nie pokazuj slotów w przeszłości
    if target_date < datetime.date.today():
        return JSONResponse(content={"slots": []})

    # Nie pokazuj slotów zbyt daleko w przyszłość
    max_date = datetime.date.today() + datetime.timedelta(days=60)
    if target_date > max_date:
        return JSONResponse(content={"slots": []})

    slots = get_available_slots(db, provider, target_date, duration=duration)
    return JSONResponse(content={"slots": slots})


@router.get("/api/{slug}/services")
def provider_services(
    slug: str,
    _rl: None = Depends(rate_limit_default),
    db: Session = Depends(get_db),
):
    """Zwraca aktywne usługi dla usługodawcy (AJAX)."""
    provider = db.query(ServiceProvider).filter(ServiceProvider.slug == slug).first()
    if not provider:
        return JSONResponse(content={"services": []})

    services = (
        db.query(Service)
        .filter(Service.provider_id == provider.id, Service.is_active == True)  # noqa: E712
        .order_by(Service.name)
        .all()
    )

    return JSONResponse(
        content={
            "services": [
                {
                    "id": s.id,
                    "name": s.name,
                    "duration": s.duration,
                    "price_pln": s.price / 100 if s.price else 0,
                }
                for s in services
            ]
        }
    )


@router.post("/api/{slug}/book")
async def create_booking(
    slug: str,
    request: Request,
    _rl: None = Depends(rate_limit_booking),
    db: Session = Depends(get_db),
):
    """Tworzy nową rezerwację."""
    provider = db.query(ServiceProvider).filter(ServiceProvider.slug == slug).first()
    if not provider or not provider.can_accept_bookings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usługodawca nie przyjmuje rezerwacji",
        )

    form = await request.json()

    # Weryfikacja reCAPTCHA
    if RECAPTCHA_SECRET_KEY:
        recaptcha_token = form.get("g_recaptcha_response", "")
        if not recaptcha_token:
            return JSONResponse(
                content={"success": False, "error": "Weryfikacja bezpieczeństwa nieudana. Odśwież stronę i spróbuj ponownie."},
                status_code=400,
            )
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data={
                    "secret": RECAPTCHA_SECRET_KEY,
                    "response": recaptcha_token,
                },
                timeout=10,
            )
            recaptcha_result = resp.json()
        if not recaptcha_result.get("success"):
            logger.warning("reCAPTCHA nieudana: %s", recaptcha_result.get("error-codes", []))
            return JSONResponse(
                content={"success": False, "error": "Weryfikacja bezpieczeństwa nieudana. Spróbuj ponownie."},
                status_code=400,
            )

    try:
        book_data = BookRequest(
            date=form.get("date", ""),
            time=form.get("time", ""),
            client_name=form.get("client_name", ""),
            client_surname=form.get("client_surname", ""),
            client_phone=form.get("client_phone", ""),
            client_email=form.get("client_email", ""),
        )
    except ValueError as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=400,
        )

    # Parsuj datę i czas
    try:
        booking_date = datetime.date.fromisoformat(book_data.date)
        booking_time = datetime.time.fromisoformat(book_data.time)
    except ValueError:
        return JSONResponse(
            content={"success": False, "error": "Nieprawidłowa data lub czas"},
            status_code=400,
        )

    # Sprawdź czy slot jest faktycznie dostępny
    available_slots = get_available_slots(db, provider, booking_date)
    if book_data.time not in available_slots:
        return JSONResponse(
            content={
                "success": False,
                "error": "Wybrany termin jest już zajęty. Wybierz inny.",
            },
            status_code=409,
        )

    # Utwórz rezerwację
    booking = Order(
        provider_id=provider.id,
        client_name=book_data.client_name,
        client_surname=book_data.client_surname,
        client_phone=book_data.client_phone,
        client_email=book_data.client_email,
        booking_date=booking_date,
        booking_time=booking_time,
        duration=provider.service_duration,
        status="confirmed",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    # Wyślij potwierdzenia (asynchronicznie — w tle)
    date_str = booking_date.strftime("%d.%m.%Y")
    time_str = booking_time.strftime("%H:%M")
    send_booking_confirmation(
        booking.client_phone,
        provider.name,
        date_str,
        time_str,
    )
    if booking.client_email:
        send_booking_confirmation_email(
            booking.client_email,
            booking.client_name,
            provider.name,
            date_str,
            time_str,
            provider.company_name,
        )

    # Powiadom usługodawcę o nowej rezerwacji — zawsze na jego adres e-mail
    send_new_booking_notification_to_provider(
        provider.email,
        provider.name,
        booking.client_name,
        booking.client_surname,
        booking.client_phone,
        date_str,
        time_str,
        company_name=provider.company_name,
    )

    # SMS do usługodawcy o nowej rezerwacji (jeśli podał numer telefonu)
    if provider.phone:
        send_new_booking_notification_to_provider_sms(
            provider.phone,
            provider.name,
            booking.client_name,
            booking.client_surname,
            date_str,
            time_str,
            company_name=provider.company_name,
        )

    # Jeśli wymagana zaliczka — utwórz Stripe Checkout
    payment_url = None
    if provider.require_deposit and provider.deposit_amount > 0:
        payment_url = create_deposit_checkout(booking, provider)

    return JSONResponse(
        content={
            "success": True,
            "booking_id": booking.id,
            "date": date_str,
            "time": time_str,
            "provider_name": provider.name,
            "payment_url": payment_url,
            "require_payment": payment_url is not None,
        }
    )


@router.get("/api/{slug}/payment-success/{booking_id}")
def payment_success(slug: str, booking_id: int, request: Request, db: Session = Depends(get_db)):
    """Strona po udanej płatności zaliczki."""
    booking = db.query(Order).filter(Order.id == booking_id).first()
    if not booking:
        return RedirectResponse(url=f"/{slug}")

    booking.paid = True
    db.commit()

    provider = db.query(ServiceProvider).filter(ServiceProvider.id == booking.provider_id).first()
    return templates.TemplateResponse(
        "public/confirmation.html",
        {
            "request": request,
            "provider": provider,
            "booking": booking,
            "paid": True,
        },
    )


@router.get("/api/{slug}/payment-cancel/{booking_id}")
def payment_cancel(slug: str, booking_id: int, request: Request, db: Session = Depends(get_db)):
    """Strona po anulowaniu płatności."""
    booking = db.query(Order).filter(Order.id == booking_id).first()
    if not booking:
        return RedirectResponse(url=f"/{slug}")

    provider = db.query(ServiceProvider).filter(ServiceProvider.id == booking.provider_id).first()
    return templates.TemplateResponse(
        "public/confirmation.html",
        {
            "request": request,
            "provider": provider,
            "booking": booking,
            "paid": False,
            "payment_cancelled": True,
        },
    )


@router.get("/api/{slug}/info")
def provider_info(
    slug: str,
    _rl: None = Depends(rate_limit_default),
    db: Session = Depends(get_db),
):
    """Zwraca podstawowe informacje o usługodawcy (AJAX)."""
    provider = db.query(ServiceProvider).filter(ServiceProvider.slug == slug).first()
    if not provider:
        return JSONResponse(content={"error": "Not found"}, status_code=404)

    return JSONResponse(
        content={
            "name": provider.name,
            "company_name": provider.company_name,
            "service_duration": provider.service_duration,
        }
    )
