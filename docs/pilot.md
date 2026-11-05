# Reproducible synthetic pilot 1.0.0 — preexisting preparation

All code, protocol, data and results here were created **2026-11-05**, before the
Apart November 13–15 sprint. This is a mechanism pilot, not a completed sprint
study, preregistration, LLM evaluation or evidence of semantic factual accuracy.
The protocol was declared alongside this dataset/implementation; it was not
independently registered, blinded or held out.

Run from the repository root, with Python 3.12+ and no dependencies:

```sh
python3 experiments/pilot.py --out output/my-pilot-v1
```

Choose a new directory; existing output is never overwritten. The command makes
no network/model call and generates `cases.json`, `summary.json`, `report.md`.
Published, actually executed outputs are in [pilot-v1/report.md](pilot-v1/report.md),
[pilot-v1/summary.json](pilot-v1/summary.json), and [pilot-v1/cases.json](pilot-v1/cases.json).
Re-running yields byte-identical artifacts, without machine paths, timestamps,
random sampling or provider metadata. Outputs bind the original dataset and
protocol byte hashes plus the runner/core code hashes; this is reproducibility
metadata, not a digital signature or external attestation.

## Inputs and comparison

[The dataset](../experiments/data/pilot-v1.json) contains sixteen independently
authored fictional workshop cases and explicit author expectations. It contains
five normal/repaired controls, four invalid selected citations, three labeled
disagreements, two incorrect/missing annotation failures, one compatible-text
false hold and one invalid unselected anchor. No outside dataset, real personal
information or model output was copied. The data is original MIT-licensed text.

All three policies receive exactly the same packet and selection:

| Policy | Validation |
|---|---|
| `quote_only` | Resolve selected IDs and copy quote strings; deliberately checks no source, span or annotation. A weak engineered comparator, not a claim about a particular deployed system. |
| `exact_span_only` | The production `validate_packet` and `selection` functions validate the **entire** packet; selected exact quotes are released without a position-label check. |
| `full_gate` | The same validators plus production `build_note`, which withholds all claims when any topic has differing human position labels. Core implementation is unchanged. |

An independent author oracle records selected-span validity and the intended
need for manual review. Policy execution cannot read it. Review expectations
are deliberately different from erroneous input labels, rather than calculated
from those labels. These are constructed scenario intentions, not independent
expert adjudication or a universal semantic truth standard.

## Declared metrics and observed pilot

The versioned [protocol](../experiments/protocol-v1.json) defines case-level
counts. Four cases have invalid selected citations; five require manual review
under the author oracle; seven have valid selected spans with no review required.
The three metric numerators are respectively invalid-citation releases,
review-required releases, and eligible-quote withholdings. Input rejection and
annotation hold counts are reported separately. Zero denominators produce
`rate: null` / `display: N/A`. Different subsets must not be added into one score.

Actual execution on the declared sixteen cases:

| Policy | Invalid citation released | Review required but released | Eligible quote withheld | Input rejected | Annotation hold |
|---|---|---|---|---|---|
| quote-only | 4/4 | 5/5 | 0/7 | 0 | 0 |
| exact-span-only | 0/4 | 5/5 | 1/7 | 5 | 0 |
| full gate | 0/4 | 2/5 | 2/7 | 5 | 4 |

The full gate misses intended review when competing source texts receive the
same wrong position label or an opposing source has no anchor annotation. It
also holds compatible quotes mislabeled as conflicting. Both stronger policies
reject a packet with an invalid **unselected** anchor, even though its selected
quote is valid. A different-topic disagreement blocks an uncontested selected
door-time quote: this conservative whole-packet cost is visible in that case,
even though its packet-level manual hold was intended by this protocol.

## Limits and dual-use considerations

This tiny authored suite has no representative sampling, held-out set, repeated
trials, confidence interval or real user/model performance claim. The core's
span checks say nothing about source credibility, missing context, semantic
entailment or decision quality. Labels and oracles can both be wrong. Future
research should obtain independent cases/annotations and report the annotation
disagreement itself; do not reuse these hand-designed cases as unseen test data.

Exact-looking quotes can be used to launder misleading excerpts. An operator
could hide sources/annotations, relabel positions or recalculate hashes; these
are not signed independent attestations. We retain complete input context,
expose negative cases and label all outputs human-review-only. Only synthetic
data is present, with no participants or private source documents. Any later
real-data or human study needs its own permissions, privacy and consent review.
