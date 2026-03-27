#!/usr/bin/env bash
# deploy/setup.sh — one-shot VPS bootstrap
set -euo pipefail

echo "==> Installing system packages"
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx ffmpeg \
    postgresql python3.12 python3.12-venv default-jre-headless

echo "==> Installing signal-cli"
SIGNAL_CLI_VERSION="0.13.2"
wget -q "https://github.com/AsamK/signal-cli/releases/download/v${SIGNAL_CLI_VERSION}/signal-cli-${SIGNAL_CLI_VERSION}-Linux.tar.gz" \
    -O /tmp/signal-cli.tar.gz
tar -xzf /tmp/signal-cli.tar.gz -C /usr/local/
ln -sf "/usr/local/signal-cli-${SIGNAL_CLI_VERSION}/bin/signal-cli" /usr/local/bin/signal-cli

echo "==> Creating postgres database"
sudo -u postgres createuser board --no-superuser --no-createdb --no-createrole || true
sudo -u postgres createdb board --owner board || true

echo "==> Creating directories"
mkdir -p /var/board/media /var/www/board /var/www/token-generator /opt/board
chown -R www-data:www-data /var/www/ /var/board/

echo "==> Creating signal user and config directory"
useradd --system --no-create-home signal || true
mkdir -p /var/signal-cli
chown signal:signal /var/signal-cli

echo "==> Installing systemd services"
cp deploy/signal-cli.service /etc/systemd/system/
cp deploy/board.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable signal-cli board

echo "==> Copying nginx configs"
cp nginx/board.conf /etc/nginx/sites-enabled/board.conf
cp nginx/token-generator.conf /etc/nginx/sites-enabled/token-generator.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo ""
echo "==> Next steps (run in order):"
echo "1. Register Signal number (as signal user):"
echo "   sudo -u signal signal-cli --config /var/signal-cli -u +1XXXXXXXXXX register"
echo "2. Verify with SMS code:"
echo "   sudo -u signal signal-cli --config /var/signal-cli -u +1XXXXXXXXXX verify <code>"
echo "3. Create /etc/board.env with TOTP_SECRET, ADMIN_TOKEN, DATABASE_URL, MEDIA_DIR"
echo "4. Deploy backend:   cp -r backend/ /opt/board/ && cd /opt/board/backend && python3.12 -m venv /opt/board/venv && /opt/board/venv/bin/pip install -e ."
echo "5. Run migrations:   cd /opt/board/backend && /opt/board/venv/bin/alembic upgrade head"
echo "6. Start services:   systemctl start signal-cli board"
echo "7. Issue TLS certs:  certbot --nginx -d board.example.com -d token.example.com"
echo "8. Deploy frontend:  cp -r frontend/dist/* /var/www/board/"
echo "9. Deploy token-gen: cp -r token-generator/dist/* /var/www/token-generator/"
