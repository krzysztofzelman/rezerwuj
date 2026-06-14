"""Konfiguracja testów — TestClient z izolowaną bazą SQLite."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def _setup_test_env():
    """Ustawia środowisko testowe raz na sesję."""
    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only-1234567890"
    os.environ["SITE_URL"] = "http://testserver"
    os.environ["ADMIN_EMAIL"] = "admin@test.pl"
    os.environ["ADMIN_PASSWORD"] = "TestAdmin123!"
    os.environ["SMS_MOCK"] = "true"

    # Użyj testowej bazy (tmp, żeby nie mieszać z dev)
    os.environ["DATABASE_URL"] = "sqlite:///./.pytest_cache/test_napraw_mnie.db"

    # Usuń starą testową bazę jeśli istnieje
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".pytest_cache",
        "test_napraw_mnie.db",
    )
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(scope="session")
def client(_setup_test_env):
    """TestClient dla aplikacji FastAPI — raz na sesję."""
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_with_csrf(client):
    """Client z ważnym tokenem CSRF (po stronie logowania GET).

    Zwraca krotkę (client, csrf_token).
    """
    resp = client.get("/auth/logowanie")
    assert resp.status_code == 200

    csrf_cookie = resp.cookies.get("csrf_token", "")
    raw_token = csrf_cookie.split(".", 1)[0] if "." in csrf_cookie else ""
    assert raw_token, "Brak tokenu CSRF w odpowiedzi"

    return client, raw_token
