import argparse
import json
import os
from pathlib import Path
import sys
from .core import InputError, build_note, canonical, markdown, parse_json, verify_report
from .http_api import make_server
from .provider import ProviderError, configured
from .service import Conflict, Service


def load(path): return parse_json(Path(path).read_bytes())


def output(value, folder):
    report = value.get('report', value)
    destination = Path(folder); destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    stem = destination/report['report_sha256']
    for suffix, content in [('.json', canonical(value)+'\n'), ('.md', markdown(report))]:
        descriptor = os.open(str(stem)+suffix, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as file: file.write(content)
    return str(stem)+'.md'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Exact-span research notes; no semantic truth guarantee')
    parser.add_argument('--db', default='var/requests.sqlite3')
    sub = parser.add_subparsers(dest='command', required=True)
    review = sub.add_parser('review'); review.add_argument('packet'); review.add_argument('--selection', required=True); review.add_argument('--out', default='output')
    suggest = sub.add_parser('suggest'); suggest.add_argument('packet'); suggest.add_argument('--goal', required=True); suggest.add_argument('--key', required=True); suggest.add_argument('--out', default='output')
    sub.add_parser('audit')
    verify = sub.add_parser('verify'); verify.add_argument('report')
    serve = sub.add_parser('serve'); serve.add_argument('--port', type=int, default=8796)
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify':
            value = load(args.report); valid = verify_report(value.get('report', value) if isinstance(value, dict) else value); print(canonical({'content_hash_valid': valid, 'digital_signature': False})); return 0 if valid else 2
        if args.command == 'review':
            result = build_note(load(args.packet), load(args.selection)); location = output(result, args.out)
        else:
            service = Service(args.db, configured())
            if args.command == 'audit': print(canonical({'requests': service.audit()})); return 0
            if args.command == 'serve':
                if not 1024 <= args.port <= 65535: raise InputError('Port must be 1024–65535')
                server = make_server(('127.0.0.1', args.port), service, os.environ.get('SOURCE_TRAIL_API_TOKEN'))
                print(canonical({'listening': f'http://127.0.0.1:{args.port}', 'mode': service.provider.mode}), flush=True)
                try: server.serve_forever()
                except KeyboardInterrupt: pass
                finally: server.server_close()
                return 0
            result = service.suggest(load(args.packet), args.goal, args.key); location = output(result, args.out)
        report = result.get('report', result)
        print(canonical({'status': report['status'], 'claims': len(report['claims']), 'output': location, 'inference_performed': result.get('provider', {}).get('inference_performed', False)}))
        return 3 if report['status'] == 'blocked_disagreement' else 0
    except (InputError, ProviderError, Conflict, OSError, ValueError) as error:
        print(canonical({'error': type(error).__name__, 'message': str(error)}), file=sys.stderr); return 2


if __name__ == '__main__': raise SystemExit(main())
