#!/usr/bin/env bash
# Mise à jour automatique : à lancer à la main (sudo bash deploy/update.sh) ou par cron toutes les heures :
#   0 * * * * root /opt/playbook-drill/deploy/update.sh >> /var/log/playbook-drill-update.log 2>&1
set -euo pipefail

main() {
APP_DIR=/opt/playbook-drill
before=$(git -C "$APP_DIR" rev-parse HEAD)
git -C "$APP_DIR" pull --ff-only --quiet
after=$(git -C "$APP_DIR" rev-parse HEAD)
if [ "$before" != "$after" ]; then
  echo "$(date -Is) mise à jour $before -> $after"
  install -m 644 "$APP_DIR/deploy/playbook-drill.service" /etc/systemd/system/playbook-drill.service
  systemctl daemon-reload
  systemctl restart playbook-drill
  if [ -f /etc/nginx/sites-enabled/playbook-drill ]; then
    install -m 644 "$APP_DIR/deploy/nginx-drill.conf" /etc/nginx/sites-available/playbook-drill && nginx -t && systemctl reload nginx
  fi
fi
}

main "$@"
