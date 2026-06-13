import datetime
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload

from app.config import SITE_URL, STRIPE_WEBHOOK_SECRET
from app.database import engine, Base, get_db, SessionLocal
from app.models import Provider
from app.auth import decode_access_token
from app.payments import handle_stripe_webhook, process_subscription_event, MOCK_MODE
from app.routers import auth_router, public_router, dashboard_router, admin_router

# === Logowanie ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("rezerwuj")

# === Tworzenie tabel ===
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uruchamiane przy starcie i zamknięciu aplikacji."""
    logger.info(f"🚀 Rezerwuj SaaS uruchomiony na {SITE_URL}")
    logger.info(f"📧 Tryb SMS: {'MOCK' if __import__('app.config', fromlist=['']).SMS_MOCK else 'PRODUKCYJNY'}")

    # Sprawdź konfigurację Stripe
    stripe_key = __import__('app.config', fromlist=['']).STRIPE_SECRET_KEY
    if not stripe_key or stripe_key.startswith('sk_test_...'):
        logger.info("💳 Stripe: tryb MOCK (bez klucza lub placeholder)")
    else:
        logger.info("💳 Stripe: skonfigurowany")

    # Seed konta admina
    _seed_admin()

    yield
    logger.info("👋 Rezerwuj SaaS zatrzymany")


def _seed_admin():
    """Tworzy konto admina jeśli nie istnieje."""
    from app.config import ADMIN_EMAIL, ADMIN_PASSWORD
    from app.auth import hash_password

    db = SessionLocal()
    try:
        admin = db.query(Provider).filter(Provider.email == ADMIN_EMAIL).first()
        if not admin:
            admin = Provider(
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                name="Administrator",
                slug="admin",
                subscription_status="active",
                is_active=True,
                is_admin=True,
                trial_start=datetime.date.today(),
                trial_end=datetime.date.today() + datetime.timedelta(days=365),
            )
            db.add(admin)
            db.commit()
            logger.info(f"✅ Konto admina utworzone: {ADMIN_EMAIL}")
        elif not admin.is_admin:
            admin.is_admin = True
            db.commit()
            logger.info(f"✅ Uprawnienia admina nadane: {ADMIN_EMAIL}")
        else:
            logger.info(f"✅ Konto admina istnieje: {ADMIN_EMAIL}")
    except Exception as e:
        logger.error(f"❌ Błąd podczas tworzenia konta admina: {e}")
    finally:
        db.close()


app = FastAPI(
    title="Rezerwuj — System Rezerwacji dla Usługodawców",
    description="SaaS do zarządzania rezerwacjami dla małych firm usługowych",
    version="1.0.0",
    lifespan=lifespan,
)

# === Statyczne pliki ===
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# === Routery ===
app.include_router(auth_router.router)

# Router dashboardu z middlewarem cookie-auth
app.include_router(dashboard_router.router)

# Router publiczny
app.include_router(public_router.router)

# Router admina
app.include_router(admin_router.router)


# === Middleware: Auth przez cookie dla dashboardu ===
@app.middleware("http")
async def cookie_auth_middleware(request: Request, call_next):
    """Sprawdza ciasteczko access_token i ustawia request.state.provider."""
    request.state.provider = None

    # Tylko dla ścieżek dashboardu i admina
    path = request.url.path
    if path.startswith("/dashboard") or path.startswith("/api/dashboard") or path.startswith("/admin"):
        token = None
        auth_cookie = request.cookies.get("access_token")
        if auth_cookie and auth_cookie.startswith("Bearer "):
            token = auth_cookie[7:]

        if token:
            provider_id = decode_access_token(token)
            if provider_id:
                db = SessionLocal()
                try:
                    provider = (
                        db.query(Provider)
                        .options(
                            selectinload(Provider.working_hours),
                            selectinload(Provider.bookings),
                            selectinload(Provider.blocked_slots),
                            selectinload(Provider.services),
                        )
                        .filter(Provider.id == provider_id)
                        .first()
                    )
                    request.state.provider = provider
                finally:
                    db.close()

        if not request.state.provider:
            if path.startswith("/api/"):
                return JSONResponse(
                    content={"error": "Nie jesteś zalogowany"},
                    status_code=401,
                )
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/auth/logowanie", status_code=302)

    response = await call_next(request)
    return response


# === Webhook Stripe ===
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Endpoint webhooka Stripe dla zdarzeń subskrypcji."""
    if MOCK_MODE:
        logger.info("Webhook Stripe pominięty (tryb MOCK)")
        return {"status": "mock"}

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    event = handle_stripe_webhook(payload, sig_header)
    if event is None:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    process_subscription_event(event, db)
    return {"status": "ok"}


# === Obsługa błędów ===
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Strona 404."""
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse(
        "public/not_found.html",
        {"request": request},
        status_code=404,
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc):
    """Ogólna obsługa błędów."""
    logger.error(f"Nieobsłużony błąd: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Wystąpił wewnętrzny błąd serwera. Spróbuj ponownie później."},
    )


# === Landing page ===
@app.get("/")
def landing_page(request: Request):
    """Strona główna — landing page z informacją o produkcie."""
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse("public/landing.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
