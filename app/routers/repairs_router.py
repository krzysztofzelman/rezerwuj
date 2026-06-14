"""Router B2C Marketplace — wyszukiwarka serwisów, składanie zleceń, tracking."""
import datetime
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import rate_limit_default
from app.models import (
    ServiceProvider,
    ServiceProviderLocation,
    Order,
    OrderStatus,
    DeliveryType,
)
from app.schemas import RepairSearchRequest, RepairCreateRequest
from app.sms_mock import send_sms
from app.email_mock import send_email
from app.config import SITE_URL

logger = logging.getLogger("napraw_mnie.repairs")
router = APIRouter(prefix="/api/repairs", tags=["repairs"])
templates = Jinja2Templates(directory="app/templates")

# Mapowanie DeliveryType na przyjazne etykiety
DELIVERY_LABELS = {
    "self_delivery": "Odbiór własny",
    "courier_pickup": "Kurier (odbiór i dostawa)",
    "home_visit": "Dojazd serwisanta",
}
DELIVERY_ICONS = {
    "self_delivery": "bi-shop",
    "courier_pickup": "bi-truck",
    "home_visit": "bi-house-check",
}


# ===== Strony HTML =====

@router.get("/search", response_class=HTMLResponse)
def repairs_search_page(request: Request):
    """Strona wyszukiwarki serwisów."""
    return templates.TemplateResponse(
        "public/repairs_search.html",
        {
            "request": request,
            "site_url": SITE_URL,
            "delivery_types": DeliveryType,
        },
    )


@router.get("/booking/{location_id}", response_class=HTMLResponse)
def repairs_booking_page(location_id: int, request: Request, db: Session = Depends(get_db)):
    """Strona formularza zgłoszenia naprawy dla wybranej lokalizacji."""
    location = (
        db.query(ServiceProviderLocation)
        .filter(ServiceProviderLocation.id == location_id, ServiceProviderLocation.is_online == True)  # noqa: E712
        .first()
    )
    if not location:
        return templates.TemplateResponse(
            "public/not_found.html",
            {"request": request},
            status_code=404,
        )

    provider = db.query(ServiceProvider).filter(ServiceProvider.id == location.provider_id).first()

    return templates.TemplateResponse(
        "public/repairs_booking.html",
        {
            "request": request,
            "location": location,
            "provider": provider,
            "delivery_types": json.loads(location.delivery_types or "[]"),
            "delivery_labels": DELIVERY_LABELS,
            "repair_price_pln": location.repair_price_pln,
            "site_url": SITE_URL,
        },
    )


