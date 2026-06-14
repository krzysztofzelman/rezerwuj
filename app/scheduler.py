"""
Harmonogram zadań — APScheduler.
Uruchamiany w lifespan aplikacji (main.py).
Zadania:
  - auto_complete_past_orders: oznacza przeszłe zlecenia jako zakończone
  - send_reminder_emails: wysyła przypomnienia o zleceniach na następny dzień
"""
import datetime
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.models import Order, ServiceProvider
from app.email_mock import send_booking_reminder_email

logger = logging.getLogger("servicehub.scheduler")

scheduler = AsyncIOScheduler()


def auto_complete_past_orders():
    """Oznacza przeszłe zlecenia jako zakończone (codziennie 3:00)."""
    db = SessionLocal()
    try:
        today = datetime.date.today()
        past_orders = (
            db.query(Order)
            .filter(
                Order.booking_date < today,
                Order.status == "confirmed",
            )
            .all()
        )
        count = 0
        for o in past_orders:
            o.status = "completed"
            count += 1
        if count:
            db.commit()
            logger.info("Auto-completed %d past order(s)", count)
    except Exception as e:
        logger.error("Auto-complete error: %s", e)
    finally:
        db.close()


def send_reminder_emails():
    """Wysyła przypomnienia o zleceniach na następny dzień (codziennie 8:00)."""
    db = SessionLocal()
    try:
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        upcoming = (
            db.query(Order)
            .filter(
                Order.booking_date == tomorrow,
                Order.status == "confirmed",
                Order.client_email != "",
            )
            .all()
        )
        count = 0
        for o in upcoming:
            provider = db.query(ServiceProvider).filter(ServiceProvider.id == o.provider_id).first()
            if provider and o.client_email:
                date_str = o.booking_date.strftime("%d.%m.%Y")
                time_str = o.booking_time.strftime("%H:%M")
                send_booking_reminder_email(
                    o.client_email,
                    o.client_name,
                    provider.name,
                    date_str,
                    time_str,
                    provider.company_name,
                )
                count += 1
        if count:
            logger.info("Sent %d reminder email(s)", count)
    except Exception as e:
        logger.error("Reminder email error: %s", e)
    finally:
        db.close()


def start_scheduler():
    """Rejestruje zadania i uruchamia scheduler."""
    if scheduler.get_jobs():
        logger.warning("Scheduler już uruchomiony")
        return

    scheduler.add_job(
        auto_complete_past_orders,
        CronTrigger(hour=3, minute=0),
        id="auto_complete",
        name="Auto-complete past orders",
        replace_existing=True,
    )
    scheduler.add_job(
        send_reminder_emails,
        CronTrigger(hour=8, minute=0),
        id="send_reminders",
        name="Send order reminders",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("APScheduler uruchomiony (auto-complete 3:00, reminders 8:00)")


def stop_scheduler():
    """Zatrzymuje scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler zatrzymany")
