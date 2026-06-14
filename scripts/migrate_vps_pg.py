"""Uruchom migracje Napraw Mnie na PostgreSQL w kontenerze Docker na VPS."""
import psycopg2

conn = psycopg2.connect(
    host="db",
    dbname="napraw_mnie",
    user="napraw_mnie",
    password="napraw_mnie_secret_2024",
)
c = conn.cursor()

c.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='bookings' AND table_schema='public'"
)
cols = [row[0] for row in c.fetchall()]
print("Existing columns:", cols)

columns = {
    "device_type": "TEXT DEFAULT ''",
    "brand": "TEXT DEFAULT ''",
    "model_name": "TEXT DEFAULT ''",
    "serial_number": "TEXT DEFAULT ''",
    "problem_description": "TEXT DEFAULT ''",
    "status_order": "VARCHAR(20) DEFAULT 'pending'",
    "repair_cost": "INTEGER DEFAULT 0",
    "provider_notes": "TEXT DEFAULT ''",
    "photo_paths": "TEXT DEFAULT ''",
}

for col, dtype in columns.items():
    if col not in cols:
        c.execute(f"ALTER TABLE bookings ADD COLUMN {col} {dtype}")
        print(f"  + Added: {col}")
    else:
        print(f"  - Exists: {col}")

c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_device_type ON bookings(device_type)")
c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_status_order ON bookings(status_order)")
conn.commit()
conn.close()
print("Migration complete!")
