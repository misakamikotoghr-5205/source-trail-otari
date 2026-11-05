# Source Trail synthetic pilot v1.0.0

**Preexisting work dated 2026-11-05; not research performed during the November 13–15 sprint.**

16 authored synthetic cases; no model, provider, human-participant or factual-truth measurement.

| Policy | Invalid selected citation released | Required review missed | Eligible quote withheld | Invalid input rejected | Annotation holds |
|---|---|---|---|---|---|
| quote_only | 4/4 | 5/5 | 0/7 | 0 | 0 |
| exact_span_only | 0/4 | 5/5 | 1/7 | 5 | 0 |
| full_gate | 0/4 | 2/5 | 2/7 | 5 | 4 |

Each rate is a case count n/N on its declared subset; zero denominators display N/A.
The subsets differ and these metrics must not be added into one accuracy score.

Input rejection is distinct from a disagreement hold. The packet-level gates can also withhold
an uncontested selection because an unselected anchor is invalid or another topic is disputed.

Read `cases.json` for the input, independent author expectation and actual output of every policy.
Incorrect/missing position annotations cause full-gate misses; compatible quotes with incorrect
different labels cause a full-gate false hold. These failures are intentionally retained.

## Limits

- Sixteen small authored synthetic cases are a mechanism pilot, not a representative dataset, held-out evaluation, model-performance estimate or statistical generalization.
- No LLM, Otari, external search or human participant is used. No claim is made about semantic truth, entailment, decision quality or source reliability.
- The author oracle is a declared test intention and may be wrong; it was not independently expert-annotated, blinded or adjudicated.
- The quote-only comparator is deliberately weak. Both stronger policies validate the entire packet; this controls their ablation but does not represent every plausible citation system.
- Wrong or missing human labels can hide a needed review; different labels on compatible text can cause a false hold. These cases remain visible rather than relabeled to make the full gate win.
- Whole-packet validation and holds can suppress an otherwise uncontested selected quote. A later study should measure this cost with independently authored real tasks and annotations.
- Version 1.0.0 and all present results were created on 2026-11-05 before the Apart sprint. New sprint work and the required research report remain undone.
