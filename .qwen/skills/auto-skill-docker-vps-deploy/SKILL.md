---
name: docker-vps-deploy
description: Deploy code changes to a VPS running Docker Compose — rebuild containers, handle database migrations when .dockerignore blocks migration files
source: auto-skill
extracted_at: '2026-06-14T10:24:41.608Z'
---

# Deploy to Docker VPS with Database Migrations

Use when the user wants to push code changes to a production VPS running Docker Compose, including database schema migrations that cannot go through the normal Docker build because `.dockerignore` excludes the `migrations/` directory.

## The challenge

A common pattern: the Dockerfile builds a production image, and `.dockerignore` excludes `migrations/`, `scripts/`, and other development artifacts. This means SQL migration files or helper scripts are **not present** inside the running container — so you cannot simply `docker exec` to run a migration.

Solution: write a self-contained Python migration script that connects directly to the database container, copy it into the application container via `docker cp`, and execute it.

## Prerequisites

- SSH access to the VPS (host, port, password or key)
- The project uses Docker Compose with a database container (PostgreSQL or similar)
- The application container has the database driver installed (e.g., `psycopg2` for PostgreSQL, `sqlite3` for SQLite — these are often in the app's `requirements.txt`)
- Code changes are already committed and pushed to the remote git repository

## Process

### 1. Push code to git

```bash
git add -A
git commit -m "Description of changes"
git push
```

### 2. SSH into the VPS and update the code

```bash
ssh -p <PORT> root@<HOST>
cd /path/to/project
git pull
```

### 3. Rebuild and restart containers

```bash
docker compose down
docker compose up -d --build
```

Wait for containers to become healthy:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

### 4. Check if migration file is accessible inside the container

```bash
docker exec <app-container-name> ls migrations/
```

If the file is missing (likely, due to `.dockerignore`), proceed to step 5.

### 5. Create a self-contained Python migration script

Write a Python script that:

- Connects to the database directly (using the container's internal hostname, e.g., `host="db"` for the sibling container)
- Checks which columns/tables already exist using `information_schema.columns` (PostgreSQL) or `PRAGMA table_info` (SQLite)
- Only adds missing columns — making the script **idempotent** and safe to run multiple times
- Creates indexes with `IF NOT EXISTS`

**PostgreSQL template:**

```python
"""Run database migration inside Docker container."""
import psycopg2

conn = psycopg2.connect(
    host="db",                          # Docker Compose service name
    dbname="<dbname>",
    user="<dbuser>",
    password="<dbpassword>",
)
c = conn.cursor()

# Discover existing columns
c.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name='<table>' AND table_schema='public'"
)
cols = [row[0] for row in c.fetchall()]
print("Existing columns:", cols)

# Define new columns: {name: "TYPE DEFAULT value"}
columns = {
    "new_col_1": "TEXT DEFAULT ''",
    "new_col_2": "INTEGER DEFAULT 0",
    "new_col_3": "VARCHAR(20) DEFAULT 'pending'",
}

for col, dtype in columns.items():
    if col not in cols:
        c.execute(f"ALTER TABLE <table> ADD COLUMN {col} {dtype}")
        print(f"  + Added: {col}")
    else:
        print(f"  - Exists: {col}")

# Add indexes
c.execute("CREATE INDEX IF NOT EXISTS idx_<table>_<col> ON <table>(<col>)")
conn.commit()
conn.close()
print("Migration complete!")
```

### 6. Copy script to the VPS

```bash
# From local machine
scp -P <PORT> /path/to/local/migration_script.py root@<HOST>:/tmp/
```

### 7. Copy script into the Docker container

```bash
ssh -p <PORT> root@<HOST> "docker cp /tmp/migration_script.py <app-container-name>:/tmp/"
```

### 8. Execute the migration inside the container

```bash
ssh -p <PORT> root@<HOST> "docker exec <app-container-name> python3 /tmp/migration_script.py"
```

### 9. Verify the migration

Check that the new columns were added:

```bash
ssh -p <PORT> root@<HOST> "docker exec <app-container-name> python3 -c \"
import psycopg2
conn = psycopg2.connect(host='db', dbname='<dbname>', user='<dbuser>', password='<dbpassword>')
c = conn.cursor()
c.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='<table>'\")
for row in c.fetchall(): print(row[0])
\""
```

### 10. Clean up (optional)

Remove the script from the container and VPS:

```bash
ssh -p <PORT> root@<HOST> "docker exec <app-container-name> rm /tmp/migration_script.py && rm /tmp/migration_script.py"
```

## Alternative: mount migrations as a volume

If you need to run migrations regularly, a more permanent solution is to modify `docker-compose.yml` to mount the `migrations/` directory as a bind volume:

```yaml
services:
  app:
    volumes:
      - ./migrations:/app/migrations:ro
```

Then migrations can be run directly:

```bash
docker exec <app-container-name> psql -U <dbuser> -d <dbname> -f migrations/002_something.sql
```

## Key invariants

- **Idempotency**: The migration script must check what already exists before adding — it should be safe to run multiple times.
- **Password handling**: Database passwords are often environment variables. Look for `${DB_PASSWORD:-default}` patterns in `docker-compose.yml` and `.env.production` files. Use the default or read from the env file.
- **Container hostnames**: Inside Docker Compose, containers can reach each other by service name (e.g., `db`, not `localhost` or `127.0.0.1`).
- **.dockerignore awareness**: Always check the project's `.dockerignore` before relying on any file being inside the container.
- **Connection strings**: The `DATABASE_URL` environment variable in the running container tells you exactly how the app connects — match those credentials in your migration script.
