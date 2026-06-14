import os
from dotenv import load_dotenv

load_dotenv()

# === Aplikacja ===
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./napraw_mnie.db")
SECRET_KEY = os.getenv("SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_HOURS = 72
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")

# === Stripe ===
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
SUBSCRIPTION_PRICE_ID = os.getenv("SUBSCRIPTION_PRICE_ID", "")
SUBSCRIPTION_PRICE_PLN = int(os.getenv("SUBSCRIPTION_PRICE_PLN", "4900"))  # grosze

# === SMS ===
SMS_API_KEY = os.getenv("SMS_API_KEY", "")
SMS_SENDER = os.getenv("SMS_SENDER", "NaprawMnie")
SMS_MOCK = os.getenv("SMS_MOCK", "true").lower() == "true"

# === E-mail (SMTP) ===
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "Napraw Mnie <noreply@naprawmnie.pl>")
EMAIL_MOCK = os.getenv("EMAIL_MOCK", "true").lower() == "true"

# === reCAPTCHA ===
RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")

# === Redis ===
REDIS_URL = os.getenv("REDIS_URL", "")

# === Ogólne ===
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "14"))
MAX_BOOKING_DAYS_AHEAD = int(os.getenv("MAX_BOOKING_DAYS_AHEAD", "60"))

# === Admin ===
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@naprawmnie.pl")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# === Stripe Product price (fallback) ===
STRIPE_CURRENCY = "pln"
