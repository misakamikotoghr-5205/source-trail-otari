import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .core import InputError, build_note, canonical, fields, parse_json
from .provider import ProviderError
from .service import Conflict


def make_server(address, service, token):
    if not isinstance(token, str) or not 32 <= len(token) <= 256 or not token.isascii() or any(ord(c) < 33 for c in token): raise InputError('SOURCE_TRAIL_API_TOKEN needs 32–256 visible ASCII characters')
    class Handler(BaseHTTPRequestHandler):
        def setup(self): super().setup(); self.connection.settimeout(10)
        def log_message(self, *_): pass
        def reply(self, status, value):
            raw = canonical(value).encode(); self.send_response(status)
            for key, value in {'Content-Type': 'application/json; charset=utf-8', 'Content-Length': str(len(raw)), 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}.items(): self.send_header(key, value)
            self.end_headers(); self.wfile.write(raw)
        def body(self):
            if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1 or self.headers.get_content_type() != 'application/json': raise InputError('A single bounded application/json body is required')
            try: length = int(self.headers['Content-Length'])
            except ValueError: raise InputError('Invalid Content-Length') from None
            if not 1 <= length <= 1_000_000: raise InputError('Body limit is 1 MB')
            return parse_json(self.rfile.read(length))
        def handle_request(self):
            try:
                url = urlsplit(self.path)
                if url.query: raise InputError('No query parameters are supported')
                if self.command == 'GET' and url.path == '/health': return self.reply(200, {'service': 'source-trail', 'mode': service.provider.mode, 'external_search': False})
                auth = self.headers.get('Authorization', '')
                if not auth.isascii() or not hmac.compare_digest(auth, 'Bearer '+token): return self.reply(401, {'error': 'UNAUTHORIZED'})
                if self.command == 'GET' and url.path == '/v1/audit': return self.reply(200, {'requests': service.audit()})
                if self.command == 'POST' and url.path == '/v1/review':
                    body = self.body(); fields(body, {'packet', 'selection'})
                    return self.reply(200, build_note(body['packet'], body['selection']))
                if self.command == 'POST' and url.path == '/v1/suggest':
                    body = self.body(); fields(body, {'packet', 'goal'})
                    return self.reply(200, service.suggest(body['packet'], body['goal'], self.headers.get('Idempotency-Key')))
                self.reply(404, {'error': 'NOT_FOUND'})
            except InputError as error: self.reply(400, {'error': 'INVALID_INPUT', 'message': str(error)})
            except Conflict as error: self.reply(409, {'error': 'KEY_CONFLICT', 'message': str(error)})
            except ProviderError as error: self.reply(503, {'error': 'NO_NOTE_ACCEPTED', 'message': str(error)})
            except Exception: self.reply(503, {'error': 'SERVICE_UNAVAILABLE', 'message': 'No response can be confirmed. Inspect the audit before retrying a hosted request.'})
        do_GET = handle_request
        do_POST = handle_request
    return ThreadingHTTPServer(address, Handler)
