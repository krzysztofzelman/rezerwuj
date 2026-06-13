"""
Test aplikacji Rezerwuj.
Uruchom: python test_app.py (gdy app działa na localhost:8000)
"""
import urllib.request, urllib.parse
import json, re, sys, time
from http.cookies import SimpleCookie


def req(method, path, data=None, headers=None):
    url = f"http://localhost:8000{path}"
    body = None
    if data and method == "POST":
        body = urllib.parse.urlencode(data).encode()
        if headers is None:
            headers = {}
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

    r = urllib.request.Request(url, data=body, method=method)
    if headers:
        for k, v in headers.items():
            r.add_header(k, v)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        resp = opener.open(r, timeout=10)
        return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")


def parse_token(hdrs):
    from urllib.parse import unquote
    # HTTPMessage converts to dict yields lowercase keys, but be safe
    raw_cookie = hdrs.get("set-cookie") or hdrs.get("Set-Cookie") or ""
    if not raw_cookie:
        return None
    c = SimpleCookie(raw_cookie)
    raw = c.get("access_token")
    if not raw:
        return None
    val = unquote(raw.value)
    if val.startswith("Bearer "):
        return val[7:]
    return val


def main():
    print("=== Testowanie aplikacji Rezerwuj ===\n")

    # 1. Login page
    print("1. Strona logowania...", end=" ")
    s, h, body = req("GET", "/auth/logowanie")
    assert s == 200
    assert "Zaloguj" in body
    print("OK")

    # 2. Rejestracja
    print("2. Rejestracja...", end=" ")
    s, h, body = req("POST", "/auth/rejestracja", {
        "email": "test@example.com",
        "password": "test12345",
        "name": "Jan Testowy",
        "slug": "fryzjer-janek",
    })
    assert s == 302, f"Oczekiwano 302, mamy {s}"
    token = parse_token(h)
    assert token, f"Brak tokena w set-cookie (keys={list(h.keys())})"
    print(f"OK (token={token[:16]}...)")

    # 3. Dashboard
    print("3. Dashboard z tokenem...", end=" ")
    s, h, body = req("GET", "/dashboard", headers={
        "Cookie": f"access_token=Bearer {token}"
    })
    assert s == 200, f"Mamy {s}"
    assert "Jan Testowy" in body or "Witaj" in body
    print("OK")

    # 4. Dashboard bez auth
    print("4. Dashboard bez tokena...", end=" ")
    s, h, body = req("GET", "/dashboard")
    assert s == 302
    print("OK (przekierowanie)")

    # 5. Public booking page
    print("5. Strona rezerwacji...", end=" ")
    s, h, body = req("GET", "/fryzjer-janek")
    assert s == 200
    assert "Wybierz dogodny termin" in body
    print("OK")

    # 6. 404
    print("6. Nieistniejący slug...", end=" ")
    s, h, body = req("GET", "/nie-istnieje")
    assert s == 404
    print("OK")

    # 7. API slots
    print("7. API sloty (2099)...", end=" ")
    s, h, body = req("GET", "/api/fryzjer-janek/slots?date=2099-01-01")
    data = json.loads(body)
    assert "slots" in data
    print(f"OK ({len(data['slots'])} slotów)")

    # 8. Login
    print("8. Logowanie...", end=" ")
    s, h, body = req("POST", "/auth/logowanie", {
        "email": "test@example.com",
        "password": "test12345",
    })
    assert s == 302
    print("OK")

    # 9. Złe hasło
    print("9. Logowanie (złe hasło)...", end=" ")
    s, h, body = req("POST", "/auth/logowanie", {
        "email": "test@example.com",
        "password": "zlehaslo",
    })
    assert s == 200
    assert "Nieprawidłowy" in body
    print("OK")

    # 10. Provider info
    print("10. API info...", end=" ")
    s, h, body = req("GET", "/api/fryzjer-janek/info")
    d = json.loads(body)
    assert d.get("name") == "Jan Testowy"
    print("OK")

    # 11. Dashboard settings (z tokenem)
    print("11. Dashboard ustawienia...", end=" ")
    s, h, body = req("GET", "/dashboard/ustawienia", headers={
        "Cookie": f"access_token=Bearer {token}"
    })
    assert s == 200, f"Mamy {s}, body={body[:100]}"
    assert "Godziny pracy" in body
    print("OK")

    # 12. Zakładka płatności
    print("12. Dashboard płatności...", end=" ")
    s, h, body = req("GET", "/dashboard/platnosci", headers={
        "Cookie": f"access_token=Bearer {token}"
    })
    assert s == 200, f"Mamy {s}, body={body[:100]}"
    assert "Status subskrypcji" in body
    print("OK")

    # 13. Podgląd linku
    print("13. Dashboard podgląd...", end=" ")
    s, h, body = req("GET", "/dashboard/podglad", headers={
        "Cookie": f"access_token=Bearer {token}"
    })
    assert s == 200
    assert "publiczny link" in body.lower()
    print("OK")

    print(f"\n{'='*40}")
    print(f"✅ Wszystkie 13 testów przeszło pomyślnie!")
    print(f"{'='*40}")
    return 0


if __name__ == "__main__":
    time.sleep(1)
    sys.exit(main())
