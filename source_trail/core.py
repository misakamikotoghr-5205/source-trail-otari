from copy import deepcopy
import hashlib
import html
import json
import re


class InputError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def parse_json(raw):
    if not isinstance(raw, (str, bytes)) or len(raw) > 1_000_000:
        raise InputError('JSON input must be at most 1 MB')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise InputError('Duplicate JSON field')
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(InputError('Non-finite JSON value')))
    except (ValueError, UnicodeError, RecursionError) as error:
        raise InputError('Invalid JSON input') from error


def fields(value, required):
    if not isinstance(value, dict) or set(value) != set(required): raise InputError('Object fields do not match the schema')


def text(value, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or '\x00' in value:
        raise InputError('Expected bounded nonblank text')
    try: value.encode('utf-8', errors='strict')
    except UnicodeError as error: raise InputError('Invalid Unicode text') from error
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', value): raise InputError('Invalid identifier')
    return value


def validate_packet(raw):
    fields(raw, {'schema_version', 'title', 'sources', 'anchors'})
    packet = deepcopy(raw)
    if type(packet['schema_version']) is not int or packet['schema_version'] != 1: raise InputError('Unsupported schema version')
    text(packet['title'], 150)
    if not isinstance(packet['sources'], list) or not 1 <= len(packet['sources']) <= 30: raise InputError('Provide 1–30 user-supplied documents')
    sources = {}
    for source in packet['sources']:
        fields(source, {'id', 'title', 'text'})
        identifier(source['id']); text(source['title'], 150); text(source['text'], 20_000)
        if source['id'] in sources: raise InputError('Duplicate source id')
        sources[source['id']] = source
    if sum(len(source['text'].encode()) for source in sources.values()) > 80_000: raise InputError('Document context exceeds 80 KB; split the packet')
    if not isinstance(packet['anchors'], list) or not 1 <= len(packet['anchors']) <= 100: raise InputError('Provide 1–100 user-reviewed quote anchors')
    ids, spans = set(), set()
    for anchor in packet['anchors']:
        fields(anchor, {'id', 'source_id', 'start', 'end', 'quote', 'topic', 'position'})
        for key in ['id', 'source_id', 'topic', 'position']: identifier(anchor[key])
        if anchor['id'] in ids: raise InputError('Duplicate anchor id')
        ids.add(anchor['id'])
        source = sources.get(anchor['source_id'])
        if source is None: raise InputError('Unknown anchor source')
        start, end = anchor['start'], anchor['end']
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source['text']): raise InputError('Anchor offsets are outside the source')
        text(anchor['quote'], 2000)
        if source['text'][start:end] != anchor['quote']: raise InputError('Anchor quote does not match its exact source span')
        span = (anchor['source_id'], start, end)
        if span in spans: raise InputError('The same span cannot be relabeled as independent evidence')
        spans.add(span)
    return packet


def selection(value, packet):
    fields(value, {'anchor_ids'})
    ids = value['anchor_ids']
    known = {anchor['id'] for anchor in packet['anchors']}
    if not isinstance(ids, list) or not 1 <= len(ids) <= 20 or any(not isinstance(item, str) or item not in known for item in ids) or len(ids) != len(set(ids)):
        raise InputError('Selection must contain 1–20 unique, known anchor IDs')
    return list(ids)


def build_note(raw, chosen):
    packet = validate_packet(raw)
    selected = selection(chosen, packet)
    topics = {}
    for anchor in packet['anchors']:
        topics.setdefault(anchor['topic'], {}).setdefault(anchor['position'], []).append(anchor['id'])
    conflicts = [{'topic': topic, 'positions': positions} for topic, positions in sorted(topics.items()) if len(positions) > 1]
    # All source annotations are checked, so a model cannot hide an opposing
    # position simply by selecting only the favorable quote.
    anchors = {anchor['id']: anchor for anchor in packet['anchors']}
    claims = []
    if not conflicts:
        for anchor_id in selected:
            anchor = anchors[anchor_id]
            claims.append({'anchor_id': anchor_id, 'text': anchor['quote'], 'citation': deepcopy(anchor), 'support': 'exact-source-span-only'})
    report = {'schema_version': 1, 'title': packet['title'], 'packet_sha256': fingerprint(packet),
              'status': 'blocked_disagreement' if conflicts else 'ready_for_human_review',
              'proposed_anchor_ids': selected, 'claims': claims, 'conflicts': conflicts,
              'review_anchors': deepcopy(packet['anchors']) if conflicts else [],
              'source_manifest': [{'id': source['id'], 'title': source['title'], 'sha256': hashlib.sha256(source['text'].encode()).hexdigest()} for source in packet['sources']],
              'limitations': ['Claims are verbatim excerpts, never model paraphrases.', 'Exact spans establish textual alignment, not truth, entailment, completeness or source reliability.', 'Disagreements are different user-assigned position labels on the same topic; no semantic contradiction detector is claimed.', 'Missing or incorrectly annotated disagreements cannot be inferred automatically. Read the full document context.']}
    report['report_sha256'] = fingerprint(report)
    return report


def verify_report(report):
    if not isinstance(report, dict): return False
    try:
        copied = deepcopy(report); expected = copied.pop('report_sha256')
        return isinstance(expected, str) and fingerprint(copied) == expected
    except (TypeError, ValueError, KeyError, RecursionError): return False


def markdown(report):
    def safe(value):
        return re.sub(r'([\\`*_{}\[\]()#+.!|>-])', r'\\\1', html.escape(str(value))).replace('\n', ' ')
    lines = ['# '+safe(report['title']), '', 'Status: '+report['status'], '', 'Packet SHA256: '+report['packet_sha256'], '', '## Extractive claims — human review required', '']
    for claim in report['claims']:
        cite = claim['citation']
        lines += ['> '+safe(claim['text']), '', f"Source `{cite['source_id']}` · Unicode offsets [{cite['start']}, {cite['end']}) · anchor `{cite['id']}`", '']
    if report['conflicts']:
        lines += ['No accepted claims are released. Resolve the user-annotated disagreements first.', '', '## Disagreement review', '']
        for conflict in report['conflicts']: lines += ['- '+safe(conflict['topic'])+': '+safe(canonical(conflict['positions']))]
        for anchor in report['review_anchors']: lines += ['', f"- `{anchor['id']}` / `{anchor['source_id']}` / `{anchor['position']}`: "+safe(anchor['quote'])]
    lines += ['', '## Limits', '']+['- '+safe(value) for value in report['limitations']]
    return '\n'.join(lines)+'\n'