@router.get("/{order_id}/tracking", response_class=HTMLResponse)
def repairs_tracking_page(order_id: int, request: Request, db: Session = Depends(get_db)):
    """Strona śledzenia zlecenia naprawy."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        return templates.TemplateResponse(
            "public/not_found.html",
            {"request": request},
            status_code=404,
        )

    provider = db.query(ServiceProvider).filter(ServiceProvider.id == order.provider_id).first()

    status_labels = {
        "pending": "Oczekuje na przyjęcie",
        "confirmed": "Przyjęto do naprawy",
        "in_progress": "W trakcie naprawy",
        "completed": "Gotowe do odbioru",
        "cancelled": "Anulowano",
    }

    # Oś czasu — generowana na podstawie statusu
    timeline = _build_timeline(order)

    return templates.TemplateResponse(
        "public/tracking.html",
        {
            "request": request,
            "order": order,
            "provider": provider,
            "status_label": status_labels.get(order.status_order.value, order.status_order.value),
            "timeline": timeline,
            "delivery_label": DELIVERY_LABELS.get(order.delivery_type, ""),
            "repair_cost_pln": order.repair_cost / 100 if order.repair_cost else 0,
            "courier_cost_pln": order.courier_cost / 100 if order.courier_cost else 0,
            "total_cost_pln": (order.repair_cost + order.courier_cost) / 100 if order.repair_cost else 0,
        },
    )


def _build_timeline(order: Order) -> list:
    """Buduje oś czasu statusów zlecenia."""
    timeline = []
    status_order = ["pending", "confirmed", "in_progress", "completed"]
    current_idx = status_order.index(order.status_order.value) if order.status_order.value in status_order else -1

    for idx, status_val in enumerate(status_order):
        is_past = idx <= current_idx and current_idx >= 0
        is_current = idx == current_idx

        # Przyporządkuj datę — używamy created_at dla pending,
        # booking_date dla confirmed, brak dla reszty (symulacja)
        date_str = ""
        if idx == 0:
            date_str = order.created_at.strftime("%d.%m.%Y") if order.created_at else ""
        elif idx == 1 and order.booking_date:
            date_str = order.booking_date.strftime("%d.%m.%Y")

        labels = {
            "pending": "Zgłoszenie wysłane",
            "confirmed": "Przyjęto do naprawy",
            "in_progress": "Naprawa w toku",
            "completed": "Gotowe do odbioru",
        }

        timeline.append({
            "status": status_val,
            "label": labels[status_val],
            "is_past": is_past,
            "is_current": is_current,
            "date": date_str,
        })

    if order.status_order.value == "cancelled":
        timeline.append({
            "status": "cancelled",
            "label": "Anulowano",
            "is_past": True,
            "is_current": False,
            "date": "",
        })

    return timeline


# ===== API JSON =====

@router.post("/search")
async def repairs_search(
    request: Request,
    _rl: None = Depends(rate_limit_default),
    db: Session = Depends(get_db),
):
    """Wyszukuje serwisy według kryteriów (JSON API)."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    if isinstance(body, dict) and body:
        search = RepairSearchRequest(**body)
    else:
        return JSONResponse(content={"results": [], "error": "Brak danych wyszukiwania"}, status_code=400)

    query = (
        db.query(ServiceProviderLocation)
        .join(ServiceProvider)
        .filter(
            ServiceProviderLocation.is_online == True,  # noqa: E712
            ServiceProvider.is_active == True,  # noqa: E712
        )
    )

    if search.city:
        query = query.filter(ServiceProviderLocation.city.ilike(f"%{search.city}%"))
    if search.district:
        query = query.filter(ServiceProviderLocation.district.ilike(f"%{search.district}%"))
    if search.delivery_type:
        # Szukaj lokalizacji które obsługują dany typ dostawy
        query = query.filter(ServiceProviderLocation.delivery_types.like(f"%{search.delivery_type}%"))

    locations = query.order_by(ServiceProviderLocation.avg_rating.desc()).limit(50).all()

    results = []
    for loc in locations:
        dt_list = loc.delivery_types_list
        provider = loc.provider

        results.append({
            "id": loc.id,
            "provider_id": provider.id,
            "provider_name": provider.company_name or provider.name,
            "city": loc.city,
            "district": loc.district,
            "address": loc.address,
            "repair_price_pln": loc.repair_price_pln,
            "avg_rating": loc.avg_rating or 0,
            "delivery_types": dt_list,
            "delivery_labels": [DELIVERY_LABELS.get(dt, dt) for dt in dt_list],
            "phone": provider.phone or "",
        })

    return JSONResponse(content={"results": results, "count": len(results)})


