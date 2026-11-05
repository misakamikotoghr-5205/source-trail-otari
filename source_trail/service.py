from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sqlite3
from .core import InputError, build_note, canonical, fingerprint, parse_json, text, validate_packet
from .provider import ProviderError


class Conflict(ValueError):
    pass


class Service:
    def __init__(self, path, provider):
        if str(path) == ':memory:': raise InputError('Use a persistent audit file')
        self.path, self.provider = str(path), provider
        target = Path(path); target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(target, os.O_CREAT | os.O_RDWR, 0o600); os.close(descriptor); os.chmod(target, 0o600)
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY,intent TEXT NOT NULL,status TEXT NOT NULL,audit TEXT NOT NULL,result TEXT)')

    def suggest(self, raw, goal, key):
        packet = validate_packet(raw); text(goal, 2000)
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{12,128}', key): raise InputError('A 12–128 character idempotency key is required')
        identity = self.provider.identity
        intent = fingerprint({'packet': packet, 'goal': goal, 'provider': identity})
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT intent,status,result FROM requests WHERE key=?', (key,)).fetchone()
            if prior:
                if prior[0] != intent: raise Conflict('Key belongs to a different request')
                if prior[1] == 'complete': return parse_json(prior[2]) | {'replayed': True}
                raise ProviderError('A prior attempt with this key is pending or failed. It is not automatically retried; inspect the audit and hosted usage before explicitly using a new key.')
            audit = {'at': datetime.now(timezone.utc).isoformat(), 'mode': self.provider.mode, 'provider_config': identity, 'intent_sha256': intent, 'packet_sha256': fingerprint(packet), 'source_count': len(packet['sources']), 'anchor_count': len(packet['anchors']), 'goal_sha256': fingerprint(goal), 'status': 'started'}
            db.execute('INSERT INTO requests VALUES (?,?,?,?,NULL)', (key, intent, 'started', canonical(audit)))
        try:
            selected, metadata = self.provider.select(packet, goal)
            report = build_note(packet, selected)
            result = {'report': report, 'provider': metadata, 'replayed': False}
        except Exception as error:
            audit['status'] = 'failed_or_rejected'; audit['error_code'] = 'NO_NOTE_ACCEPTED'
            with sqlite3.connect(self.path) as db: db.execute('UPDATE requests SET status=?,audit=? WHERE key=?', (audit['status'], canonical(audit), key))
            raise ProviderError('No note was accepted. Inspect request audit; this key will not trigger another provider call.') from error
        audit['status'] = 'complete'; audit['report_sha256'] = report['report_sha256']; audit['provider'] = metadata
        with sqlite3.connect(self.path) as db: db.execute('UPDATE requests SET status=?,audit=?,result=? WHERE key=?', ('complete', canonical(audit), canonical(result), key))
        return result

    def audit(self):
        with sqlite3.connect(self.path) as db: return [parse_json(row[0]) for row in db.execute('SELECT audit FROM requests ORDER BY rowid')]
