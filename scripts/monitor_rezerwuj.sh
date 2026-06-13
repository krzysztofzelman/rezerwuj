#!/bin/bash
# Monitor rezerwuj-app healthcheck - runs every 5 min via cron

LOGFILE=/var/log/rezerwuj-monitor.log
APP_NAME=rezerwuj-app
COMPOSE_DIR=/root/rezerwuj

check_and_log() {
    local label="$1" url="$2"
    local code=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 10 "$url" 2>/dev/null)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $label: $code" >> "$LOGFILE"
    [ "$code" = "200" ] && return 0 || return 1
}

# Docker health status
docker_health=$(docker inspect --format='{{.State.Health.Status}}' "$APP_NAME" 2>/dev/null)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Docker health: ${docker_health:-unknown}" >> "$LOGFILE"

# Internal healthcheck (direct to Docker)
if ! check_and_log "Internal /health" "http://localhost:8002/health"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Internal FAIL - restarting container..." >> "$LOGFILE"
    cd "$COMPOSE_DIR" && docker compose restart "$APP_NAME"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restart issued" >> "$LOGFILE"
fi

# Public healthcheck (via nginx)
check_and_log "Public  /health" "https://rezerwuj.kzelman.pl/health"
