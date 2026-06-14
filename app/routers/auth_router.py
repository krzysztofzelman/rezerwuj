import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import rate_limit_strict
from app.models import ServiceProvider, PasswordResetToken
from app.schemas import RegisterRequest, LoginRequest
from app.auth import hash_password, verify_password, create_access_token
from app.config import TRIAL_DAYS, SITE_URL
from app.email_mock import send_password_reset_email

logger = logging.getLogger("servicehub.auth")
router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


def _set_auth_cookie(response: RedirectResponse, token: str) -> None:
    """Ustawia ciasteczko z tokenem JWT."""
    is_https = SITE_URL.startswith("https")
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        max_age=72 * 3600,  # 72h
        samesite="lax",
        secure=is_https,
    )


def _auth_context(request: Request) -> dict:
    """Kontekst dla stron logowania/rejestracji."""
    return {
        "request": request,
        "csrf_token": getattr(request.state, "csrf_token", ""),
    }


@router.get("/rejestracja")
def register_page(request: Request):
    """Strona rejestracji."""
    return templates.TemplateResponse(
        "dashboard/register.html",
        _auth_context(request),
    )


@router.post("/rejestracja")
async def register(
    request: Request,
    _rl: None = Depends(rate_limit_strict),
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
            {"request": request, "error": str(e), "csrf_token": getattr(request.state, "csrf_token", "")},
        )

    # Sprawdź czy email już istnieje
    existing = db.query(ServiceProvider).filter(ServiceProvider.email == reg_data.email).first()
    if existing:
        return templates.TemplateResponse(
            "dashboard/register.html",
            {"request": request, "error": "Ten adres e-mail jest już zarejestrowany", "csrf_token": getattr(request.state, "csrf_token", "")},
        )

    # Sprawdź czy slug już istnieje
    existing_slug = db.query(ServiceProvider).filter(ServiceProvider.slug == reg_data.slug).first()
    if existing_slug:
        return templates.TemplateResponse(
            "dashboard/register.html",
            {
                "request": request,
                "error": "Ten identyfikator (slug) jest już zajęty. Wybierz inny.",
                "csrf_token": getattr(request.state, "csrf_token", ""),
            },
        )

    # Utwórz konto z trialem
    today = datetime.date.today()
    trial_end_date = today + datetime.timedelta(days=TRIAL_DAYS)

    provider = ServiceProvider(
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


def _create_default_hours(db: Session, provider: ServiceProvider) -> None:
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
        "dashboard/login.html", _auth_context(request)
    )


@router.post("/logowanie")
async def login(
    request: Request,
    _rl: None = Depends(rate_limit_strict),
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
            {"request": request, "error": str(e), "csrf_token": getattr(request.state, "csrf_token", "")},
        )

    provider = (
        db.query(ServiceProvider)
        .filter(ServiceProvider.email == login_data.email)
        .first()
    )

    if not provider or not verify_password(login_data.password, provider.password_hash):
        return templates.TemplateResponse(
            "dashboard/login.html",
            {"request": request, "error": "Nieprawidłowy e-mail lub hasło", "csrf_token": getattr(request.state, "csrf_token", "")},
        )

    token = create_access_token(provider.id)
    response = RedirectResponse(url="/dashboard", status_code=302)
    _set_auth_cookie(response, token)
    return response


# ===== Resetowanie hasła =====

@router.get("/reset-hasla")
def password_reset_request_page(request: Request):
    """Strona z formularzem do żądania resetu hasła."""
    return templates.TemplateResponse(
        "dashboard/reset_password_request.html",
        _auth_context(request),
    )


