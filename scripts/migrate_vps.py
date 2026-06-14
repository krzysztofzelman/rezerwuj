"""Uruchom migrację Napraw Mnie na bazie SQLite w kontenerze Docker na VPS."""
import sqlite3

DB = "/app/data/napraw_mnie.db"

conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("PRAGMA table_info(bookings)")
cols = [row[1] for row in c.fetchall()]
print("Existing columns:", cols)

needed = [
    "device_type", "brand", "model_name", "serial_number",
    "problem_description", "status_order", "repair_cost",
    "provider_notes", "photo_paths",
]

for col in needed:
    if col not in cols:
        if col == "status_order":
            c.execute("ALTER TABLE bookings ADD COLUMN status_order TEXT DEFAULT 'pending'")
        elif col == "repair_cost":
            c.execute("ALTER TABLE bookings ADD COLUMN repair_cost INTEGER DEFAULT 0")
        else:
            c.execute(f"ALTER TABLE bookings ADD COLUMN {col} TEXT DEFAULT ''")
        print(f"  + Added column: {col}")
    else:
        print(f"  - Exists: {col}")

c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_device_type ON bookings(device_type)")
c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_status_order ON bookings(status_order)")
conn.commit()
conn.close()
print("Migration complete!")
