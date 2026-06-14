# ServiceHub — System Zarządzania Zleceniami Serwisowymi RTV/AGD

SaaS do zarządzania przyjęciem i naprawą sprzętu RTV/AGD dla warsztatów serwisowych.

## Funkcje

### Dla klientów
- **Publiczna strona zgłoszenia** — klient wybiera typ sprzętu (TV, pralka, lodówka, audio, komputer, inny), podaje markę, model, numer seryjny i opis usterki
- **Termin dostarczenia** — wybór daty i godziny z dostępnych slotów (harmonogram serwisu)
- **Zdjęcia** — opcjonalne załączanie zdjęć uszkodzonego sprzętu
- **Potwierdzenie SMS** — automatyczny SMS po przyjęciu zlecenia
- **Potwierdzenie e-mail** — automatyczny e-mail z podsumowaniem zlecenia i opisem usterki
- **Płatność online** — opcjonalna zaliczka przez Stripe
- **Ochrona przed botami** — Google reCAPTCHA v2 przy składaniu zlecenia

### Dla serwisantów
- **Dashboard** — podgląd nadchodzących zleceń z danymi sprzętu i priorytetem
- **Zarządzanie statusem** — potwierdzone → w naprawie → zrealizowane / anulowane
- **Ustawienia godzin pracy** — dzień po dniu, z przerwami
- **Blokowanie terminów** — urlop, przerwy, dni wolne
- **Zarządzanie usługami** — typy napraw (np. diagnostyka, wymiana płyty, czyszczenie) z własną nazwą, ceną i czasem trwania
- **Notatki serwisowe** — pole do notatek o przebiegu naprawy, kosztach naprawy
- **Kalendarz wizualny** — podgląd zleceń w widoku miesięcznym/tygodniowym (FullCalendar v6)
- **Eksport CSV** — lista zleceń do pliku CSV (UTF-8-BOM, Excel-compatible)
- **Unikalny link** — `{domena}/{slug}` do udostępnienia klientom
- **Subskrypcja** — 14 dni za darmo, potem 79 zł/mies. (Stripe)
- **Przypomnienia e-mail** — automatyczne przypomnienia o zleceniach oczekujących na odbiór

### Dla administratora
- **Panel admina** — `/admin` — lista wszystkich użytkowników
- **Statystyki** — liczba użytkowników, aktywni, zlecenia
- **Zarządzanie** — aktywacja/dezaktywacja kont, przedłużanie subskrypcji

### Automatyka i monitoring
- **APScheduler** — automatyczne kończenie minionych zleceń (3:00) i wysyłanie przypomnień (8:00)
- **Prometheus metrics** — `/metrics` — liczniki zleceń, rate limitów, e-maili, resetów haseł, czasu odpowiedzi
- **Rate limiting** — Redis (z automatycznym fallbackiem do pamięci RAM) — chroni przed brute-force i abuse

## Tech Stack

| Komponent | Technologia |
|-----------|-------------|
| Backend | Python 3.10+ / FastAPI |
| Baza danych | PostgreSQL (produkcja), SQLite (developersko) |
| Frontend | Jinja2 / Bootstrap 5 / Flatpickr / FullCalendar v6 |
| Autentykacja | JWT + bcrypt (passlib) |
| Ochrona CSRF | Double Submit Cookie + HMAC |
| Rate Limiting | Redis + automatyczny fallback do pamięci RAM |
| Płatności | Stripe Checkout / Subskrypcje |
| SMS | SMSAPI.pl / Twilio (mock w development) |
| E-mail | SMTP (smtplib, STARTTLS, port 587) — mock w development |
| Bezpieczeństwo | CSP + HSTS + reCAPTCHA v2 |
| Monitoring | Prometheus + APScheduler |
| Deployment | Docker Compose, VPS (nginx reverse proxy) |

## Szybki start (lokalny)

### 1. Wymagania

- Python 3.10+
- pip

### 2. Instalacja

```bash
cd servicehub
pip install -r requirements.txt
cp .env.example .env
# Edytuj .env według potrzeb
```

### 3. Uruchomienie

```bash
python -m app.main
```

Aplikacja będzie dostępna pod adresem: **http://localhost:8000**

### 4. Rejestracja