@router.post("/reset-hasla")
async def password_reset_request(
    request: Request,
    _rl: None = Depends(rate_limit_strict),
    db: Session = Depends(get_db),
):
    """Wysyła e-mail z linkiem do resetu hasła."""
    form = await request.form()
    email = form.get("email", "").strip().lower()

    if not email:
        return templates.TemplateResponse(
            "dashboard/reset_password_request.html",
            {
                "request": request,
                "error": "Podaj adres e-mail",
                "csrf_token": getattr(request.state, "csrf_token", ""),
            },
        )

    provider = db.query(ServiceProvider).filter(ServiceProvider.email == email).first()

    # Zawsze zwracaj sukces, nawet jeśli e-mail nie istnieje (bezpieczeństwo)
    if provider:
        import secrets
        from datetime import timedelta

        token = secrets.token_urlsafe(48)
        expires_at = datetime.datetime.now(datetime.timezone.utc) + timedelta(hours=1)

        reset_token = PasswordResetToken(
            provider_id=provider.id,
            token=token,
            expires_at=expires_at,
        )
        db.add(reset_token)
        db.commit()

        site_url = SITE_URL.rstrip("/")
        reset_url = f"{site_url}/auth/reset-hasla/{token}"
        send_password_reset_email(provider.email, reset_url)

    return templates.TemplateResponse(
        "dashboard/reset_password_request.html",
        {
            "request": request,
            "success": "Jeśli konto z tym adresem e-mail istnieje, wysłaliśmy link do resetu hasła.",
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.get("/reset-hasla/{token}")
def password_reset_form(request: Request, token: str, db: Session = Depends(get_db)):
    """Strona z formularzem do ustawienia nowego hasła."""
    reset_token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token == token,
            PasswordResetToken.used == False,  # noqa: E712
            PasswordResetToken.expires_at > datetime.datetime.now(datetime.timezone.utc),
        )
        .first()
    )

    if not reset_token:
        return templates.TemplateResponse(
            "dashboard/reset_password_request.html",
            {
                "request": request,
                "error": "Link do resetu hasła jest nieprawidłowy lub wygasł. Poproś o nowy link.",
                "csrf_token": getattr(request.state, "csrf_token", ""),
            },
        )

    return templates.TemplateResponse(
        "dashboard/reset_password_form.html",
        {
            "request": request,
            "token": token,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/reset-hasla/{token}")
async def password_reset_confirm(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
):
    """Przetwarza formularz ustawienia nowego hasła."""
    reset_token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token == token,
            PasswordResetToken.used == False,  # noqa: E712
            PasswordResetToken.expires_at > datetime.datetime.now(datetime.timezone.utc),
        )
        .first()
    )

    if not reset_token:
        return templates.TemplateResponse(
            "dashboard/reset_password_request.html",
            {
                "request": request,
                "error": "Link do resetu hasła jest nieprawidłowy lub wygasł.",
                "csrf_token": getattr(request.state, "csrf_token", ""),
            },
        )

    form = await request.form()
    password = form.get("password", "")
    confirm = form.get("confirm_password", "")

    if len(password) < 8:
        return templates.TemplateResponse(
            "dashboard/reset_password_form.html",
            {
                "request": request,
                "token": token,
                "error": "Hasło musi mieć co najmniej 8 znaków.",
                "csrf_token": getattr(request.state, "csrf_token", ""),
            },
        )

    if password != confirm:
        return templates.TemplateResponse(
            "dashboard/reset_password_form.html",
            {
                "request": request,
                "token": token,
                "error": "Hasła nie są zgodne.",
                "csrf_token": getattr(request.state, "csrf_token", ""),
            },
        )

    provider = db.query(ServiceProvider).filter(ServiceProvider.id == reset_token.provider_id).first()
    if not provider:
        return templates.TemplateResponse(
            "dashboard/reset_password_request.html",
            {
                "request": request,
                "error": "Użytkownik nie istnieje.",
                "csrf_token": getattr(request.state, "csrf_token", ""),
            },
        )

    provider.password_hash = hash_password(password)
    reset_token.used = True
    db.commit()

    return templates.TemplateResponse(
        "dashboard/login.html",
        {
            "request": request,
            "success": "Hasło zostało zmienione. Możesz się zalogować nowym hasłem.",
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.get("/wyloguj")
def logout():
    """Wylogowanie."""
    response = RedirectResponse(url="/auth/logowanie", status_code=302)
    response.delete_cookie("access_token")
    return response
