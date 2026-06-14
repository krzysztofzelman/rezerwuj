-- Migration 002: ServiceHub — dodanie kolumn dla napraw RTV/AGD
-- Uruchom: sqlite3 rezerwuj.db < migrations/002_servicehub_columns.sql
-- UWAGA: Dla PostgreSQL należy użyć ALTER TABLE ... ADD COLUMN z USING dla status_order

-- Nowe kolumny w tabeli bookings (Order)
ALTER TABLE bookings ADD COLUMN device_type TEXT DEFAULT '';
ALTER TABLE bookings ADD COLUMN brand TEXT DEFAULT '';
ALTER TABLE bookings ADD COLUMN model_name TEXT DEFAULT '';
ALTER TABLE bookings ADD COLUMN serial_number TEXT DEFAULT '';
ALTER TABLE bookings ADD COLUMN problem_description TEXT DEFAULT '';
ALTER TABLE bookings ADD COLUMN status_order TEXT DEFAULT 'pending' CHECK(status_order IN ('pending', 'confirmed', 'in_progress', 'completed', 'cancelled'));
ALTER TABLE bookings ADD COLUMN repair_cost INTEGER DEFAULT 0;
ALTER TABLE bookings ADD COLUMN provider_notes TEXT DEFAULT '';
ALTER TABLE bookings ADD COLUMN photo_paths TEXT DEFAULT '';

-- Indeksy dla nowych kolumn
CREATE INDEX IF NOT EXISTS idx_bookings_device_type ON bookings(device_type);
CREATE INDEX IF NOT EXISTS idx_bookings_status_order ON bookings(status_order);