1. Otwórz http://localhost:8000/auth/rejestracja
2. Wprowadź dane: e-mail, hasło, nazwę serwisu, unikalny slug (np. `rtv-serwis`)
3. Po rejestracji zostaniesz automatycznie zalogowany
4. Twój publiczny link: http://localhost:8000/{slug}

## Deployment (Docker + VPS)

### Wymagania

- Serwer VPS z Docker i Docker Compose
- Domena z certyfikatem SSL (nginx na hoście)

### Pliki deploymnetu

| Plik | Opis |
|------|------|
| `Dockerfile` | Obraz Pythona z aplikacją |
| `docker-compose.yml` | Definicja kontenera (port 8002) |
| `.env.production` | Konfiguracja produkcyjna |
| `scripts/deploy.sh` | Pull obrazu, restart kontenera |
| `scripts/vps-init.sh` | Inicjalizacja VPS (jednorazowo) |

Aplikacja uruchamiana na `127.0.0.1:8002`, obsługiwana przez nginx na hoście z SSL.

## Panel administracyjny

Dostępny po zalogowaniu na konto z rolą admina:

| Ścieżka | Opis |
|---------|------|
| `/admin` | Panel admina — lista użytkowników, statystyki |
| `/admin/users/{id}/toggle-active` | Aktywacja/dezaktywacja konta |
| `/admin/users/{id}/activate-subscription` | Przedłużenie subskrypcji o 30 dni |

Konto admina tworzone automatycznie przy starcie aplikacji — konfiguracja w `.env.production`:

```
ADMIN_EMAIL=admin@servicehub.app
ADMIN_PASSWORD=Admin123!
```

## Konfiguracja (.env)

| Zmienna | Opis | Domyślnie |
|---------|------|-----------|
| `DATABASE_URL` | URI bazy danych | `sqlite:///./servicehub.db` |
| `SECRET_KEY` | Klucz do JWT i CSRF (wymagany w produkcji!) | `""` (brak — warning przy starcie) |
| `SITE_URL` | Adres aplikacji | `http://localhost:8000` |
| `ADMIN_EMAIL` | Email konta admina | `admin@servicehub.app` |
| `ADMIN_PASSWORD` | Hasło admina (wymagane w produkcji!) | `""` (brak — warning przy starcie) |
| `TRIAL_DAYS` | Długość okresu próbnego | `14` |
| `MAX_BOOKING_DAYS_AHEAD` | Maks. liczba dni do przodu dla przyjmowania zleceń | `60` |
| `STRIPE_SECRET_KEY` | Klucz Secret Stripe | `sk_test_...` |
| `STRIPE_PUBLISHABLE_KEY` | Klucz Publiczny Stripe | `pk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | Sekret webhooka Stripe | `whsec_...` |
| `SUBSCRIPTION_PRICE_ID` | ID produktu Stripe | `price_...` |
| `SUBSCRIPTION_PRICE_PLN` | Cena subskrypcji w groszach | `4900` |
| `SMS_API_KEY` | Klucz API SMS | — |
| `SMS_SENDER` | Nazwa nadawcy SMS | `ServiceHub` |
| `SMS_MOCK` | Tryb mock SMS (true=log, false=API) | `true` |
| `SMTP_HOST` | Serwer SMTP | `""` |
| `SMTP_PORT` | Port SMTP (STARTTLS) | `587` |
| `SMTP_USER` | Użytkownik SMTP | `""` |
| `SMTP_PASSWORD` | Hasło SMTP | `""` |
| `SMTP_FROM` | Adres nadawcy e-mail | `ServiceHub <noreply@servicehub.app>` |
| `EMAIL_MOCK` | Tryb mock e-mail (true=log, false=SMTP) | `true` |
| `RECAPTCHA_SITE_KEY` | Site key Google reCAPTCHA v2 | `""` |
| `RECAPTCHA_SECRET_KEY` | Secret key Google reCAPTCHA v2 | `""` |
| `REDIS_URL` | URL Redis (puste = fallback do RAM) | `""` |

### Stripe — konfiguracja płatności

W trybie developerskim (bez kluczy Stripe) aplikacja działa w trybie **mock** — płatności są symulowane, a subskrypcja aktywowana automatycznie po kliknięciu przycisku.

Dla rzeczywistych płatności:

1. Załóż konto na [stripe.com](https://stripe.com)
2. Pobierz klucze testowe z dashboardu Stripe
3. Utwórz produkt subskrypcyjny (cena miesięczna, np. 79 PLN)
4. Skopiuj `price_id` do `.env`
5. Uruchom Stripe CLI do testowania webhooków:
   ```bash
   stripe listen --forward-to localhost:8000/stripe/webhook
   ```
6. Skopiuj `whsec_...` do `.env`

### SMS — konfiguracja

Domyślnie SMS-y działają w trybie mock — logują treść do konsoli.
Aby włączyć rzeczywiste SMS-y przez **SMSAPI.pl**:
1. Załóż konto na [SMSAPI.pl](https://www.smsapi.pl)
2. Wygeneruj klucz API (Bearer token) w panelu SMSAPI
3. Ustaw `SMS_API_KEY=TwójKluczAPI` w `.env`
4. Ustaw `SMS_MOCK=false`

Aplikacja wysyła SMS-y przez `https://api.smsapi.pl/sms.do` z autoryzacją Bearer token.

