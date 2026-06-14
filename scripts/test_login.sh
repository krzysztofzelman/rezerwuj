#!/bin/bash
# Test login and dashboard access on VPS
DOMAIN="https://rezerwuj.kzelman.pl"
COOKIE_FILE="/tmp/test_cookies.txt"

# Step 1: GET login page to get CSRF cookie
echo "=== Step 1: GET login page ==="
curl -s -c "$COOKIE_FILE" "$DOMAIN/auth/logowanie" > /dev/null

# Extract cookie value: tab-separated, last field
FULL_TOKEN=$(grep "csrf_token" "$COOKIE_FILE" | awk '{print $NF}')
echo "Full cookie: $FULL_TOKEN"

# Raw token = before first dot
RAW_TOKEN="${FULL_TOKEN%%.*}"
echo "Raw token: $RAW_TOKEN"

if [ -z "$RAW_TOKEN" ]; then
    echo "ERROR: No CSRF token found in cookies"
    cat "$COOKIE_FILE"
    exit 1
fi

# Step 2: POST login (without -L to capture cookie properly)
echo ""
echo "=== Step 2: POST login ==="
curl -s -c "$COOKIE_FILE" -b "$COOKIE_FILE" -D /tmp/test_headers2.txt -X POST \
  "$DOMAIN/auth/logowanie" \
  -d "email=admin@naprawmnie.pl&password=Admin123!" \
  -H "X-CSRF-Token: $RAW_TOKEN" -o /tmp/test_login_final.html

echo "HTTP status:"
grep 'HTTP/' /tmp/test_headers2.txt | tail -1
echo "Set-Cookie:"
grep 'set-cookie' /tmp/test_headers2.txt | head -1 | cut -d: -f2 | cut -d';' -f1

# Step 3: Dashboard (no trailing slash - route is /dashboard not /dashboard/)
echo ""
echo "=== Step 3: Dashboard ==="
curl -s -b "$COOKIE_FILE" "$DOMAIN/dashboard" -D /tmp/test_dash_headers.txt \
  -o /tmp/test_dashboard.html
echo "HTTP status:"
grep 'HTTP/' /tmp/test_dash_headers.txt | tail -1
echo "Title:"
grep -oP '(?<=<title>)[^<]+' /tmp/test_dashboard.html
echo "H1:"
grep -oP '<h1[^>]*>[^<]+' /tmp/test_dashboard.html | head -1

# Step 4: Health check
echo ""
echo "=== Step 4: Health check ==="
curl -s "$DOMAIN/health"

# Step 5: Landing page price
echo ""
echo "=== Step 5: Landing page price ==="
curl -s "$DOMAIN/" | grep -oP 'fw-bold">[0-9]+</span>' | head -2

echo ""
echo "=== Step 5b: Register page price ==="
curl -s "$DOMAIN/auth/rejestracja" | grep -oP 'potem[^<]+' | head -2

echo ""
echo "=== Step 6: Bookings page ==="
curl -s -b "$COOKIE_FILE" "$DOMAIN/dashboard/rezerwacje" -D /tmp/test_book_headers.txt -o /tmp/test_booking.html
grep 'HTTP/' /tmp/test_book_headers.txt | tail -1
grep -oP '(?<=<title>)[^<]+' /tmp/test_booking.html

echo ""
echo "=== Step 7: Settings page ==="
curl -s -b "$COOKIE_FILE" "$DOMAIN/dashboard/ustawienia" -D /tmp/test_sett_headers.txt -o /tmp/test_settings.html
grep 'HTTP/' /tmp/test_sett_headers.txt | tail -1
grep -oP '(?<=<title>)[^<]+' /tmp/test_settings.html

echo ""
echo "=== DONE ==="
