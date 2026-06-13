#!/bin/bash
set -euo pipefail

cd /root/rezerwuj

# Generuj SECRET_KEY
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env.production
echo "SECRET_KEY wygenerowany"

# Uruchom aplikację
docker compose up -d
sleep 3
docker compose ps
echo "Aplikacja uruchomiona (port 8002)"
