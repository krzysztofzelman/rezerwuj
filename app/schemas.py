from pydantic import BaseModel, EmailStr, field_validator, model_validator
from typing import Optional
import re


# === Autentykacja ===
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    slug: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Nieprawidłowy adres e-mail")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Hasło musi mieć co najmniej 8 znaków")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Imię i nazwisko musi mieć co najmniej 2 znaki")
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("Slug może zawierać tylko małe litery, cyfry i myślniki")
        if len(v) < 3:
            raise ValueError("Slug musi mieć co najmniej 3 znaki")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Nieprawidłowy adres e-mail")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 1:
            raise ValueError("Hasło nie może być puste")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# === Publiczna rezerwacja ===
class SlotRequest(BaseModel):
    date: str  # YYYY-MM-DD


class BookRequest(BaseModel):
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    client_name: str
    client_surname: str
    client_phone: str
    client_email: str = ""

    @field_validator("client_name")
    @classmethod
    def validate_client_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Imię musi mieć co najmniej 2 znaki")
        return v

    @field_validator("client_surname")
    @classmethod
    def validate_client_surname(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Nazwisko musi mieć co najmniej 2 znaki")
        return v

    @field_validator("client_phone")
    @classmethod
    def validate_client_phone(cls, v: str) -> str:
        v = v.strip()
        digits = re.sub(r"\D", "", v)
        if len(digits) < 9:
            raise ValueError("Numer telefonu musi mieć co najmniej 9 cyfr")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Nieprawidłowy format daty (YYYY-MM-DD)")
        return v

    @field_validator("time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError("Nieprawidłowy format czasu (HH:MM)")
        return v


# === Dashboard / Ustawienia ===
class HoursUpdate(BaseModel):
    day_of_week: int  # 0-6
    is_working: bool
    start_time: str = ""  # HH:MM
    end_time: str = ""
    break_start: str = ""
    break_end: str = ""

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v: int) -> int:
        if v < 0 or v > 6:
            raise ValueError("Dzień tygodnia musi być w zakresie 0-6")
        return v


class SettingsUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    service_duration: Optional[int] = None
    require_deposit: Optional[bool] = None
    deposit_amount: Optional[int] = None

    @field_validator("service_duration")
    @classmethod
    def validate_duration(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 15:
            raise ValueError("Czas trwania musi wynosić co najmniej 15 minut")
        if v is not None and v > 480:
            raise ValueError("Czas trwania nie może przekraczać 480 minut")
        return v

    @field_validator("deposit_amount")
    @classmethod
    def validate_deposit(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Kwota zaliczki nie może być ujemna")
        return v


class BlockSlotRequest(BaseModel):
    block_date: str
    start_time: str
    end_time: str
    reason: str = ""

    @field_validator("block_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Nieprawidłowy format daty (YYYY-MM-DD)")
        return v

    @field_validator("start_time")
    @classmethod
    def validate_start(cls, v: str) -> str:
        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError("Nieprawidłowy format czasu (HH:MM)")
        return v

    @field_validator("end_time")
    @classmethod
    def validate_end(cls, v: str) -> str:
        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError("Nieprawidłowy format czasu (HH:MM)")
        return v


class ServiceCreate(BaseModel):
    name: str
    duration: int
    price: int = 0

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Nazwa usługi musi mieć co najmniej 2 znaki")
        return v

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if v < 15:
            raise ValueError("Czas trwania musi wynosić co najmniej 15 minut")
        return v


# === Przyjęcie serwisowe (Order) ===

VALID_DEVICE_TYPES = [
    "pralka", "lodówka", "zamrażarka", "piekarnik", "kuchenka",
    "płyta_indukcyjna", "zmywarka", "mikrofalówka", "ekspres_do_kawy",
    "odkurzacz", "telewizor", "monitor", "laptop", "konsola",
    "słuchawki", "głośnik", "inny",
]


class OrderCreate(BaseModel):
    """Tworzenie nowego przyjęcia serwisowego (z publicznego formularza)."""
    client_name: str
    client_surname: str
    client_phone: str
    client_email: str = ""
    device_type: str = "inny"
    brand: str = ""
    model_name: str = ""
    serial_number: str = ""
    problem_description: str = ""

    @field_validator("client_name")
    @classmethod
    def validate_client_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Imię musi mieć co najmniej 2 znaki")
        return v

    @field_validator("client_surname")
    @classmethod
    def validate_client_surname(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Nazwisko musi mieć co najmniej 2 znaki")
        return v

    @field_validator("client_phone")
    @classmethod
    def validate_client_phone(cls, v: str) -> str:
        v = v.strip()
        digits = re.sub(r"\D", "", v)
        if len(digits) < 9:
            raise ValueError("Numer telefonu musi mieć co najmniej 9 cyfr")
        return v

    @field_validator("device_type")
    @classmethod
    def validate_device_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v and v not in VALID_DEVICE_TYPES:
            raise ValueError(f"Nieprawidłowy typ urządzenia. Dozwolone: {', '.join(VALID_DEVICE_TYPES)}")
        return v

    @field_validator("problem_description")
    @classmethod
    def validate_problem(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Opis problemu musi mieć co najmniej 5 znaków")
        return v


class OrderUpdate(BaseModel):
    """Aktualizacja przyjęcia serwisowego (z dashboardu)."""
    status_order: Optional[str] = None  # pending | confirmed | in_progress | completed | cancelled
    repair_cost: Optional[int] = None    # grosze
    notes: Optional[str] = None          # notatka CRM
    provider_notes: Optional[str] = None # notatki serwisowe
    paid: Optional[bool] = None

    @field_validator("status_order")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid = {"pending", "confirmed", "in_progress", "completed", "cancelled"}
            if v not in valid:
                raise ValueError(f"Nieprawidłowy status. Dozwolone: {', '.join(sorted(valid))}")
        return v
