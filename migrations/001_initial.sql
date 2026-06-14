-- Migration 001: Initial schema for Napraw Mnie
-- Uruchom: sqlite3 napraw_mnie.db < migrations/001_initial.sql

CREATE TABLE IF NOT EXISTS providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    phone TEXT DEFAULT '',
    company_name TEXT DEFAULT '',
    service_duration INTEGER DEFAULT 60,
    require_deposit INTEGER DEFAULT 0,
    deposit_amount INTEGER DEFAULT 0,
    stripe_account_id TEXT DEFAULT '',
    stripe_customer_id TEXT DEFAULT '',
    stripe_subscription_id TEXT DEFAULT '',
    subscription_status TEXT DEFAULT 'trial',
    trial_start DATE,
    trial_end DATE,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS working_hours (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL CHECK(day_of_week >= 0 AND day_of_week <= 6),
    is_working INTEGER DEFAULT 1,
    start_time TEXT,
    end_time TEXT,
    break_start TEXT,
    break_end TEXT,
    UNIQUE(provider_id, day_of_week)
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    duration INTEGER NOT NULL,
    price INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    client_name TEXT NOT NULL,
    client_surname TEXT NOT NULL,
    client_phone TEXT NOT NULL,
    client_email TEXT DEFAULT '',
    booking_date TEXT NOT NULL,
    booking_time TEXT NOT NULL,
    duration INTEGER DEFAULT 60,
    status TEXT DEFAULT 'confirmed' CHECK(status IN ('confirmed', 'cancelled', 'completed')),
    paid INTEGER DEFAULT 0,
    payment_intent_id TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS blocked_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    block_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indeksy dla wydajności
CREATE INDEX IF NOT EXISTS idx_bookings_provider_date
    ON bookings(provider_id, booking_date);
CREATE INDEX IF NOT EXISTS idx_blocked_slots_provider_date
    ON blocked_slots(provider_id, block_date);
CREATE INDEX IF NOT EXISTS idx_working_hours_provider
    ON working_hours(provider_id);
CREATE INDEX IF NOT EXISTS idx_providers_slug
    ON providers(slug);
CREATE INDEX IF NOT EXISTS idx_providers_email
    ON providers(email);
