import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Date, Time, DateTime,
    ForeignKey, Boolean, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Provider(Base):
    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    phone = Column(String(20), default="")
    company_name = Column(String(200), default="")

    # Domyślne ustawienia usługi
    service_duration = Column(Integer, default=60)  # minuty
    require_deposit = Column(Boolean, default=False)
    deposit_amount = Column(Integer, default=0)  # grosze

    # Stripe
    stripe_account_id = Column(String(100), default="")
    stripe_customer_id = Column(String(100), default="")
    stripe_subscription_id = Column(String(100), default="")
    subscription_status = Column(
        String(20), default="trial"
    )  # trial | active | past_due | canceled | incomplete

    # Trial
    trial_start = Column(Date, nullable=True)
    trial_end = Column(Date, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relacje
    working_hours = relationship(
        "WorkingHour", back_populates="provider", cascade="all, delete-orphan"
    )
    bookings = relationship(
        "Booking", back_populates="provider", cascade="all, delete-orphan"
    )
    blocked_slots = relationship(
        "BlockedSlot", back_populates="provider", cascade="all, delete-orphan"
    )
    services = relationship(
        "Service", back_populates="provider", cascade="all, delete-orphan"
    )

    @property
    def is_trial_active(self) -> bool:
        if not self.trial_end:
            return False
        return datetime.date.today() <= self.trial_end

    @property
    def can_accept_bookings(self) -> bool:
        if not self.is_active:
            return False
        if self.subscription_status == "canceled":
            return False
        if self.subscription_status in ("past_due", "incomplete"):
            return self.is_trial_active
        return True

    @property
    def requires_subscription(self) -> bool:
        if self.subscription_status in ("active", "trial"):
            return False
        if self.is_trial_active:
            return False
        return True


class WorkingHour(Base):
    __tablename__ = "working_hours"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Poniedziałek … 6=Niedziela
    is_working = Column(Boolean, default=True)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    break_start = Column(Time, nullable=True)
    break_end = Column(Time, nullable=True)

    provider = relationship("Provider", back_populates="working_hours")

    __table_args__ = (
        UniqueConstraint("provider_id", "day_of_week", name="uq_provider_day"),
    )


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False)
    name = Column(String(200), nullable=False)
    duration = Column(Integer, nullable=False)  # minuty
    price = Column(Integer, default=0)  # grosze
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    provider = relationship("Provider", back_populates="services")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False)
    client_name = Column(String(100), nullable=False)
    client_surname = Column(String(100), nullable=False)
    client_phone = Column(String(20), nullable=False)
    client_email = Column(String(255), default="")
    booking_date = Column(Date, nullable=False)
    booking_time = Column(Time, nullable=False)
    duration = Column(Integer, default=60)  # minuty
    status = Column(String(20), default="confirmed")  # confirmed | cancelled | completed
    paid = Column(Boolean, default=False)
    payment_intent_id = Column(String(100), default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())

    provider = relationship("Provider", back_populates="bookings")


class BlockedSlot(Base):
    __tablename__ = "blocked_slots"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False)
    block_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    reason = Column(String(255), default="")
    created_at = Column(DateTime, server_default=func.now())

    provider = relationship("Provider", back_populates="blocked_slots")
