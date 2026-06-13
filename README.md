# Rezerwuj — System Rezerwacji Online dla Usługodawców

SaaS do zarządzania rezerwacjami dla małych firm usługowych (fryzjerzy, salony piękności, masażyści).

## Funkcje

### Dla klientów
- **Publiczna strona rezerwacji** — klient wybiera datę i godzinę z dostępnych slotów
- **Formularz** — imię, nazwisko, telefon, e-mail (opcjonalnie)
- **Potwierdzenie SMS** — automatyczny SMS po rezerwacji
- **Płatność online** — opcjonalna zaliczka przez Stripe

### Dla usługodawców
- **Dashboard** — podgląd nadchodzących rezerwacji
- **Ustawienia godzin pracy** — dzień po dniu, z przerwami
- **Blokowanie terminów** — urlop, przerwy, dni wolne
- **Unikalny link** — `{domena}/{slug}` do udostępnienia klientom
- **Subskrypcja** — 14 dni za darmo, potem 79 zł/mies. (Stripe)

## Tech Stack

| Komponent | Technologia |
|-----------|-------------|
| Backend | Python 3.10+ / FastAPI |
| Baza danych | SQLite (developersko) / PostgreSQL (produkcja) |
| Frontend | Jinja2 / Bootstrap 5 / Flatpickr |
| Autentykacja | JWT + bcrypt |
| Płatności | Stripe Checkout / Subskrypcje |
| SMS | SMSAPI.pl / Twilio (mock w development) |

## Szybki start

### 1. Wymagania

- Python 3.10+
- pip

### 2. Instalacja

```bash
# Sklonuj repozytorium
cd rezerwuj

# Zainstaluj zależności
pip install -r requirements.txt

# Skopiuj konfigurację
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
2. Wprowadź dane: e-mail, hasło, nazwę, unikalny slug (np. `fryzjer-janek`)
3. Po rejestracji zostaniesz automatycznie zalogowany
4. Twój publiczny link: http://localhost:8000/{slug}

## Konfiguracja (.env)

| Zmienna | Opis | Domyślnie |
|---------|------|-----------|
| `DATABASE_URL` | URI bazy danych | `sqlite:///./rezerwuj.db` |
| `SECRET_KEY` | Klucz do JWT (zmień w produkcji!) | `dev-secret-key-...` |
| `SITE_URL` | Adres aplikacji | `http://localhost:8000` |
| `STRIPE_SECRET_KEY` | Klucz Secret Stripe | `sk_test_...` |
| `STRIPE_PUBLISHABLE_KEY` | Klucz Publiczny Stripe | `pk_test_...` |
| `STRIPE_WEBHOOK_SECRET` | Sekret webhooka Stripe | `whsec_...` |
| `SUBSCRIPTION_PRICE_ID` | ID produktu Stripe | `price_...` |
| `SMS_API_KEY` | Klucz API SMS | — |
| `SMS_MOCK` | Tryb mock SMS (true=log, false=API) | `true` |
| `TRIAL_DAYS` | Długość okresu próbnego | `14` |

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
Aby włączyć rzeczywiste SMS-y:
1. Załóż konto na [SMSAPI.pl](https://www.smsapi.pl) lub [Twilio](https://twilio.com)
2. Ustaw `SMS_API_KEY` w `.env`
3. Ustaw `SMS_MOCK=false`

## Struktura projektu

```
rezerwuj/
├── .env                    # Konfiguracja lokalna
├── .env.example            # Wzór konfiguracji
├── requirements.txt        # Zależności Pythona
├── README.md               # Ten plik
├── app/
│   ├── main.py             # Główny plik aplikacji (FastAPI)
│   ├── config.py           # Konfiguracja z .env
│   ├── database.py         # Połączenie z bazą (SQLAlchemy)
│   ├── models.py           # Modele ORM (Provider, Booking, etc.)
│   ├── schemas.py          # Schematy Pydantic (walidacja)
│   ├── auth.py             # JWT + bcrypt
│   ├── utils.py            # Generator slotów czasowych
│   ├── sms_mock.py         # Obsługa SMS (mock/produkcja)
│   ├── payments.py         # Integracja Stripe
│   ├── routers/
│   │   ├── auth_router.py      # Rejestracja/logowanie
│   │   ├── public_router.py    # Publiczna strona rezerwacji
│   │   └── dashboard_router.py # Panel usługodawcy
│   ├── templates/
│   │   ├── base.html
│   │   ├── public/
│   │   │   ├── booking.html
│   │   │   ├── confirmation.html
│   │   │   ├── booking_closed.html
│   │   │   └── not_found.html
│   │   └── dashboard/
│   │       ├── base_dashboard.html
│   │       ├── login.html
│   │       ├── register.html
│   │       ├── index.html
│   │       ├── bookings.html
│   │       ├── settings.html
│   │       ├── billing.html
│   │       └── preview.html
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── js/
│           └── calendar.js
└── migrations/
    └── 001_initial.sql     # Schemat bazy danych
```

## Bezpieczeństwo

- **Hasła**: hashowane bcryptem (passlib)
- **JWT**: tokeny z ważnością 72h
- **SQL Injection**: SQLAlchemy ORM (parametryzowane zapytania)
- **Walidacja**: Pydantic (wejście API) + HTML5 (formularze)
- **XSS**: Jinja2 automatycznie escape'uje dane
- **Ciasteczka**: HttpOnly + SameSite=Lax
- **Subskrypcja**: blokada dostępu po anulowaniu/braku płatności

## API Endpoints

### Publiczne
| Metoda | Ścieżka | Opis |
|--------|---------|------|
| GET | `/{slug}` | Strona rezerwacji |
| GET | `/api/{slug}/slots?date=YYYY-MM-DD` | Dostępne sloty |
| POST | `/api/{slug}/book` | Tworzenie rezerwacji |
| GET | `/api/{slug}/info` | Info o usługodawcy |

### Dashboard (wymaga logowania)
| Metoda | Ścieżka | Opis |
|--------|---------|------|
| GET | `/dashboard` | Strona główna |
| GET | `/dashboard/rezerwacje` | Lista rezerwacji |
| GET | `/dashboard/ustawienia` | Ustawienia |
| POST | `/dashboard/ustawienia` | Zapis ustawień |
| POST | `/dashboard/godziny-pracy` | Godziny pracy |
| POST | `/dashboard/blokuj` | Blokada terminu |
| GET | `/dashboard/platnosci` | Subskrypcja/płatności |
| GET | `/dashboard/podglad` | Podgląd linku |

### Autentykacja
| Metoda | Ścieżka | Opis |
|--------|---------|------|
| GET | `/auth/rejestracja` | Formularz rejestracji |
| POST | `/auth/rejestracja` | Rejestracja |
| GET | `/auth/logowanie` | Formularz logowania |
| POST | `/auth/logowanie` | Logowanie |
| GET | `/auth/wyloguj` | Wylogowanie |

### Webhook
| Metoda | Ścieżka | Opis |
|--------|---------|------|
| POST | `/stripe/webhook` | Webhook Stripe |

## Plan rozwoju (TODO)

- [ ] Obsługa PostgreSQL zamiast SQLite
- [ ] Panel admina (zarządzanie wszystkimi tenantami)
- [ ] Eksport rezerwacji do CSV/PDF
- [ ] Przypomnienia SMS/email automatyczne (z harmonogramem)
- [ ] Strona firmowa z portfolio usługodawcy
- [ ] System opinii i ocen po wizycie

## Licencja

Projekt prywatny — do użytku własnego i komercyjnego.
