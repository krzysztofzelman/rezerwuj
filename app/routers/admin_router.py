import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Provider, Booking
from app.config import SITE_URL

logger = logging.getLogger("rezerwuj.admin")
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_admin(request: Request) -> Provider:
    """Pobiera providera i sprawdza czy jest adminem."""
    provider = getattr(request.state, "provider", None)
    if not provider or not provider.is_admin:
        raise HTTPException(status_code=403, detail="Brak dostępu")
    return provider


@router.get("/admin")
def admin_home(request: Request, db: Session = Depends(get_db)):
    """Panel admina — lista wszystkich użytkowników."""
    _get_admin(request)

    users = (
        db.query(Provider)
        .options(selectinload(Provider.bookings))
        .order_by(Provider.created_at.desc())
        .all()
    )

    today = datetime.date.today()

    stats = []
    for u in users:
        total_bookings = len(u.bookings)
        upcoming = sum(
            1 for b in u.bookings
            if b.booking_date >= today and b.status == "confirmed"
        )
        stats.append({
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "slug": u.slug,
            "subscription": u.subscription_status,
            "trial_end": u.trial_end.strftime("%d.%m.%Y") if u.trial_end else "—",
            "is_active": u.is_active,
            "is_admin": u.is_admin,
            "total_bookings": total_bookings,
            "upcoming_bookings": upcoming,
            "created_at": u.created_at.strftime("%d.%m.%Y %H:%M") if u.created_at else "—",
        })

    total_users = len(users)
    active_users = sum(1 for u in users if u.is_active)
    total_bookings_all = sum(s["total_bookings"] for s in stats)

    return templates.TemplateResponse(
        "admin/index.html",
        {
            "request": request,
            "provider": _get_admin(request),
            "site_url": SITE_URL,
            "stats": stats,
            "total_users": total_users,
            "active_users": active_users,
            "total_bookings_all": total_bookings_all,
            "today": today,
        },
    )


@router.post("/admin/users/{user_id}/toggle-active")
def toggle_user_active(user_id: int, request: Request, db: Session = Depends(get_db)):
    """Aktywuje/dezaktywuje użytkownika."""
    _get_admin(request)

    user = db.query(Provider).filter(Provider.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie istnieje")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Nie możesz dezaktywować admina")

    user.is_active = not user.is_active
    db.commit()
    logger.info(f"Admin zmienił status użytkownika {user.email}: is_active={user.is_active}")

    return RedirectResponse(url="/admin", status_code=302)
