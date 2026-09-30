#!/usr/bin/env bash
# Add-on entrypoint; output goes to the add-on's Log tab.

set -euo pipefail

mkdir -p /data

# 1. First start: import a database from the Samba share if one exists.
IMPORT=/share/bar_inventory/bar.db
if [ ! -f /data/bar.db ] && [ -f "$IMPORT" ]; then
    cp "$IMPORT" /data/bar.db
    echo "[bar] First start: imported the database from share/bar_inventory/bar.db"
fi

# 2. First start: self-signed certificate, since phone cameras need HTTPS.
CERT=/data/tls/cert.pem
KEY=/data/tls/key.pem
if [ ! -f "$CERT" ]; then
    mkdir -p /data/tls
    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
        -subj "/CN=bar-inventory" -keyout "$KEY" -out "$CERT" 2>/dev/null
    echo "[bar] Made a self-signed HTTPS certificate"
fi

cd /app

# 3. Create or upgrade tables once, so the two servers can't race.
python -c "from app.db import init_db; init_db()"

# Forward Home Assistant's SIGTERM to both servers.
stopping=0
trap 'stopping=1; kill $(jobs -p) 2>/dev/null || true' TERM INT

# 4. Two servers: :8000 HTTP for the iPad panel, :8443 HTTPS for phone cameras.
# Both share /data/bar.db.
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
uvicorn app.main:app --host 0.0.0.0 --port 8443 \
    --ssl-keyfile "$KEY" --ssl-certfile "$CERT" &

echo "[bar] Up: http://<pi>:8000  and  https://<pi>:8443"

# If either server exits unexpectedly, stop the add-on so the watchdog restarts it.
wait -n || true
if [ "$stopping" = 0 ]; then
    echo "[bar] A server stopped unexpectedly -- exiting so the add-on restarts"
    kill $(jobs -p) 2>/dev/null || true
    wait || true
    exit 1
fi
wait || true
echo "[bar] Stopped"
