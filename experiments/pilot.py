"""Preexisting 2026-11-05 synthetic policy ablation, not a model benchmark."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from source_trail.core import InputError, build_note, fingerprint, parse_json, selection, validate_packet

PILOT_VERSION = '1.0.0'
DATASET = ROOT / 'experiments/data/pilot-v1.json'
PROTOCOL = ROOT / 'experiments/protocol-v1.json'
POLICIES = ('quote_only', 'exact_span_only', 'full_gate')


def load_dataset(path=DATASET):
    value = parse_json(Path(path).read_bytes())
    if not isinstance(value, dict) or set(value) != {'dataset_version', 'created_on', 'provenance', 'cases'}:
        raise InputError('Unsupported pilot dataset')
    if value['dataset_version'] != PILOT_VERSION or value['created_on'] != '2026-11-05':
        raise InputError('Unsupported pilot dataset version')
    cases = value['cases']
    if not isinstance(cases, list) or not 12 <= len(cases) <= 24:
        raise InputError('The pilot requires 12–24 explicit cases')
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {'id', 'condition', 'description', 'packet', 'selection', 'oracle'}:
            raise InputError('Unsupported pilot case')
        if not isinstance(case['id'], str) or not case['id'] or case['id'] in ids:
            raise InputError('Pilot case IDs must be nonempty and unique')
        ids.add(case['id'])
        oracle = case['oracle']
        if not isinstance(oracle, dict) or set(oracle) != {'selected_spans_valid', 'review_required', 'rationale'}:
            raise InputError('Unsupported independent author oracle')
        if any(type(oracle[key]) is not bool for key in ['selected_spans_valid', 'review_required']):
            raise InputError('Oracle flags must be explicit booleans')
        if not isinstance(oracle['rationale'], str) or not oracle['rationale']:
            raise InputError('Explain each author expectation')
    return value


def run_policy(packet, chosen, policy):
    """Only inputs, never the independent oracle, enter any policy."""
    if policy not in POLICIES:
        raise ValueError('Unknown policy')
    try:
        if policy == 'quote_only':
            # Deliberately weak comparator: resolve IDs and copy quote strings.
            # It does not validate source existence, offsets, text or labels.
            anchors = {anchor['id']: anchor for anchor in packet['anchors']}
            ids = chosen['anchor_ids']
            if not isinstance(ids, list) or not ids or any(not isinstance(item, str) or item not in anchors for item in ids):
                raise InputError('Unresolvable selection')
            quotes = [anchors[item]['quote'] for item in ids]
            if any(not isinstance(quote, str) or not quote for quote in quotes):
                raise InputError('Quote strings required')
        else:
            # Both stronger policies validate the ENTIRE same packet and the
            # same selection. The ablation removes only the annotation gate.
            validated = validate_packet(packet)
            ids = selection(chosen, validated)
            if policy == 'full_gate':
                report = build_note(validated, chosen)
                if report['status'] == 'blocked_disagreement':
                    return {'decision': 'withheld_review', 'failure_class': 'annotated_disagreement', 'quotes': [], 'conflicts': report['conflicts']}
                quotes = [claim['text'] for claim in report['claims']]
            else:
                anchors = {anchor['id']: anchor for anchor in validated['anchors']}
                quotes = [anchors[item]['quote'] for item in ids]
        return {'decision': 'released', 'failure_class': None, 'quotes': quotes, 'conflicts': []}
    except (InputError, KeyError, TypeError, ValueError, RecursionError):
        return {'decision': 'rejected_input', 'failure_class': 'input_validation', 'quotes': [], 'conflicts': []}


def run_case(case):
    oracle = case['oracle']
    results = {}
    for policy in POLICIES:
        result = run_policy(case['packet'], case['selection'], policy)
        released = result['decision'] == 'released'
        result['flags'] = {
            'invalid_selected_citation_released': released and not oracle['selected_spans_valid'],
            'required_review_missed': released and oracle['review_required'],
            'eligible_quote_withheld': not released and oracle['selected_spans_valid'] and not oracle['review_required'],
        }
        results[policy] = result
    return deepcopy(case) | {'case_sha256': fingerprint(case), 'policies': results}


def ratio(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator,
            'rate': round(numerator / denominator, 6) if denominator else None,
            'display': f'{numerator}/{denominator}' if denominator else 'N/A'}


def summarize(rows):
    summary = {}
    invalid = sum(not row['oracle']['selected_spans_valid'] for row in rows)
    review = sum(row['oracle']['review_required'] for row in rows)
    eligible = sum(row['oracle']['selected_spans_valid'] and not row['oracle']['review_required'] for row in rows)
    for policy in POLICIES:
        outputs = [row['policies'][policy] for row in rows]
        summary[policy] = {
            'released_cases': sum(row['decision'] == 'released' for row in outputs),
            'input_rejected_cases': sum(row['decision'] == 'rejected_input' for row in outputs),
            'annotation_hold_cases': sum(row['decision'] == 'withheld_review' for row in outputs),
            'invalid_selected_citation_release': ratio(sum(row['flags']['invalid_selected_citation_released'] for row in outputs), invalid),
            'required_review_miss': ratio(sum(row['flags']['required_review_missed'] for row in outputs), review),
            'eligible_quote_withheld': ratio(sum(row['flags']['eligible_quote_withheld'] for row in outputs), eligible),
        }
    return summary


def experiment(dataset_path=DATASET):
    dataset_path = Path(dataset_path)
    data = load_dataset(dataset_path)
    protocol = parse_json(PROTOCOL.read_bytes())
    rows = [run_case(case) for case in data['cases']]
    evidence = {
        'pilot_version': PILOT_VERSION, 'dataset_version': data['dataset_version'],
        'work_status': 'preexisting-2026-11-05-before-Apart-2026-11-13-sprint',
        'inference_performed': False, 'synthetic_cases_only': True,
        'dataset_sha256': hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        'protocol_sha256': hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        'implementation_sha256': {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in [Path(__file__).resolve(), ROOT / 'source_trail/core.py']},
    }
    conditions = {}
    for row in rows:
        conditions[row['condition']] = conditions.get(row['condition'], 0) + 1
    summary = evidence | {'case_count': len(rows), 'condition_counts': conditions,
                          'metrics': protocol['metrics'], 'policies': summarize(rows),
                          'limitations': protocol['limitations']}
    return {'summary': summary, 'cases': evidence | {'cases': rows}}


def render(summary):
    lines = ['# Source Trail synthetic pilot v1.0.0', '',
             '**Preexisting work dated 2026-11-05; not research performed during the November 13–15 sprint.**', '',
             f"{summary['case_count']} authored synthetic cases; no model, provider, human-participant or factual-truth measurement.", '',
             '| Policy | Invalid selected citation released | Required review missed | Eligible quote withheld | Invalid input rejected | Annotation holds |',
             '|---|---|---|---|---|---|']
    for policy, row in summary['policies'].items():
        lines.append('| ' + ' | '.join([policy, row['invalid_selected_citation_release']['display'],
                    row['required_review_miss']['display'], row['eligible_quote_withheld']['display'],
                    str(row['input_rejected_cases']), str(row['annotation_hold_cases'])]) + ' |')
    lines += ['', 'Each rate is a case count n/N on its declared subset; zero denominators display N/A.',
              'The subsets differ and these metrics must not be added into one accuracy score.', '',
              'Input rejection is distinct from a disagreement hold. The packet-level gates can also withhold',
              'an uncontested selection because an unselected anchor is invalid or another topic is disputed.', '',
              'Read `cases.json` for the input, independent author expectation and actual output of every policy.',
              'Incorrect/missing position annotations cause full-gate misses; compatible quotes with incorrect',
              'different labels cause a full-gate false hold. These failures are intentionally retained.', '',
              '## Limits', ''] + ['- ' + item for item in summary['limitations']]
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='output/pilot-v1', help='A new directory; existing output is never overwritten')
    args = parser.parse_args(argv)
    try:
        result = experiment()
        destination = Path(args.out)
        destination.mkdir(parents=True, exist_ok=False)
        for name in ['summary', 'cases']:
            (destination / f'{name}.json').write_text(json.dumps(result[name], ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        (destination / 'report.md').write_text(render(result['summary']), encoding='utf-8')
        print(json.dumps({'case_count': len(result['cases']['cases']), 'inference_performed': False,
                          'pilot_version': PILOT_VERSION, 'output': str(destination)}))
        return 0
    except (InputError, OSError, ValueError) as error:
        print(json.dumps({'error': type(error).__name__, 'message': str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
