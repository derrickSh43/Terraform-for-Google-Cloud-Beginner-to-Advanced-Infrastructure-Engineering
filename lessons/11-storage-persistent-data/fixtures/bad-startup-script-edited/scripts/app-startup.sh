#!/usr/bin/env bash
# Meridian app tier placeholder: a tiny HTTP API on port 8080.
set -euo pipefail

apt-get update
apt-get install -y python3 xfsprogs  # to format the data disk

mkdir -p /opt/meridian-api
echo '{"service": "meridian-api", "status": "ok"}' > /opt/meridian-api/health.json

cat > /etc/systemd/system/meridian-api.service <<'UNIT'
[Unit]
Description=Meridian API placeholder
After=network-online.target

[Service]
WorkingDirectory=/opt/meridian-api
ExecStart=/usr/bin/python3 -m http.server 8080
Restart=always

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now meridian-api
