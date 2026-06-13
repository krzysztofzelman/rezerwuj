import os
from dotenv import load_dotenv

load_dotenv()

# === Aplikacja ===
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./rezerwuj.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production-1234567890")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_HOURS = 72
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")

# === Stripe ===
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
SUBSCRIPTION_PRICE_ID = os.getenv("SUBSCRIPTION_PRICE_ID", "")
SUBSCRIPTION_PRICE_PLN = int(os.getenv("SUBSCRIPTION_PRICE_PLN", "7900"))  # grosze

# === SMS ===
SMS_API_KEY = os.getenv("SMS_API_KEY", "")
SMS_SENDER = os.getenv("SMS_SENDER", "Rezerwuj")
SMS_MOCK = os.getenv("SMS_MOCK", "true").lower() == "true"

# === Ogólne ===
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "14"))
MAX_BOOKING_DAYS_AHEAD = int(os.getenv("MAX_BOOKING_DAYS_AHEAD", "60"))

# === Stripe Product price (fallback) ===
STRIPE_CURRENCY = "pln"
