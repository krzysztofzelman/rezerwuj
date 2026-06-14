import datetime
import logging
import secrets
from contextlib import asynccontextmanager
from urllib.parse import parse_qs

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload

from app.config import SITE_URL, STRIPE_WEBHOOK_SECRET, SECRET_KEY, ADMIN_PASSWORD, SUBSCRIPTION_PRICE_PLN
from app.database import engine, Base, get_db, SessionLocal
from app.models import ServiceProvider, WorkingHour, Service, Order, BlockedSlot
from app.auth import decode_access_token
from app.payments import handle_stripe_webhook, process_subscription_event, MOCK_MODE
from app.csrf import verify_csrf
from app.routers import auth_router, public_router, dashboard_router, admin_router
from app.scheduler import start_scheduler, stop_scheduler
from app.metrics import MetricsMiddleware, metrics_endpoint

# === Logowanie ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("napraw_mnie")

# === Tworzenie tabel ===
Base.metadata.create_all(bind=engine)

# === Migracje dla SQLite (ALTER TABLE nie jest obsługiwany przez create_all) ===
def _run_migrations():
    """Dodaje brakujące kolumny do istniejących tabel SQLite."""
    from sqlalchemy import inspect as sa_inspect, text as sa_text
    from app.database import DATABASE_URL

    if not DATABASE_URL.startswith("sqlite"):
        return

    inspector = sa_inspect(engine)
    all_models = [ServiceProvider, WorkingHour, Service, Order, BlockedSlot]

    for model_cls in all_models:
        table_name = model_cls.__tablename__
        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        model_cols = {c.name for c in model_cls.__table__.columns}

        missing = model_cols - existing_cols
        if not missing:
            continue

        with engine.connect() as conn:
            for col_name in sorted(missing):
                col = model_cls.__table__.columns[col_name]
                col_type = col.type.compile(engine.dialect)
                default = ""
                if col.default is not None and hasattr(col.default, "arg"):
                    val = col.default.arg
                    if isinstance(val, bool):
                        default = f" DEFAULT {1 if val else 0}"
                    elif isinstance(val, (int, float)):
                        default = f" DEFAULT {val}"
                    elif isinstance(val, str):
                        default = f" DEFAULT '{val}'"
                null = "NULL" if col.nullable else "NOT NULL"
                sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {null}{default}"
                conn.execute(sa_text(sql))
                logger.info(f"✅ Migracja: dodano kolumnę {table_name}.{col_name} ({col_type})")


_run_migrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uruchamiane przy starcie i zamknięciu aplikacji."""
    logger.info(f"🚀 Napraw Mnie uruchomiony na {SITE_URL}")
    logger.info(f"📧 Tryb SMS: {'MOCK' if __import__('app.config', fromlist=['']).SMS_MOCK else 'PRODUKCYJNY'}")
    logger.info(f"📧 Tryb E-mail: {'MOCK' if __import__('app.config', fromlist=['']).EMAIL_MOCK else 'PRODUKCYJNY (SMTP)'}")

    # Sprawdź konfigurację Stripe
    stripe_key = __import__('app.config', fromlist=['']).STRIPE_SECRET_KEY
    if not stripe_key or stripe_key.startswith('sk_test_...'):
        logger.info("💳 Stripe: tryb MOCK (bez klucza lub placeholder)")
    else:
        logger.info("💳 Stripe: skonfigurowany")

    # Walidacja bezpieczeństwa
    if not SECRET_KEY or SECRET_KEY == "dev-secret-key-change-in-production-1234567890":
        logger.warning("⚠️  SECRET_KEY nie został ustawiony! Użyj silnego, losowego klucza w .env.production")
    if not ADMIN_PASSWORD or ADMIN_PASSWORD == "Admin123!":
        logger.warning("⚠️  ADMIN_PASSWORD nie został zmieniony! Ustaw silne hasło dla konta admina")

    # Seed konta admina
    _seed_admin()

    # Uruchom harmonogram zadań
    start_scheduler()

    yield
    logger.info("👋 Napraw Mnie zatrzymany")

    stop_scheduler()


def _seed_admin():
    """Tworzy konto admina jeśli nie istnieje."""
    from app.config import ADMIN_EMAIL, ADMIN_PASSWORD
    from app.auth import hash_password

    db = SessionLocal()
    try:
        admin = db.query(ServiceProvider).filter(ServiceProvider.email == ADMIN_EMAIL).first()
        if not admin:
            admin = ServiceProvider(
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
    title="naprawmnie — System Zleceń Serwisowych",
    description="SaaS do zarządzania zleceniami serwisowymi dla warsztatów naprawczych",
    version="1.0.0",
    lifespan=lifespan,
)

# === Endpointy systemowe (przed routerami, aby uniknąć przechwycenia przez catch-all /{slug}) ===
@app.get("/health")
def health_check():
    """Endpoint dla Docker healthcheck."""
    return {"status": "ok"}


@app.get("/metrics")
def prometheus_metrics():
    """Endpoint metryk Prometheus."""
    return metrics_endpoint()


@app.get("/favicon.ico")
async def favicon():
    """Minimalny favicon — kalendarz."""
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="6" y="12" width="52" height="46" rx="6" fill="#2C3E50"/>
  <rect x="6" y="20" width="52" height="10" fill="#1B2838"/>
  <rect x="12" y="14" width="6" height="5" rx="2" fill="#fff"/>
  <rect x="28" y="14" width="6" height="5" rx="2" fill="#fff"/>
  <rect x="44" y="14" width="6" height="5" rx="2" fill="#fff"/>
  <text x="32" y="48" text-anchor="middle" font-size="22" font-weight="bold" fill="#fff" font-family="sans-serif">17</text>
</svg>"""
    from starlette.responses import Response
    return Response(content=svg.strip(), media_type="image/svg+xml")


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

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=[SITE_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

# === Middleware metryk ===
app.add_middleware(MetricsMiddleware)


# === Middleware: Nagłówki bezpieczeństwa ===
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Dodaje nagłówki bezpieczeństwa do każdej odpowiedzi."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # HSTS tylko na HTTPS
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # CSP — zezwól na Bootstrap CDN, Flatpickr CDN i własne skrypty/style
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://www.google.com https://www.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "img-src 'self' data: https:; "
        "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
        "frame-src https://www.google.com; "
        "connect-src 'self' https://cdn.jsdelivr.net;"
        "form-action 'self'"
    )
    return response


