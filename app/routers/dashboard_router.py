import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import get_db
from app.models import Provider, WorkingHour, Booking, BlockedSlot, Service
from app.schemas import (
    SettingsUpdate,
    HoursUpdate,
    BlockSlotRequest,
    ServiceCreate,
)
from app.payments import (
    create_subscription_checkout,
    cancel_subscription,
    is_stripe_configured,
    SUBSCRIPTION_PRICE_PLN,
)
from app.config import SITE_URL, TRIAL_DAYS

logger = logging.getLogger("rezerwuj.dashboard")
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ===== Helper =====

def _get_provider(request: Request) -> Provider:
    """Pobiera provider z request.state (ustawiony przez middleware w main.py)."""
    provider = getattr(request.state, "provider", None)
    if not provider:
        raise HTTPException(status_code=401, detail="Nie jesteś zalogowany")
    return provider


def _get_dashboard_context(request: Request) -> dict:
    """Zwraca kontekst base dla dashboardu."""
    provider = _get_provider(request)
    return {
        "request": request,
        "provider": provider,
        "site_url": SITE_URL,
    }


# ===== Strony ====

@router.get("/dashboard")
def dashboard_home(request: Request):
    """Strona główna dashboardu — nadchodzące rezerwacje."""
    provider = _get_provider(request)
    db = next(get_db())

    today = datetime.date.today()

    # Nadchodzące rezerwacje (dziś i w przyszłości)
    upcoming = (
        db.query(Booking)
        .filter(
            Booking.provider_id == provider.id,
            Booking.booking_date >= today,
            Booking.status == "confirmed",
        )
        .order_by(Booking.booking_date, Booking.booking_time)
        .limit(20)
        .all()
    )

    # Dziś
    today_bookings = [b for b in upcoming if b.booking_date == today]
    # Przyszłe
    future_bookings = [b for b in upcoming if b.booking_date > today]

    # Statystyki
    total_bookings = (
        db.query(Booking)
        .filter(Booking.provider_id == provider.id)
        .count()
    )
    completed_bookings = (
        db.query(Booking)
        .filter(
            Booking.provider_id == provider.id,
            Booking.status == "confirmed",
            Booking.booking_date < today,
        )
        .count()
    )

    db.close()

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            ** _get_dashboard_context(request),
            "today_bookings": today_bookings,
            "future_bookings": future_bookings,
            "upcoming_count": len(upcoming),
            "total_bookings": total_bookings,
            "completed_bookings": completed_bookings,
        },
    )


@router.get("/dashboard/rezerwacje")
def bookings_list(request: Request):
    """Lista wszystkich rezerwacji."""
    provider = _get_provider(request)
    db = next(get_db())

    bookings = (
        db.query(Booking)
        .filter(Booking.provider_id == provider.id)
        .order_by(Booking.booking_date.desc(), Booking.booking_time.desc())
        .all()
    )

    db.close()

    return templates.TemplateResponse(
        "dashboard/bookings.html",
        {
            ** _get_dashboard_context(request),
            "bookings": bookings,
        },
    )


