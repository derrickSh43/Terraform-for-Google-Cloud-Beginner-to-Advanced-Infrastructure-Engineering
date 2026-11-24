#!/usr/bin/env bash
# Runs as root on first boot (and every reboot) of the Meridian web VM.
set -euo pipefail

apt-get update
apt-get install -y nginx

cat > /var/www/html/index.html <<'HTML'
<!doctype html>
<title>Meridian Books</title>
<h1>Meridian Books</h1>
<p>Served by NGINX on Compute Engine, provisioned with Terraform.</p>
HTML

systemctl enable --now nginx
