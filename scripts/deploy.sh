#!/bin/bash
# Skrypt inicjalizujący wdrożenie ServiceHub na VPS
# Uruchom: bash scripts/deploy.sh
set -e

DOMAIN="rezerwuj.kzelman.pl"
REPO_DIR="/root/rezerwuj"
EMAIL="krzysztof@zelman.pl"
APP_PORT=8002

echo "=== Krok 1: Klonowanie repozytorium ==="
if [ -d "$REPO_DIR" ]; then
    cd $REPO_DIR && git pull
else
    git clone git@github.com:krzysztofzelman/rezerwuj.git $REPO_DIR
    cd $REPO_DIR
fi

echo "=== Krok 2: Konfiguracja .env.production ==="
if [ ! -f "$REPO_DIR/.env.production" ]; then
    cat > .env.production << 'EOF'
DATABASE_URL=sqlite:///./data/servicehub.db
SECRET_KEY=change-this-to-a-long-random-secret-key-for-production
SITE_URL=https://$DOMAIN
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
SUBSCRIPTION_PRICE_ID=
SMS_API_KEY=
SMS_SENDER=ServiceHub
SMS_MOCK=true
TRIAL_DAYS=14
MAX_BOOKING_DAYS_AHEAD=60
SUBSCRIPTION_PRICE_PLN=4900
EOF
fi

# Generuj SECRET_KEY jeśli placeholder
CURRENT_KEY=$(grep SECRET_KEY .env.production | cut -d= -f2)
if [ "$CURRENT_KEY" = "change-this-to-a-long-random-secret-key-for-production" ] || [ -z "$CURRENT_KEY" ]; then
    NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$NEW_KEY/" .env.production
    echo "SECRET_KEY wygenerowany"
fi

echo "=== Krok 3: Uruchomienie aplikacji (Docker) ==="
docker compose up -d

echo "=== Krok 4: Konfiguracja Nginx (host) ==="
mkdir -p /var/www/certbot

cat > /etc/nginx/sites-available/$DOMAIN << NGINX_EOF
server {
    listen 80;
    server_name $DOMAIN;
    server_tokens off;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    server_tokens off;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX_EOF

ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN

echo "=== Krok 5: Pobranie certyfikatu SSL ==="
certbot certonly --webroot -w /var/www/certbot \
    --email $EMAIL --agree-tos --no-eff-email -d $DOMAIN

echo "=== Krok 6: Przeładowanie Nginx ==="
nginx -t && nginx -s reload

echo "=== Krok 7: Sprawdzenie statusu ==="
docker compose ps

echo ""
echo "Wdrożenie zakończone!"
echo "https://$DOMAIN"