@router.post("/dashboard/rezerwacje/{booking_id}/anuluj")
def cancel_booking(booking_id: int, request: Request, db: Session = Depends(get_db)):
    """Anulowanie rezerwacji."""
    provider = _get_provider(request)
    booking = (
        db.query(Booking)
        .filter(
            Booking.id == booking_id,
            Booking.provider_id == provider.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Rezerwacja nie istnieje")

    booking.status = "cancelled"
    db.commit()

    return RedirectResponse(url="/dashboard/rezerwacje", status_code=302)


@router.post("/dashboard/rezerwacje/{booking_id}/zakoncz")
def complete_booking(booking_id: int, request: Request, db: Session = Depends(get_db)):
    """Oznaczenie rezerwacji jako zakończonej."""
    provider = _get_provider(request)
    booking = (
        db.query(Booking)
        .filter(
            Booking.id == booking_id,
            Booking.provider_id == provider.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Rezerwacja nie istnieje")

    booking.status = "completed"
    db.commit()

    return RedirectResponse(url="/dashboard/rezerwacje", status_code=302)


# ===== Ustawienia =====

@router.get("/dashboard/ustawienia")
def settings_page(request: Request):
    """Strona ustawień."""
    return templates.TemplateResponse(
        "dashboard/settings.html",
        {
            **_get_dashboard_context(request),
            "today": datetime.date.today(),
        },
    )


@router.post("/dashboard/ustawienia")
async def update_settings(request: Request, db: Session = Depends(get_db)):
    """Zapisuje ustawienia profilu."""
    provider = _get_provider(request)
    form = await request.form()

    try:
        settings = SettingsUpdate(
            name=form.get("name") or None,
            phone=form.get("phone") or None,
            company_name=form.get("company_name") or None,
            service_duration=int(form.get("service_duration", 0)) if form.get("service_duration") else None,
            require_deposit=form.get("require_deposit") == "on",
            deposit_amount=int(float(form.get("deposit_amount", 0)) * 100) if form.get("deposit_amount") else None,
        )
    except (ValueError, TypeError) as e:
        return templates.TemplateResponse(
            "dashboard/settings.html",
            {
                **_get_dashboard_context(request),
                "error": f"Nieprawidłowa wartość: {e}",
            },
        )

    if settings.name:
        provider.name = settings.name
    if settings.phone is not None:
        provider.phone = settings.phone
    if settings.company_name is not None:
        provider.company_name = settings.company_name
    if settings.service_duration is not None:
        provider.service_duration = settings.service_duration
    if settings.require_deposit is not None:
        provider.require_deposit = settings.require_deposit
    if settings.deposit_amount is not None:
        provider.deposit_amount = settings.deposit_amount

    db.commit()
    return templates.TemplateResponse(
        "dashboard/settings.html",
        {
            **_get_dashboard_context(request),
            "success": "Ustawienia zostały zapisane",
        },
    )


@router.post("/dashboard/godziny-pracy")
async def update_hours(request: Request, db: Session = Depends(get_db)):
    """Zapisuje godziny pracy."""
    provider = _get_provider(request)
    form = await request.form()

    days_data = {}
    for key, value in form.items():
        if key.startswith("day_"):
            parts = key.split("_")
            if len(parts) >= 3:
                day_idx = parts[1]
                field = parts[2]
                if day_idx not in days_data:
                    days_data[day_idx] = {}
                days_data[day_idx][field] = value

    for day_str, data in days_data.items():
        try:
            day = int(day_str)
        except ValueError:
            continue

        is_working = data.get("is_working") == "on"

        wh = (
            db.query(WorkingHour)
            .filter(
                WorkingHour.provider_id == provider.id,
                WorkingHour.day_of_week == day,
            )
            .first()
        )

        if not wh:
            wh = WorkingHour(
                provider_id=provider.id,
                day_of_week=day,
            )
            db.add(wh)

        wh.is_working = is_working
        if is_working:
            wh.start_time = _parse_time(data.get("start_time", "09:00"))
            wh.end_time = _parse_time(data.get("end_time", "17:00"))
            wh.break_start = _parse_time(data.get("break_start", ""))
            wh.break_end = _parse_time(data.get("break_end", ""))
        else:
            wh.start_time = None
            wh.end_time = None
            wh.break_start = None
            wh.break_end = None

    db.commit()
    return templates.TemplateResponse(
        "dashboard/settings.html",
        {
            **_get_dashboard_context(request),
            "success": "Godziny pracy zostały zapisane",
        },
    )


def _parse_time(value: str):
    """Parsuje string 'HH:MM' na obiekt time."""
    if not value or ":" not in value:
        return None
    try:
        h, m = value.split(":")
        return datetime.time(int(h), int(m))
    except (ValueError, TypeError):
        return None


# ===== Blokowanie terminów =====

@router.post("/dashboard/blokuj")
async def block_slot(request: Request, db: Session = Depends(get_db)):
    """Blokuje termin (urlop, przerwa)."""
    provider = _get_provider(request)
    form = await request.form()

    try:
        block_data = BlockSlotRequest(
            block_date=form.get("block_date", ""),
            start_time=form.get("start_time", ""),
            end_time=form.get("end_time", ""),
            reason=form.get("reason", ""),
        )
    except ValueError as e:
        return templates.TemplateResponse(
            "dashboard/settings.html",
            {
                **_get_dashboard_context(request),
                "error": f"Nieprawidłowe dane blokady: {e}",
            },
        )

    try:
        block_date = datetime.date.fromisoformat(block_data.block_date)
        start = datetime.time.fromisoformat(block_data.start_time)
        end = datetime.time.fromisoformat(block_data.end_time)
    except ValueError:
        return templates.TemplateResponse(
            "dashboard/settings.html",
            {
                **_get_dashboard_context(request),
                "error": "Nieprawidłowy format daty lub czasu",
            },
        )

    if end <= start:
        return templates.TemplateResponse(
            "dashboard/settings.html",
            {
                **_get_dashboard_context(request),
                "error": "Czas zakończenia musi być późniejszy niż rozpoczęcia",
            },
        )

    blocked = BlockedSlot(
        provider_id=provider.id,
        block_date=block_date,
        start_time=start,
        end_time=end,
        reason=block_data.reason,
    )
    db.add(blocked)
    db.commit()

    return templates.TemplateResponse(
        "dashboard/settings.html",
        {
            **_get_dashboard_context(request),
            "success": "Termin został zablokowany",
        },
    )


@router.post("/dashboard/odblokuj/{block_id}")
def unblock_slot(block_id: int, request: Request, db: Session = Depends(get_db)):
    """Usuwa blokadę terminu."""
    provider = _get_provider(request)
    blocked = (
        db.query(BlockedSlot)
        .filter(
            BlockedSlot.id == block_id,
            BlockedSlot.provider_id == provider.id,
        )
        .first()
    )
    if not blocked:
        raise HTTPException(status_code=404, detail="Blokada nie istnieje")

    db.delete(blocked)
    db.commit()

    return RedirectResponse(url="/dashboard/ustawienia", status_code=302)


# ===== Płatności i subskrypcja =====

@router.get("/dashboard/platnosci")
def billing_page(request: Request, db: Session = Depends(get_db)):
    """Strona płatności i subskrypcji."""
    provider = _get_provider(request)

    trial_end_str = provider.trial_end.strftime("%d.%m.%Y") if provider.trial_end else "—"

    return templates.TemplateResponse(
        "dashboard/billing.html",
        {
            **_get_dashboard_context(request),
            "trial_end": trial_end_str,
            "trial_days_left": (
                (provider.trial_end - datetime.date.today()).days
                if provider.trial_end
                else 0
            ),
            "stripe_configured": is_stripe_configured(),
            "subscription_price_pln": SUBSCRIPTION_PRICE_PLN / 100,
            "subscription_status": provider.subscription_status,
            "stripe_publishable_key": "",  # niepotrzebne z Checkout Session
        },
    )


@router.post("/dashboard/subskrypcja/utworz")
def create_subscription(request: Request, db: Session = Depends(get_db)):
    """Tworzy sesję Stripe Checkout dla subskrypcji."""
    provider = _get_provider(request)

    checkout_url = create_subscription_checkout(provider)
    db.commit()

    if checkout_url:
        return RedirectResponse(url=checkout_url, status_code=302)

    # W trybie mock przekieruj na billing z sukcesem
    return RedirectResponse(url="/dashboard/platnosci?subscription=success", status_code=302)


@router.post("/dashboard/subskrypcja/anuluj")
def cancel_subscription_route(request: Request, db: Session = Depends(get_db)):
    """Anuluje subskrypcję."""
    provider = _get_provider(request)

    success = cancel_subscription(provider)
    db.commit()

    if success:
        return RedirectResponse(
            url="/dashboard/platnosci?subscription=cancelled",
            status_code=302,
        )
    return RedirectResponse(
        url="/dashboard/platnosci?error=Anulowanie nie powiodło się",
        status_code=302,
    )


# ===== Podgląd linku =====

@router.get("/dashboard/podglad")
def public_preview(request: Request):
    """Pokazuje link do publicznej strony rezerwacji."""
    provider = _get_provider(request)
    public_url = f"{SITE_URL}/{provider.slug}"

    return templates.TemplateResponse(
        "dashboard/preview.html",
        {
            **_get_dashboard_context(request),
            "public_url": public_url,
        },
    )