# === Middleware: Auth przez cookie dla dashboardu ===
@app.middleware("http")
async def cookie_auth_middleware(request: Request, call_next):
    """Sprawdza ciasteczko access_token i ustawia request.state.provider."""
    request.state.provider = None
    request.state.csrf_token = ""

    # Tylko dla ścieżek dashboardu i admina
    path = request.url.path
    needs_csrf = path.startswith("/dashboard") or path.startswith("/admin") or path.startswith("/auth")
    token_set = False

    # Dla GET — wygeneruj CSRF token przed renderowaniem szablonu
    if request.method == "GET" and needs_csrf:
        request.state.csrf_token = secrets.token_hex(32)
        token_set = True

    # Dla POST — zweryfikuj CSRF przed przetworzeniem
    if request.method in ("POST", "PUT", "DELETE", "PATCH") and needs_csrf and not path.startswith("/stripe/"):
        try:
            # Browser JS wstawia _csrf_token jako pole formularza (nie nagłówek)
            if not request.headers.get("X-CSRF-Token"):
                # Czytamy surowe body, aby nie konsumować strumienia dla request.form()
                body_bytes = await request.body()
                params = parse_qs(body_bytes.decode("utf-8"))
                form_token = params.get("_csrf_token", [None])[0]
                if form_token:
                    # Wstrzyknij do scope i zresetuj cache headers
                    request.scope["headers"].append(("x-csrf-token".encode(), form_token.encode()))
                    if hasattr(request, "_headers"):
                        del request._headers
            verify_csrf(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail},
            )

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
                        db.query(ServiceProvider)
                        .options(
                            selectinload(ServiceProvider.working_hours),
                            selectinload(ServiceProvider.orders),
                            selectinload(ServiceProvider.blocked_slots),
                            selectinload(ServiceProvider.services),
                        )
                        .filter(ServiceProvider.id == provider_id)
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

    # Ustaw ciasteczko CSRF z tokenem wygenerowanym przed renderowaniem
    if request.method == "GET" and token_set:
        csrf_val = getattr(request.state, "csrf_token", "")
        if csrf_val:
            from app.csrf import CSRF_COOKIE_NAME, CSRF_TOKEN_TTL, sign_token
            signed = sign_token(csrf_val)
            is_https = request.url.scheme == "https"
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=signed,
                httponly=False,
                samesite="strict",
                max_age=CSRF_TOKEN_TTL,
                secure=is_https,
                path="/",
            )

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


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc):
    """Zwraca JSON z kodem błędu zamiast 500 dla HTTPException."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
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
    return templates.TemplateResponse("public/landing.html", {
        "request": request,
        "subscription_price": SUBSCRIPTION_PRICE_PLN // 100,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
