from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from experiments.pilot import ROOT, experiment, load_dataset, ratio, run_case, summarize


class PilotTests(unittest.TestCase):
    def test_ablation_exposes_citation_failures_and_wrong_or_missing_annotation_limits(self):
        result = experiment()
        rows = {row['id']: row for row in result['cases']['cases']}
        self.assertEqual(len(rows), 16)
        self.assertFalse(result['summary']['inference_performed'])
        expected = {
            'quote_only': (4, 5, 0, 0, 0),
            'exact_span_only': (0, 5, 1, 5, 0),
            'full_gate': (0, 2, 2, 5, 4),
        }
        for policy, values in expected.items():
            actual = result['summary']['policies'][policy]
            metrics = ['invalid_selected_citation_release', 'required_review_miss', 'eligible_quote_withheld']
            self.assertEqual(tuple(actual[key]['numerator'] for key in metrics) + (actual['input_rejected_cases'], actual['annotation_hold_cases']), values)
            self.assertEqual(tuple(actual[key]['denominator'] for key in metrics), (4, 5, 7))
        for case_id in ['missing_source', 'absent_quote', 'moved_offsets', 'utf8_offsets_used_as_codepoints']:
            self.assertTrue(rows[case_id]['policies']['quote_only']['flags']['invalid_selected_citation_released'])
            for policy in ['exact_span_only', 'full_gate']:
                self.assertEqual(rows[case_id]['policies'][policy]['decision'], 'rejected_input')
        for case_id in ['wrong_same_position_labels', 'missing_opposing_annotation']:
            self.assertTrue(rows[case_id]['policies']['full_gate']['flags']['required_review_missed'])
        self.assertTrue(rows['compatible_quotes_wrong_distinct_labels']['policies']['full_gate']['flags']['eligible_quote_withheld'])
        self.assertEqual(rows['invalid_unselected_anchor']['policies']['full_gate']['decision'], 'rejected_input')
        self.assertEqual(rows['disagreement_opposition_omitted']['policies']['full_gate']['decision'], 'withheld_review')
        # Both stronger policies validate the entire packet, not only selected IDs.
        for row in rows.values():
            if row['policies']['exact_span_only']['decision'] == 'rejected_input':
                self.assertEqual(row['policies']['full_gate']['decision'], 'rejected_input')

    def test_independent_oracle_changes_scoring_not_policy_behavior_and_empty_subsets_are_na(self):
        original = load_dataset()['cases'][0]
        before = deepcopy(original)
        alternate = deepcopy(original)
        alternate['oracle']['review_required'] = True
        first, second = run_case(original), run_case(alternate)
        self.assertEqual(original, before)
        for policy in first['policies']:
            one, two = first['policies'][policy], second['policies'][policy]
            self.assertEqual({key: val for key, val in one.items() if key != 'flags'}, {key: val for key, val in two.items() if key != 'flags'})
            self.assertFalse(one['flags']['required_review_missed'])
            self.assertTrue(two['flags']['required_review_missed'])
        self.assertEqual(ratio(0, 0), {'numerator': 0, 'denominator': 0, 'rate': None, 'display': 'N/A'})
        for policy in summarize([]).values():
            self.assertEqual(policy['invalid_selected_citation_release']['display'], 'N/A')
            self.assertIsNone(policy['required_review_miss']['rate'])

    def test_actual_cli_is_reproducible_matches_published_artifacts_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            outputs = [Path(temporary) / str(index) for index in range(2)]
            for destination in outputs:
                result = subprocess.run([sys.executable, 'experiments/pilot.py', '--out', str(destination)], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['case_count'], 16)
            for name in ['summary.json', 'cases.json', 'report.md']:
                self.assertEqual((outputs[0] / name).read_bytes(), (outputs[1] / name).read_bytes())
                self.assertEqual((outputs[0] / name).read_bytes(), (ROOT / 'docs/pilot-v1' / name).read_bytes())
            previous = (outputs[0] / 'summary.json').read_bytes()
            repeated = subprocess.run([sys.executable, 'experiments/pilot.py', '--out', str(outputs[0])], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(repeated.returncode, 2)
            self.assertNotIn('Traceback', repeated.stderr)
            self.assertEqual(previous, (outputs[0] / 'summary.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