@router.post("/create")
async def create_repair_order(
    request: Request,
    _rl: None = Depends(rate_limit_default),
    db: Session = Depends(get_db),
):
    """Tworzy nowe zlecenie naprawy z marketplace B2C."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={"success": False, "error": "Nieprawidłowe dane JSON"},
            status_code=400,
        )

    try:
        data = RepairCreateRequest(**body)
    except ValueError as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=400,
        )

    # Pobierz lokalizację
    location = (
        db.query(ServiceProviderLocation)
        .filter(ServiceProviderLocation.id == data.location_id)
        .first()
    )
    if not location:
        return JSONResponse(
            content={"success": False, "error": "Lokalizacja nie istnieje"},
            status_code=404,
        )

    provider = db.query(ServiceProvider).filter(ServiceProvider.id == location.provider_id).first()
    if not provider or not provider.can_accept_bookings:
        return JSONResponse(
            content={"success": False, "error": "Serwis nie przyjmuje obecnie zgłoszeń"},
            status_code=400,
        )

    # Parsuj datę dostawy (opcjonalna)
    delivery_date = None
    if data.delivery_date_from:
        try:
            delivery_date = datetime.date.fromisoformat(data.delivery_date_from)
        except ValueError:
            pass

    # Utwórz zamówienie
    order = Order(
        provider_id=provider.id,
        client_name=data.client_name,
        client_surname=data.client_surname,
        client_phone=data.client_phone,
        client_email=data.client_email,
        device_type=data.device_type,
        brand=data.brand,
        model_name=data.model_name,
        serial_number=data.serial_number,
        problem_description=data.problem_description,
        booking_date=datetime.date.today(),
        booking_time=datetime.datetime.now().time(),
        duration=provider.service_duration,
        delivery_type=data.delivery_type,
        delivery_address=data.delivery_address,
        delivery_date_from=delivery_date,
        status_order=OrderStatus.pending,
        status="confirmed",
        repair_cost=location.repair_price,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # Wyślij notyfikacje
    date_str = datetime.date.today().strftime("%d.%m.%Y")
    time_str = datetime.datetime.now().strftime("%H:%M")
    biz_name = provider.company_name or provider.name

    # SMS do klienta — potwierdzenie
    _send_b2c_confirmation_sms(
        order.client_phone,
        biz_name,
        data.delivery_type,
    )

    # E-mail do klienta
    if order.client_email:
        _send_b2c_confirmation_email(
            order.client_email,
            order.client_name,
            biz_name,
            data.delivery_type,
            order.id,
        )

    # SMS z linkiem do trackowania
    tracking_url = f"{SITE_URL}/api/repairs/{order.id}/tracking"
    send_sms(
        order.client_phone,
        f"📱 Śledź status naprawy: {tracking_url}",
    )

    # Powiadomienie do providera
    _send_b2c_new_order_to_provider(
        provider.email,
        biz_name,
        order.client_name,
        order.client_surname,
        order.client_phone,
        data.device_type,
        data.brand,
        data.delivery_type,
    )

    return JSONResponse(
        content={
            "success": True,
            "order_id": order.id,
            "tracking_url": f"{SITE_URL}/api/repairs/{order.id}/tracking",
            "provider_name": biz_name,
        }
    )


# ===== Funkcje pomocnicze do notyfikacji =====

def _send_b2c_confirmation_sms(phone: str, provider_name: str, delivery_type: str):
    """SMS potwierdzający przyjęcie zlecenia B2C."""
    delivery_text = DELIVERY_LABELS.get(delivery_type, delivery_type)
    message = (
        f"✅ Zgłoszenie naprawy przyjęte – {provider_name}.\n"
        f"Dostawa: {delivery_text}\n"
        f"Skontaktujemy się po wstępnej diagnozie."
    )
    send_sms(phone, message)


def _send_b2c_confirmation_email(to: str, client_name: str, provider_name: str,
                                  delivery_type: str, order_id: int):
    """E-mail potwierdzający przyjęcie zlecenia B2C."""
    delivery_text = DELIVERY_LABELS.get(delivery_type, delivery_type)
    subject = f"Potwierdzenie zgłoszenia naprawy – {provider_name}"
    tracking_url = f"{SITE_URL}/api/repairs/{order_id}/tracking"
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
<h2 style="color:#0d6efd;">✅ Zgłoszenie naprawy przyjęte</h2>
<p>Dzień dobry, <strong>{client_name}</strong>!</p>
<p>Twoje zgłoszenie naprawy w <strong>{provider_name}</strong> zostało przyjęte.</p>
<table style="border-collapse:collapse;margin:16px 0;">
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Serwis</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{provider_name}</td></tr>
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Forma dostawy</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{delivery_text}</td></tr>
</table>
<p style="margin:24px 0;text-align:center;">
<a href="{tracking_url}" style="display:inline-block;background:#0d6efd;color:#fff;text-decoration:none;padding:12px 32px;border-radius:6px;font-weight:bold;">Śledź naprawę</a>
</p>
<p style="color:#6c757d;font-size:14px;">— {provider_name}</p></body></html>"""
    send_email(to, subject, html)


def _send_b2c_new_order_to_provider(
    to: str, provider_name: str, client_name: str, client_surname: str,
    client_phone: str, device_type: str, brand: str, delivery_type: str,
):
    """Powiadomienie e-mail do serwisu o nowym zleceniu z marketplace."""
    delivery_text = DELIVERY_LABELS.get(delivery_type, delivery_type)
    subject = f"🆕 Nowe zlecenie z rynku B2C – {client_name} {client_surname}"
    device_info = f"{brand} ({device_type})" if brand else device_type
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
<h2 style="color:#198754;">🆕 Nowe zlecenie z rynku B2C</h2>
<p>Dzień dobry, <strong>{provider_name}</strong>!</p>
<p>Otrzymałeś nowe zgłoszenie naprawy:</p>
<table style="border-collapse:collapse;margin:16px 0;">
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Klient</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{client_name} {client_surname}</td></tr>
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Telefon</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{client_phone}</td></tr>
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Sprzęt</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{device_info}</td></tr>
<tr><td style="padding:6px 12px;font-weight:bold;border:1px solid #dee2e6;">Dostawa</td><td style="padding:6px 12px;border:1px solid #dee2e6;">{delivery_text}</td></tr>
</table>
<p style="color:#6c757d;font-size:14px;">— Napraw Mnie</p></body></html>"""
    send_email(to, subject, html)
