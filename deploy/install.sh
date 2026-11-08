#!/usr/bin/env bash
# Installation ou mise à jour d'Playbook Drill sur la VM (Debian/Ubuntu, nginx).
# Usage :  sudo bash deploy/install.sh
# Idempotent : relancer après chaque git pull, ou utiliser deploy/update.sh.
set -euo pipefail

main() {

APP_DIR=/opt/playbook-drill
DOMAIN=drill.eldwin-uk.com
REPO_URL="${REPO_URL:-git@github.com:MAREESOL87/playbook-drill.git}"

if [ "$(id -u)" -ne 0 ]; then echo "Lance avec sudo."; exit 1; fi

# 1. Code
if [ ! -d "$APP_DIR/.git" ]; then
  if [ -d "$(pwd)/.git" ] && [ -f "$(pwd)/server/server.py" ]; then
    echo "Copie du dépôt courant vers $APP_DIR"
    mkdir -p "$APP_DIR"; cp -R "$(pwd)/." "$APP_DIR/"
  else
    echo "Clonage de $REPO_URL vers $APP_DIR"
    git clone "$REPO_URL" "$APP_DIR"
  fi
else
  git -C "$APP_DIR" pull --ff-only
fi

# 2. Utilisateur de service et dossier de données
id -u playbook-drill >/dev/null 2>&1 || useradd --system --shell /usr/sbin/nologin --home "$APP_DIR" playbook-drill
mkdir -p "$APP_DIR/data"
chown -R playbook-drill:playbook-drill "$APP_DIR/data"
chmod 750 "$APP_DIR/data"

# 3. Service systemd
install -m 644 "$APP_DIR/deploy/playbook-drill.service" /etc/systemd/system/playbook-drill.service
systemctl daemon-reload
systemctl enable playbook-drill >/dev/null
systemctl restart playbook-drill
sleep 1
systemctl --no-pager --lines=3 status playbook-drill || true

# 4. Serveur web en façade
WEB_HINT=""
if command -v nginx >/dev/null; then
  install -m 644 "$APP_DIR/deploy/nginx-drill.conf" /etc/nginx/sites-available/playbook-drill
  ln -sf /etc/nginx/sites-available/playbook-drill /etc/nginx/sites-enabled/playbook-drill
  nginx -t && systemctl reload nginx
  WEB_HINT="   2. HTTPS : sudo certbot --nginx -d $DOMAIN"
elif command -v docker >/dev/null && docker ps --format '{{.Names}} {{.Image}}' 2>/dev/null | grep -qi caddy; then
  CADDY=$(docker ps --format '{{.Names}} {{.Image}}' | grep -i caddy | head -1 | cut -d' ' -f1)
  NET=$(docker inspect "$CADDY" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' | head -1)
  GW=$(docker network inspect "$NET" --format '{{(index .IPAM.Config 0).Gateway}}' 2>/dev/null || echo 172.17.0.1)
  CADDYFILE=$(docker inspect "$CADDY" --format '{{range .Mounts}}{{if eq .Destination "/etc/caddy/Caddyfile"}}{{.Source}}{{end}}{{end}}')
  WEB_HINT="   2. Caddy (conteneur $CADDY) : ajouter à ${CADDYFILE:-son Caddyfile} le bloc
        drill.eldwin-uk.com {
            encode gzip
            reverse_proxy $GW:8789
        }
      puis : docker exec $CADDY caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
      (HTTPS automatique, pas de certbot)"
else
  WEB_HINT="   2. Aucun serveur web détecté : voir deploy/nginx-drill.conf ou deploy/Caddyfile.snippet"
fi

echo
echo "================================================================"
echo " Playbook Drill installé."
echo " Code de synchronisation (à coller une fois dans l'app, onglet Progression) :"
echo "   $(cat "$APP_DIR/data/token.txt")"
echo
echo " Étapes restantes si c'est la première installation :"
echo "   1. DNS : enregistrement A  drill  ->  IP statique de la VM (même IP que sync.eldwin-uk.com)"
echo "$WEB_HINT"
echo "   3. Ouvrir https://$DOMAIN, puis Partager -> Sur l'écran d'accueil"
echo "================================================================"
}

main "$@"
