#!/bin/bash
# Deploy script per droplet DigitalOcean (Ubuntu 22/24)
# Lancia su una shell SSH del droplet:
#   curl -fsSL https://raw.githubusercontent.com/USERNAME/feed-enricher/main/deploy/install.sh | bash
# oppure copia/incolla riga per riga.

set -euo pipefail

APP_DIR="/opt/feed-enricher"
APP_USER="${SUDO_USER:-root}"

echo "==> Installazione dipendenze sistema..."
apt-get update
apt-get install -y --no-install-recommends \
    docker.io docker-compose-plugin nginx curl git ufw

systemctl enable --now docker

echo "==> Configurazione firewall (UFW)..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo "==> Setup directory app: $APP_DIR"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

# Se NON usi git, scp/rsync il codice in $APP_DIR prima di lanciare lo script.
# Se usi git pubblico:
# git clone https://github.com/USERNAME/feed-enricher.git .

echo "==> Build immagine Docker..."
docker compose build

echo "==> Avvio container..."
docker compose up -d

echo "==> Configurazione nginx..."
cp deploy/nginx.conf /etc/nginx/sites-available/feed-enricher
ln -sf /etc/nginx/sites-available/feed-enricher /etc/nginx/sites-enabled/feed-enricher
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ""
echo "==> Deploy completo!"
echo "    App in ascolto su: http://$(curl -4 -s ifconfig.me)/"
echo "    Container: docker ps"
echo "    Logs:      docker compose logs -f"
echo "    Update:    cd $APP_DIR && git pull && docker compose up -d --build"
