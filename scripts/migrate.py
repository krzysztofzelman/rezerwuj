#!/usr/bin/env python3
"""Migracja danych z SQLite do PostgreSQL.

Uruchomienie lokalne:
    python scripts/migrate.py sqlite:///./data/rezerwuj.db postgresql://user:pass@host:5432/rezerwuj

Uruchomienie na VPS (w kontenerze tymczasowym):
    docker run --rm \
        -v rezerwuj_rezerwuj-data:/old-data \
        --network rezerwuj_default \
        rezerwuj-app \
        python scripts/migrate.py sqlite:///old-data/rezerwuj.db postgresql://rezerwuj:pass@db:5432/rezerwuj
"""

import sys
import os
import logging

# Dodaj katalog główny projektu do ścieżki Pythona
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("migrate")

# Kolejność tabel — zależności od kluczy obcych najpierw
TABLE_ORDER = [
    "providers",
    "working_hours",
    "services",
    "bookings",
    "blocked_slots",
]


def get_table_data(sqlite_engine, table_name: str) -> list[dict]:
    """Pobiera wszystkie wiersze z tabeli SQLite."""
    from sqlalchemy import text

    with sqlite_engine.connect() as conn:
        rows = conn.execute(text(f"SELECT * FROM {table_name}")).mappings().all()
        data = [dict(row) for row in rows]

    # Konwersja typów SQLite → PostgreSQL
    for row in data:
        for key, value in list(row.items()):
            # SQLite boolean (0/1) → Python bool
            if isinstance(value, int) and key.startswith("is_") or key in ("paid", "require_deposit", "is_working", "is_active", "is_admin"):
                row[key] = bool(value)
    return data


def migrate():
    if len(sys.argv) != 3:
        print(f"Użycie: {sys.argv[0]} <SQLITE_URL> <POSTGRES_URL>")
        print(f"   np.: {sys.argv[0]} sqlite:///./data/rezerwuj.db postgresql://user:pass@host:5432/rezerwuj")
        sys.exit(1)

    sqlite_url = sys.argv[1]
    pg_url = sys.argv[2]

    from sqlalchemy import create_engine, text

    # ---- 1. Połącz z SQLite ----
    logger.info(f"Łączę z SQLite: {sqlite_url}")
    sqlite_engine = create_engine(sqlite_url)
    try:
        with sqlite_engine.connect() as conn:
            tables = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'alembic_%'"
            )).scalars().all()
        logger.info(f"Znalezione tabele w SQLite: {tables}")
    except Exception as e:
        logger.error(f"Nie można połączyć z SQLite: {e}")
        sys.exit(1)

    # ---- 2. Pobierz dane z SQLite ----
    all_data = {}
    for table in TABLE_ORDER:
        if table not in tables:
            logger.warning(f"Tabela '{table}' nie istnieje w SQLite, pomijam")
            continue
        rows = get_table_data(sqlite_engine, table)
        all_data[table] = rows
        logger.info(f"  {table}: {len(rows)} wierszy")

    # ---- 3. Połącz z PostgreSQL ----
    logger.info(f"Łączę z PostgreSQL: {pg_url}")
    pg_engine = create_engine(pg_url)

    # ---- 4. Stwórz schemat ----
    logger.info("Tworzę tabele w PostgreSQL...")
    from app.database import Base
    import app.models  # noqa: F401 — rejestruje modele w Base.metadata
    Base.metadata.create_all(bind=pg_engine)

    # ---- 5. Wyczyść istniejące dane (na wypadek restartu migracji) ----
    with pg_engine.connect() as conn:
        for table in reversed(TABLE_ORDER):
            if table in all_data:
                conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
        conn.commit()
    logger.info("Wyczyszczono stare dane w PostgreSQL")

    # ---- 6. Wstaw dane w poprawnej kolejności ----
    from sqlalchemy import inspect
    pg_inspector = inspect(pg_engine)

    for table_name in TABLE_ORDER:
        rows = all_data.get(table_name, [])
        if not rows:
            continue

        # Pobierz kolumny tabeli
        columns = [col["name"] for col in pg_inspector.get_columns(table_name)]
        logger.info(f"Wstawiam {len(rows)} wierszy do {table_name} (kolumny: {columns})")

        # Filtruj tylko kolumny istniejące w docelowej tabeli
        for row in rows:
            for key in list(row.keys()):
                if key not in columns:
                    del row[key]

        # Wstaw batchami po 100
        batch_size = 100
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            with pg_engine.connect() as conn:
                placeholders = ", ".join([f":{c}" for c in columns])
                stmt = text(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})")
                conn.execute(
                    stmt,
                    [{c: r[c] for c in columns} for r in batch]
                )
                conn.commit()
        logger.info(f"  ✅ {table_name}: {len(rows)} wierszy")

    # ---- 7. Zresetuj sekwencje ----
    logger.info("Resetuję sekwencje PostgreSQL...")
    with pg_engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name, column_name, 
                   pg_get_serial_sequence(table_name, column_name) AS seq_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND column_default LIKE 'nextval%%'
        """))
        for row in result:
            seq = row.seq_name
            if seq:
                conn.execute(text(f"SELECT setval('{seq}', COALESCE((SELECT MAX({row.column_name}) FROM {row.table_name}), 1))"))
        conn.commit()

    logger.info("🎉 Migracja zakończona sukcesem!")
    logger.info(f"  SQLite: {sqlite_url}")
    logger.info(f"  PostgreSQL: {pg_url}")
    logger.info(f"  Przeniesiono tabele: {[t for t in TABLE_ORDER if t in all_data]}")


if __name__ == "__main__":
    migrate()
