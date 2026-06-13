import datetime
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Provider, Booking
from app.schemas import BookRequest
from app.utils import get_available_slots
from app.sms_mock import send_booking_confirmation
from app.payments import create_deposit_checkout, is_stripe_configured
from app.config import SITE_URL

logger = logging.getLogger("rezerwuj.public")
router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/{slug}")
def public_booking_page(slug: str, request: Request, db: Session = Depends(get_db)):
    """Publiczna strona rezerwacji dla danego usługodawcy."""
    provider = db.query(Provider).filter(Provider.slug == slug).first()
    if not provider:
        return templates.TemplateResponse(
            "public/not_found.html",
            {"request": request},
            status_code=404,
        )

    # Sprawdź czy usługodawca może przyjmować rezerwacje
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
        },
    )


@router.get("/api/{slug}/slots")
def get_slots(
    slug: str,
    date: str,
    db: Session = Depends(get_db),
):
    """Zwraca dostępne sloty dla podanej daty (AJAX)."""
    provider = db.query(Provider).filter(Provider.slug == slug).first()
    if not provider or not provider.can_accept_bookings:
        return JSONResponse(content={"slots": [], "error": "Brak dostępnych terminów"})

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

    slots = get_available_slots(db, provider, target_date)
    return JSONResponse(content={"slots": slots})


@router.post("/api/{slug}/book")
async def create_booking(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Tworzy nową rezerwację."""
    provider = db.query(Provider).filter(Provider.slug == slug).first()
    if not provider or not provider.can_accept_bookings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usługodawca nie przyjmuje rezerwacji",
        )

    form = await request.json()

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
    booking = Booking(
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

    # Wyślij SMS potwierdzający (asynchronicznie — w tle)
    date_str = booking_date.strftime("%d.%m.%Y")
    time_str = booking_time.strftime("%H:%M")
    send_booking_confirmation(
        booking.client_phone,
        provider.name,
        date_str,
        time_str,
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
def payment_success(slug: str, booking_id: int, db: Session = Depends(get_db)):
    """Strona po udanej płatności zaliczki."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        return RedirectResponse(url=f"/{slug}")

    booking.paid = True
    db.commit()

    provider = db.query(Provider).filter(Provider.id == booking.provider_id).first()
    return templates.TemplateResponse(
        "public/confirmation.html",
        {
            "request": Request,
            "provider": provider,
            "booking": booking,
            "paid": True,
        },
    )


@router.get("/api/{slug}/payment-cancel/{booking_id}")
def payment_cancel(slug: str, booking_id: int, db: Session = Depends(get_db)):
    """Strona po anulowaniu płatności."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        return RedirectResponse(url=f"/{slug}")

    provider = db.query(Provider).filter(Provider.id == booking.provider_id).first()
    return templates.TemplateResponse(
        "public/confirmation.html",
        {
            "request": Request,
            "provider": provider,
            "booking": booking,
            "paid": False,
            "payment_cancelled": True,
        },
    )


@router.get("/api/{slug}/info")
def provider_info(slug: str, db: Session = Depends(get_db)):
    """Zwraca podstawowe informacje o usługodawcy (AJAX)."""
    provider = db.query(Provider).filter(Provider.slug == slug).first()
    if not provider:
        return JSONResponse(content={"error": "Not found"}, status_code=404)

    return JSONResponse(
        content={
            "name": provider.name,
            "company_name": provider.company_name,
            "service_duration": provider.service_duration,
        }
    )
