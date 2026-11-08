#!/usr/bin/env python3
"""Playbook Drill, serveur de synchronisation.

Un seul document : data/progress.json. Lecture et écriture protégées par un code
de synchronisation (PD_TOKEN, ou data/token.txt généré au premier démarrage).

  GET  /api/progress?t=CODE   -> le document (404 s'il n'existe pas encore)
  PUT  /api/progress?t=CODE   -> remplace le document (JSON {state, updatedAt})
  GET  /api/health            -> ok

Sans dépendance : bibliothèque standard Python 3.8+.
Avec --static, sert aussi le dossier public/ (pratique en local ; en production nginx s'en charge).
"""
import json, os, sys, secrets, shutil, datetime
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
PUBLIC = os.path.join(ROOT, 'public')
PROGRESS = os.path.join(DATA, 'progress.json')
TOKEN_FILE = os.path.join(DATA, 'token.txt')
MAX_BODY = 1_000_000
STATIC = '--static' in sys.argv or os.environ.get('PD_STATIC') == '1'
PORT = int(os.environ.get('PD_PORT', '8789'))
HOST = os.environ.get('PD_HOST', '127.0.0.1')

os.makedirs(DATA, exist_ok=True)


def load_token():
    t = os.environ.get('PD_TOKEN', '').strip()
    if t:
        return t
    if os.path.exists(TOKEN_FILE):
        return open(TOKEN_FILE, encoding='utf-8').read().strip()
    t = secrets.token_urlsafe(18)
    with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
        f.write(t + '\n')
    os.chmod(TOKEN_FILE, 0o600)
    return t


TOKEN = load_token()


def daily_backup():
    if not os.path.exists(PROGRESS):
        return
    stamp = datetime.date.today().isoformat()
    dest = os.path.join(DATA, f'progress-{stamp}.json')
    if not os.path.exists(dest):
        shutil.copyfile(PROGRESS, dest)
    # garder 30 sauvegardes au plus
    backups = sorted(f for f in os.listdir(DATA) if f.startswith('progress-') and f.endswith('.json'))
    for old in backups[:-30]:
        try:
            os.remove(os.path.join(DATA, old))
        except OSError:
            pass


class Handler(SimpleHTTPRequestHandler):
    server_version = 'PlaybookDrill/1.0'

    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.webmanifest': 'application/manifest+json', '.js': 'text/javascript; charset=utf-8', '.html': 'text/html; charset=utf-8'}

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=PUBLIC, **kw)

    def end_headers(self):
        # la page, le service worker et le manifeste doivent toujours être revalidés, sinon les mises à jour n'arrivent pas
        path = urlparse(self.path).path
        if STATIC and (path in ('/', '/index.html', '/sw.js', '/manifest.webmanifest')):
            self.send_header('Cache-Control', 'no-cache, must-revalidate')
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stdout.write('%s %s\n' % (datetime.datetime.now().isoformat(timespec='seconds'), fmt % args))
        sys.stdout.flush()

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self, query):
        given = (query.get('t', [''])[0] or '').strip()
        if not given:
            auth = self.headers.get('Authorization', '')
            if auth.startswith('Bearer '):
                given = auth[7:].strip()
        return bool(given) and secrets.compare_digest(given, TOKEN)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == '/api/health':
            return self._json(200, {'ok': True, 'exists': os.path.exists(PROGRESS)})
        if u.path == '/api/progress':
            if not self._authorized(parse_qs(u.query)):
                return self._json(401, {'error': 'code de synchronisation manquant ou incorrect'})
            if not os.path.exists(PROGRESS):
                return self._json(404, {'exists': False})
            with open(PROGRESS, 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
            return
        if u.path.startswith('/api/'):
            return self._json(404, {'error': 'inconnu'})
        if STATIC:
            return super().do_GET()
        return self._json(404, {'error': 'le contenu statique est servi par nginx'})

    def do_PUT(self):
        u = urlparse(self.path)
        if u.path != '/api/progress':
            return self._json(404, {'error': 'inconnu'})
        if not self._authorized(parse_qs(u.query)):
            return self._json(401, {'error': 'code de synchronisation manquant ou incorrect'})
        length = int(self.headers.get('Content-Length', '0') or 0)
        if length <= 0 or length > MAX_BODY:
            return self._json(413, {'error': 'taille invalide'})
        raw = self.rfile.read(length)
        try:
            doc = json.loads(raw.decode('utf-8'))
        except Exception:
            return self._json(400, {'error': 'JSON invalide'})
        if not isinstance(doc, dict) or not isinstance(doc.get('state'), dict):
            return self._json(400, {'error': 'document attendu : {state, updatedAt}'})
        doc['updatedAt'] = int(doc.get('updatedAt') or 0)
        doc['savedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
        daily_backup()
        tmp = PROGRESS + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False)
        os.replace(tmp, PROGRESS)
        return self._json(200, {'ok': True, 'updatedAt': doc['updatedAt']})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Allow', 'GET, PUT, OPTIONS')
        self.end_headers()


def main():
    print(f'Playbook Drill sync sur http://{HOST}:{PORT}  (statique : {"oui" if STATIC else "non, nginx"})')
    print(f'Code de synchronisation : {TOKEN}')
    sys.stdout.flush()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == '__main__':
    main()
