import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Provider
from app.schemas import RegisterRequest, LoginRequest
from app.auth import hash_password, verify_password, create_access_token
from app.config import TRIAL_DAYS

logger = logging.getLogger("rezerwuj.auth")
router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


def _set_auth_cookie(response: RedirectResponse, token: str) -> None:
    """Ustawia ciasteczko z tokenem JWT."""
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        max_age=72 * 3600,  # 72h
        samesite="lax",
        secure=False,  # True w produkcji z HTTPS
    )


@router.get("/rejestracja")
def register_page(request: Request):
    """Strona rejestracji."""
    return templates.TemplateResponse(
        "dashboard/register.html", {"request": request}
    )


@router.post("/rejestracja")
async def register(
    request: Request,
    db: Session = Depends(get_db),
):
    """Rejestracja nowego usługodawcy."""
    form = await request.form()
    try:
        reg_data = RegisterRequest(
            email=form.get("email", ""),
            password=form.get("password", ""),
            name=form.get("name", ""),
            slug=form.get("slug", ""),
        )
    except ValueError as e:
        return templates.TemplateResponse(
            "dashboard/register.html",
            {"request": request, "error": str(e)},
        )

    # Sprawdź czy email już istnieje
    existing = db.query(Provider).filter(Provider.email == reg_data.email).first()
    if existing:
        return templates.TemplateResponse(
            "dashboard/register.html",
            {"request": request, "error": "Ten adres e-mail jest już zarejestrowany"},
        )

    # Sprawdź czy slug już istnieje
    existing_slug = db.query(Provider).filter(Provider.slug == reg_data.slug).first()
    if existing_slug:
        return templates.TemplateResponse(
            "dashboard/register.html",
            {
                "request": request,
                "error": "Ten identyfikator (slug) jest już zajęty. Wybierz inny.",
            },
        )

    # Utwórz konto z trialem
    today = datetime.date.today()
    trial_end_date = today + datetime.timedelta(days=TRIAL_DAYS)

    provider = Provider(
        email=reg_data.email,
        password_hash=hash_password(reg_data.password),
        name=reg_data.name,
        slug=reg_data.slug,
        subscription_status="trial",
        trial_start=today,
        trial_end=trial_end_date,
        is_active=True,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)

    # Zaloguj od razu
    token = create_access_token(provider.id)
    response = RedirectResponse(url="/dashboard", status_code=302)

    # Ustaw domyślne godziny pracy (pon-pt 9:00-17:00)
    _create_default_hours(db, provider)

    _set_auth_cookie(response, token)
    logger.info(f"Nowy użytkownik zarejestrowany: {provider.email} (slug={provider.slug})")
    return response


def _create_default_hours(db: Session, provider: Provider) -> None:
    """Tworzy domyślne godziny pracy: pon-pt 9:00-17:00 z przerwą 12:00-13:00."""
    from app.models import WorkingHour

    for day in range(5):  # 0=Pon, 4=Piątek
        wh = WorkingHour(
            provider_id=provider.id,
            day_of_week=day,
            is_working=True,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(17, 0),
            break_start=datetime.time(12, 0),
            break_end=datetime.time(13, 0),
        )
        db.add(wh)

    # Weekend — niepracujące
    for day in (5, 6):
        wh = WorkingHour(
            provider_id=provider.id,
            day_of_week=day,
            is_working=False,
        )
        db.add(wh)

    db.commit()


@router.get("/logowanie")
def login_page(request: Request):
    """Strona logowania."""
    return templates.TemplateResponse(
        "dashboard/login.html", {"request": request}
    )


@router.post("/logowanie")
async def login(
    request: Request,
    db: Session = Depends(get_db),
):
    """Logowanie usługodawcy."""
    form = await request.form()
    try:
        login_data = LoginRequest(
            email=form.get("email", ""),
            password=form.get("password", ""),
        )
    except ValueError as e:
        return templates.TemplateResponse(
            "dashboard/login.html",
            {"request": request, "error": str(e)},
        )

    provider = (
        db.query(Provider)
        .filter(Provider.email == login_data.email)
        .first()
    )

    if not provider or not verify_password(login_data.password, provider.password_hash):
        return templates.TemplateResponse(
            "dashboard/login.html",
            {"request": request, "error": "Nieprawidłowy e-mail lub hasło"},
        )

    token = create_access_token(provider.id)
    response = RedirectResponse(url="/dashboard", status_code=302)
    _set_auth_cookie(response, token)
    return response


@router.get("/wyloguj")
def logout():
    """Wylogowanie."""
    response = RedirectResponse(url="/auth/logowanie", status_code=302)
    response.delete_cookie("access_token")
    return response
