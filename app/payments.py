"""
Moduł płatności — integracja ze Stripe.
W trybie dev bez kluczy Stripe używa mocków.
"""
import logging
from typing import Optional

import stripe
from sqlalchemy.orm import Session

from app.config import (
    STRIPE_SECRET_KEY,
    STRIPE_PUBLISHABLE_KEY,
    STRIPE_WEBHOOK_SECRET,
    SUBSCRIPTION_PRICE_ID,
    SUBSCRIPTION_PRICE_PLN,
    SITE_URL,
)
from app.models import ServiceProvider, Order

logger = logging.getLogger("napraw_mnie.payments")

stripe.api_key = STRIPE_SECRET_KEY

MOCK_MODE = not STRIPE_SECRET_KEY or STRIPE_SECRET_KEY.startswith("sk_test_...")
if MOCK_MODE and STRIPE_SECRET_KEY:
    # Jeśli klucz istnieje i wygląda na testowy — używamy Stripe
    MOCK_MODE = False


def is_stripe_configured() -> bool:
    """Sprawdza, czy Stripe jest skonfigurowane."""
    return bool(STRIPE_SECRET_KEY) and not MOCK_MODE


# --- Depozyty / zaliczki ---

def create_deposit_checkout(booking: Order, provider: ServiceProvider) -> Optional[str]:
    """
    Tworzy Stripe Checkout Session dla zaliczki.
    Zwraca URL do checkoutu lub None w trybie mock.
    """
    if MOCK_MODE or not provider.deposit_amount:
        logger.info(f"=== MOCK Checkout: zaliczka {provider.deposit_amount} PLN "
                     f"dla rezerwacji #{booking.id} ===")
        return f"{SITE_URL}/mock-payment?booking_id={booking.id}&amount={provider.deposit_amount}"

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card", "blik", "p24"],
            line_items=[{
                "price_data": {
                    "currency": "pln",
                    "product_data": {
                        "name": f"Zaliczka - rezerwacja u {provider.name}",
                        "description": (
                            f"{booking.booking_date} godz. {booking.booking_time.strftime('%H:%M')}"
                        ),
                    },
                    "unit_amount": provider.deposit_amount,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{SITE_URL}/api/{provider.slug}/payment-success/{booking.id}",
            cancel_url=f"{SITE_URL}/api/{provider.slug}/payment-cancel/{booking.id}",
            customer_email=booking.client_email or None,
            metadata={
                "booking_id": str(booking.id),
                "provider_id": str(provider.id),
                "type": "deposit",
            },
        )
        return session.url
    except stripe.error.StripeError as e:
        logger.error(f"Stripe checkout error: {e}")
        return None


# --- Subskrypcje ---

def create_subscription_checkout(provider: ServiceProvider) -> Optional[str]:
    """
    Tworzy Stripe Checkout Session dla subskrypcji miesięcznej.
    Zwraca URL do checkoutu lub None.
    """
    if MOCK_MODE or not SUBSCRIPTION_PRICE_ID:
        logger.info(
            f"=== MOCK Subskrypcja: {SUBSCRIPTION_PRICE_PLN // 100} PLN/miesiąc "
            f"dla {provider.email} ==="
        )
        return f"{SITE_URL}/dashboard/billing?mock_subscription=success"

    try:
        # Upewnij się, że mamy Stripe Customer
        if not provider.stripe_customer_id:
            customer = stripe.Customer.create(
                email=provider.email,
                name=provider.name,
                metadata={"provider_id": str(provider.id)},
            )
            provider.stripe_customer_id = customer.id

        session = stripe.checkout.Session.create(
            payment_method_types=["card", "blik", "p24"],
            line_items=[{
                "price": SUBSCRIPTION_PRICE_ID,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{SITE_URL}/dashboard/billing?subscription=success",
            cancel_url=f"{SITE_URL}/dashboard/billing?subscription=cancel",
            customer=provider.stripe_customer_id,
            metadata={
                "provider_id": str(provider.id),
                "type": "subscription",
            },
        )
        return session.url
    except stripe.error.StripeError as e:
        logger.error(f"Stripe subscription error: {e}")
        return None


def cancel_subscription(provider: ServiceProvider) -> bool:
    """Anuluje subskrypcję Stripe."""
    if MOCK_MODE:
        logger.info(f"=== MOCK Anulowanie subskrypcji dla {provider.email} ===")
        provider.subscription_status = "canceled"
        return True

    if not provider.stripe_subscription_id:
        return False

    try:
        stripe.Subscription.modify(
            provider.stripe_subscription_id,
            cancel_at_period_end=True,
        )
        return True
    except stripe.error.StripeError as e:
        logger.error(f"Stripe cancel error: {e}")
        return False


# --- Webhook ---

def handle_stripe_webhook(payload: bytes, sig_header: str) -> Optional[dict]:
    """
    Obsługuje webhook Stripe.
    Zwraca zdarzenie jako dict lub None jeśli nie udało się zweryfikować.
    """
    if MOCK_MODE or not STRIPE_WEBHOOK_SECRET:
        logger.info("=== MOCK Stripe webhook ===")
        return None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
        return event
    except stripe.error.SignatureVerificationError:
        logger.error("Nieprawidłowy podpis webhooka Stripe")
        return None
    except ValueError:
        logger.error("Nieprawidłowy payload webhooka")
        return None


def process_subscription_event(event: dict, db: Session) -> None:
    """Przetwarza zdarzenie subskrypcyjne ze Stripe."""
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        metadata = data.get("metadata", {})
        if metadata.get("type") == "subscription":
            provider_id = int(metadata.get("provider_id", 0))
            subscription_id = data.get("subscription")
            customer_id = data.get("customer")

            provider = db.query(ServiceProvider).filter(ServiceProvider.id == provider_id).first()
            if provider:
                provider.stripe_subscription_id = subscription_id
                provider.stripe_customer_id = customer_id
                provider.subscription_status = "active"
                db.commit()
                logger.info(f"Subskrypcja aktywna dla provider_id={provider_id}")

    elif event_type == "invoice.paid":
        subscription_id = data.get("subscription")
        provider = (
            db.query(ServiceProvider)
            .filter(ServiceProvider.stripe_subscription_id == subscription_id)
            .first()
        )
        if provider:
            provider.subscription_status = "active"
            provider.is_active = True
            db.commit()
            logger.info(f"Płatność subskrypcji otrzymana dla {provider.email}")

    elif event_type == "invoice.payment_failed":
        subscription_id = data.get("subscription")
        provider = (
            db.query(ServiceProvider)
            .filter(ServiceProvider.stripe_subscription_id == subscription_id)
            .first()
        )
        if provider:
            provider.subscription_status = "past_due"
            db.commit()
            logger.warning(f"Płatność subskrypcji nieudana dla {provider.email}")

    elif event_type == "customer.subscription.deleted":
        subscription_id = data.get("id")
        provider = (
            db.query(ServiceProvider)
            .filter(ServiceProvider.stripe_subscription_id == subscription_id)
            .first()
        )
        if provider:
            provider.subscription_status = "canceled"
            provider.is_active = False
            db.commit()
            logger.info(f"Subskrypcja anulowana dla {provider.email}")