**Wysyłane SMS-y:**
- Potwierdzenie przyjęcia zlecenia serwisowego (do klienta)
- Powiadomienie o nowym zleceniu (do serwisanta, jeśli podał numer telefonu)

### E-mail (SMTP) — konfiguracja

Domyślnie e-maile działają w trybie mock — logują treść do konsoli.
Aby włączyć rzeczywiste e-maile:
1. Uzyskaj dane SMTP od swojego dostawcy hostingu e-mail
2. Ustaw `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` w `.env`
3. Ustaw `EMAIL_MOCK=false`
4. Aplikacja używa STARTTLS na porcie 587

**Wysyłane e-maile:**
- Potwierdzenie przyjęcia zlecenia (do klienta)
- Powiadomienie o nowym zleceniu (do serwisanta — zawsze na jego adres e-mail)
- Przypomnienie o zleceniu oczekującym na odbiór (do klienta, automatycznie codziennie 8:00)
- Link do resetu hasła

### reCAPTCHA v2 — konfiguracja

1. Wejdź na [google.com/recaptcha/admin](https://www.google.com/recaptcha/admin)
2. Wybierz **reCAPTCHA v2** — "Nie jestem robotem" (Checkbox)
3. Dodaj domenę (localhost + produkcyjną)
4. Skopiuj Site Key i Secret Key do `.env`

### Redis — konfiguracja (opcjonalna)

Redis używa się do rate limitingu w produkcji. Jeśli `REDIS_URL` jest puste, aplikacja automatycznie przełącza się na limiter w pamięci RAM — bez żadnych błędów ani przestojów.

Aby włączyć Redis:
1. Odkomentuj `REDIS_URL` w `.env.production`
2. Ustaw wartość np. `redis://redis:6379/0` (dla Docker)
3. Dodaj kontener Redis do `docker-compose.yml`

## Bezpieczeństwo

- **Hasła**: hashowane bcryptem (passlib + bcrypt 4.0.1)
- **JWT**: tokeny z ważnością 72h
- **CSRF**: Double Submit Cookie — HMAC-podpisane tokeny, weryfikacja w middleware dla POST/PUT/DELETE, automatyczne wstrzykiwanie przez JS do formularzy
- **Rate Limiting**: Redis + fallback RAM — limit 5 req/min dla logowania/rejestracji/resetu hasła, 10 req/min dla składania zleceń, 30 req/min dla pozostałych API
- **reCAPTCHA v2**: weryfikacja po stronie serwera przy składaniu zlecenia
- **Security Headers**:
  - **CSP (Content Security Policy)**: ogranicza źródła skryptów, stylów, czcionek — dozwolone CDN-y (Bootstrap, Flatpickr, FullCalendar, reCAPTCHA)
  - **HSTS**: wymusza HTTPS (tylko na produkcji)
  - **X-Frame-Options**: DENY — blokada osadzania w iframe
  - **X-Content-Type-Options**: nosniff
  - **Referrer-Policy**: strict-origin-when-cross-origin
- **SQL Injection**: SQLAlchemy ORM (parametryzowane zapytania)
- **Walidacja**: Pydantic (wejście API) + HTML5 (formularze)
- **XSS**: Jinja2 automatycznie escape'uje dane
- **Ciasteczka**: HttpOnly + SameSite=Lax (dla access_token), SameSite=Strict (dla CSRF)
- **Reset hasła**: token jednorazowy (ważność 1h), zawsze zwraca sukces (ochrona przed enumeracją e-maili)
- **Subskrypcja**: blokada dostępu po anulowaniu/braku płatności

## API Endpoints

### Systemowe
| Metoda | Ścieżka | Opis |
|--------|---------|------|
| GET | `/health` | Healthcheck (Docker, monitorowanie) |
| GET | `/metrics` | Prometheus metrics (liczniki, histogramy) |
| GET | `/favicon.ico` | Favicon (inline SVG — narzędzia) |
| GET | `/` | Landing page |

### Publiczne
| Metoda | Ścieżka | Opis |
|--------|---------|------|
| GET | `/{slug}` | Strona zgłoszenia sprzętu do naprawy |
| GET | `/api/{slug}/info` | Info o serwisie |
| GET | `/api/{slug}/services` | Lista usług serwisu |
| GET | `/api/{slug}/slots?date=YYYY-MM-DD[&service_id=N]` | Dostępne sloty (z uwzględnieniem czasu trwania naprawy) |
| POST | `/api/{slug}/book` | Tworzenie zlecenia naprawy (z weryfikacją reCAPTCHA) |
| GET | `/api/{slug}/payment-success/{order_id}` | Potwierdzenie płatności (przekierowanie z Stripe) |
| GET | `/api/{slug}/payment-cancel/{order_id}` | Anulowanie płatności (przekierowanie z Stripe) |

### Autentykacja
| Metoda | Ścieżka | Opis |
|--------|---------|------|
| GET | `/auth/rejestracja` | Formularz rejestracji |
| POST | `/auth/rejestracja` | Rejestracja |
| GET | `/auth/logowanie` | Formularz logowania |
| POST | `/auth/logowanie` | Logowanie |
| GET | `/auth/wyloguj` | Wylogowanie |
| GET | `/auth/reset-hasla` | Formularz resetu hasła (wpisz e-mail) |
| POST | `/auth/reset-hasla` | Wyślij link resetujący (zawsze zwraca sukces) |
| GET | `/auth/reset-hasla/{token}` | Formularz nowego hasła |
| POST | `/auth/reset-hasla/{token}` | Ustaw nowe hasło |

### Dashboard (wymaga logowania)
| Metoda | Ścieżka | Opis |
|--------|---------|------|
| GET | `/dashboard` | Strona główna z podsumowaniem |
| GET | `/dashboard/zlecenia` | Lista zleceń serwisowych |
| POST | `/dashboard/zlecenia/{order_id}/anuluj` | Anulowanie zlecenia |
| POST | `/dashboard/zlecenia/{order_id}/zakoncz` | Oznaczenie zlecenia jako zrealizowanego |
| POST | `/dashboard/zlecenia/{order_id}/status` | Zmiana statusu (np. na "w naprawie") |
| POST | `/dashboard/zlecenia/{order_id}/notatka` | Zapis notatki serwisowej i kosztu naprawy |
| GET | `/dashboard/zlecenia/eksport` | Eksport zleceń do CSV (UTF-8-BOM) |
| GET | `/dashboard/zlecenia/{order_id}/ics` | Eksport pojedynczego zlecenia do ICS (Google/Apple Calendar) |
| GET | `/dashboard/serwisy` | Zarządzanie usługami |
| POST | `/dashboard/serwisy` | Dodaj nową usługę |
| POST | `/dashboard/serwisy/{service_id}/edytuj` | Edytuj usługę |
| POST | `/dashboard/serwisy/{service_id}/usun` | Usuń usługę (soft delete) |
| GET | `/dashboard/kalendarz` | Widok kalendarza (FullCalendar) |
| GET | `/api/dashboard/calendar?start=&end=` | JSON ze zleceniami dla kalendarza (kolorowe) |
| GET | `/dashboard/ustawienia` | Ustawienia |
| POST | `/dashboard/ustawienia` | Zapis ustawień |
| POST | `/dashboard/godziny-pracy` | Godziny pracy |
| POST | `/dashboard/blokuj` | Blokada terminu |
| POST | `/dashboard/odblokuj/{block_id}` | Usunięcie blokady terminu |
| GET | `/dashboard/platnosci` | Subskrypcja/płatności |
| POST | `/dashboard/subskrypcja/utworz` | Utworzenie sesji Stripe Checkout |
| POST | `/dashboard/subskrypcja/anuluj` | Anulowanie subskrypcji |
| GET | `/dashboard/podglad` | Podgląd linku |

### Admin (wymaga logowania + rola admina)
| Metoda | Ścieżka | Opis |
|--------|---------|------|
| GET | `/admin` | Panel admina |
| POST | `/admin/users/{user_id}/toggle-active` | Aktywacja/dezaktywacja konta |
| POST | `/admin/users/{user_id}/activate-subscription` | Przedłużenie subskrypcji o 30 dni |

### Webhook
| Metoda | Ścieżka | Opis |
|--------|---------|------|
| POST | `/stripe/webhook` | Webhook Stripe |

## Monitorowanie (Prometheus)

Endpoint `/metrics` udostępnia metryki w formacie Prometheus:

| Metryka | Typ | Opis |
|---------|-----|------|
| `servicehub_orders_total` | Counter | Łączna liczba zleceń |
| `servicehub_rate_limit_hits_total` | Counter | Liczba odrzuconych żądań (429) |
| `servicehub_emails_sent_total` | Counter | Liczba wysłanych e-maili |
| `servicehub_password_resets_total` | Counter | Liczba wysłanych linków resetujących |
| `servicehub_active_providers` | Gauge | Liczba aktywnych serwisów |
| `servicehub_total_orders` | Gauge | Łączna liczba zleceń w systemie |
| `servicehub_request_duration_seconds` | Histogram | Czas trwania żądań HTTP (etykiety: method, path, status) |

## Automatyka (APScheduler)

| Zadanie | Harmonogram | Opis |
|---------|-------------|------|
| Auto-complete past orders | Codziennie 3:00 | Oznacza minione zlecenia jako zrealizowane |
| Send order reminders | Codziennie 8:00 | Wysyła e-mail z przypomnieniem o zleceniach oczekujących na odbiór |

Rate limitery są resetowane co minutę (okno kroczące dla RAM, EXPIRE 60s dla Redis).

## Struktura projektu

```
servicehub/
├── .env                    # Konfiguracja lokalna
├── .env.example            # Wzór konfiguracji
├── .env.production         # Konfiguracja produkcyjna
├── requirements.txt        # Zależności Pythona
├── Dockerfile              # Obraz Docker
├── docker-compose.yml      # Definicja kontenera
├── README.md               # Ten plik
├── .dockerignore           # Pliki ignorowane przy budowie Docker
├── app/
│   ├── main.py             # Główny plik aplikacji (FastAPI + middleware + scheduler)
│   ├── config.py           # Konfiguracja z .env
│   ├── database.py         # Połączenie z bazą (SQLAlchemy)
│   ├── models.py           # Modele ORM (ServiceProvider, Order, BlockedSlot, PasswordResetToken, etc.)
│   ├── schemas.py          # Schematy Pydantic (walidacja zleceń z polami sprzętu)
│   ├── auth.py             # JWT + bcrypt
│   ├── csrf.py             # Ochrona CSRF (Double Submit Cookie + HMAC)
│   ├── ratelimit.py        # Rate limiting (Redis + fallback RAM)
│   ├── deps.py             # Wspólne zależności FastAPI (rate limit)
│   ├── utils.py            # Generator slotów czasowych (z obsługą duration)
│   ├── sms_mock.py         # Obsługa SMS (mock/produkcja)
│   ├── email_mock.py       # Obsługa e-mail (SMTP/mock — potwierdzenia, przypomnienia, reset hasła)
│   ├── scheduler.py        # APScheduler — automatyczne zadania (auto-complete, reminders)
│   ├── metrics.py          # Prometheus metrics (liczniki, histogramy, middleware)
│   ├── payments.py         # Integracja Stripe
│   ├── routers/
│   │   ├── auth_router.py      # Rejestracja/logowanie/reset hasła
│   │   ├── public_router.py    # Publiczna strona zgłoszenia (z reCAPTCHA)
│   │   ├── dashboard_router.py # Panel serwisanta (zlecenia, kalendarz, CSV export, notatki, status)
│   │   └── admin_router.py     # Panel administracyjny
│   ├── templates/
│   │   ├── base.html
│   │   ├── public/
│   │   │   ├── booking.html        # Strona zgłoszenia sprzętu (typ, marka, model, opis usterki, zdjęcia)
│   │   │   ├── landing.html        # Landing page ServiceHub
│   │   │   ├── confirmation.html
│   │   │   ├── booking_closed.html
│   │   │   └── not_found.html
│   │   ├── dashboard/
│   │   │   ├── base_dashboard.html
│   │   │   ├── login.html
│   │   │   ├── register.html
│   │   │   ├── index.html            # Dashboard z podsumowaniem zleceń i statystykami
│   │   │   ├── bookings.html         # Lista zleceń z danymi sprzętu i statusem
│   │   │   ├── calendar.html         # Widok FullCalendar (miesięczny/tygodniowy)
│   │   │   ├── services.html         # Zarządzanie usługami (CRUD, inline edit)
│   │   │   ├── settings.html
│   │   │   ├── billing.html
│   │   │   ├── preview.html
│   │   │   ├── reset_password_request.html
│   │   │   └── reset_password_form.html
│   │   └── admin/
│   │       ├── base_admin.html
│   │       └── index.html
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── js/
│           └── calendar.js       # Obsługa formularza zgłoszenia (reCAPTCHA, wybór sprzętu)
├── migrations/
│   ├── 001_initial.sql
│   └── 002_servicehub_columns.sql   # Migracja dodająca pola sprzętu RTV/AGD i OrderStatus
└── scripts/
    ├── deploy.sh           # Deploy na VPS
    └── vps-init.sh         # Inicjalizacja VPS
```

## Modele danych

### ServiceProvider (dawniej Provider)
| Pole | Typ | Opis |
|------|-----|------|
| id | Integer | PK |
| email | String(255) | Email serwisanta |
| name | String(255) | Nazwa serwisu / imię i nazwisko |
| slug | String(80) | Unikalny identyfikator w URL |
| hashed_password | String(255) | Hash bcrypt |
| phone | String(20) | Telefon kontaktowy |
| company_name | String(255) | Nazwa firmy |
| is_active | Boolean | Czy konto aktywne |
| is_admin | Boolean | Czy konto admina |
| service_duration | Integer | Domyślny czas naprawy (min) |
| require_deposit | Boolean | Czy wymagać zaliczki |
| deposit_amount | Integer | Kwota zaliczki (w groszach) |
| subscription_status | String | Status subskrypcji |
| subscription_end | DateTime | Koniec subskrypcji |
| stripe_customer_id | String | ID klienta Stripe |
| trial_start | DateTime | Początek okresu próbnego |
| created_at | DateTime | Data rejestracji |

### Order (dawniej Booking)
| Pole | Typ | Opis |
|------|-----|------|
| id | Integer | PK |
| provider_id | Integer | FK → ServiceProvider |
| service_id | Integer | FK → Service (nullable) |
| client_name | String(255) | Imię i nazwisko klienta |
| client_phone | String(20) | Telefon klienta |
| client_email | String(255) | Email klienta (nullable) |
| booking_date | Date | Data dostarczenia / odbioru |
| booking_time | Time | Godzina dostarczenia / odbioru |
| **device_type** | String(50) | Typ sprzętu (tv, washing_machine, fridge, audio, computer, other) |
| **brand** | String(100) | Marka sprzętu |
| **model_name** | String(100) | Model sprzętu |
| **serial_number** | String(100) | Numer seryjny (nullable) |
| **problem_description** | Text | Opis usterki |
| **status_order** | String(20) | Status zlecenia (pending, confirmed, in_progress, completed, cancelled) |
| **repair_cost** | Integer | Koszt naprawy w groszach (nullable) |
| **provider_notes** | Text | Notatki serwisowe (nullable) |
| **photo_paths** | Text | Ścieżki zdjęć (JSON, nullable) |
| duration_minutes | Integer | Czas trwania (min) |
| notes | Text | Notatki (nullable, legacy) |
| status | String(20) | Stary status booking (nullable, dla kompatybilności) |
| stripe_payment_intent | String | ID płatności Stripe (nullable) |
| paid | Boolean | Czy opłacone |
| created_at | DateTime | Data utworzenia |

### Statusy zleceń (OrderStatus)
| Status | Opis |
|--------|------|
| `pending` | Oczekujące — klient złożył zgłoszenie |
| `confirmed` | Potwierdzone — serwisant potwierdził przyjęcie |
| `in_progress` | W naprawie — sprzęt jest naprawiany |
| `completed` | Zrealizowane — naprawa zakończona, do odbioru |
| `cancelled` | Anulowane |

## Licencja

Projekt prywatny — do użytku własnego i komercyjnego.
