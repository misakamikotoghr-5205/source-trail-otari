# Source Trail

**Preexisting work: all current code, synthetic data, pilot results and documents
were created on 2026-11-05, before the Apart Research November 13–15, 2026 sprint.
They are preparation, not research performed during that future event.** The
current target is [Apart AI x Epistemics, Track 2/3](docs/competition.md); signup,
new sprint-period research and the required research-report PDF remain undone.
Otari is an optional provider adapter; Mozilla is only a
[historical candidate, not counted as a selected event](docs/mozilla-candidate.md).

Turn a user-supplied document packet into **extractive, source-aligned research
notes**. Every accepted claim is a verbatim quote with exact source offsets. A
model can choose relevant anchors, but cannot invent a quote, paraphrase a claim,
change its position label or hide a user-annotated disagreement by omission.

This is a private CLI/JSON API, not a web crawler, customer-support policy bot or
fact-checking service. Quotation and citation workflows already exist; the
[landscape comparison](docs/landscape.md) documents the narrower implementation.

## Offline run

Python 3.12+, standard library only, no install or account required:

```sh
python3 -m source_trail review examples/notes.json --selection examples/selection.json --out output
python3 -m source_trail review examples/disagreement.json --selection examples/selection.json --out output
# The second command exits 3: disagreement holds all accepted claims.
python3 -m source_trail --db var/requests.sqlite3 suggest examples/notes.json --goal 'Plan the workshop' --key workshop-research-001
python3 -m source_trail --db var/requests.sqlite3 audit
```

`review` is a pure local review/export and never initializes a provider. Default
`suggest` uses the first 20 anchors as an **explicit offline fixture** and reports
`inference_performed: false`. It stores an idempotent request/result in SQLite.
Reports use their hash as the output filename, with JSON and escaped Markdown.
Examples are fictional, independently authored workshop notes.

## What the gates actually prove

Each packet has sources (`id`, `title`, full `text`) and user-reviewed anchors:
`id`, `source_id`, `start`, `end`, `quote`, `topic`, `position`. Offsets are zero-based
**Unicode code points**, end-exclusive; they are not UTF-8 bytes or JavaScript
UTF-16 indices. The source substring must exactly equal the provided quote.
No normalization, fuzzy relocation or silent truncation is applied. Changing a
source changes its manifest/packet hash; stale offsets fail when their text moves.

Accepted claim text is exactly the quote, never a model-authored paraphrase.
Unknown/duplicate selected IDs, extra claim fields, mismatched quotations,
out-of-bounds offsets, duplicate spans and unknown source IDs fail validation.
All packet annotations are checked independently of the model selection. If the
same topic has different **user-assigned position labels**, all accepted claims
are withheld and the report shows a disagreement review list. This is a
deterministic annotation gate, **not semantic contradiction detection**. Incorrect
or missing annotations cannot be detected automatically. Distinct labels may
describe compatible positions and require a person's resolution.

An exact quote is not proof of truth, source reliability, completeness, or
semantic entailment. Excerpts can omit qualifiers; review the complete supplied
documents. Hash verification detects changes, not authorship or deliberate
recalculation. There is no digital signature or trusted external verification.
Packets are bounded to 30 documents, 20,000 characters each, 80 KB aggregate UTF-8
document context, 100 anchors and 20 selected quotes. Oversized input is rejected,
never silently removed from context.

## Versioned synthetic pilot

```sh
python3 experiments/pilot.py --out output/my-pilot-v1
```

This runs sixteen original synthetic cases through the same packet/selection
under quote-only, exact-span-only and full-gate policies. A new output directory
gets reproducible per-case JSON, summary and Markdown, with dataset/protocol/code
hashes. [Protocol, results and limits](docs/pilot.md) explain the independently
authored review expectations, separate input rejection from annotation holds,
and publish numerator/denominator counts. Wrong/missing labels still cause two
of five intended reviews to be missed by the full gate; compatible text with
wrong labels also causes an unnecessary hold. These failures are retained.
No LLM, remote provider, semantic-truth measurement or statistical generalization
is involved. All results are preexisting November 5 pilot preparation.

## Optional real hosted Otari

The real adapter follows the [official current API reference](https://github.com/mozilla-ai/otari/blob/3cca8d6759e3b91c1f6817a8d53d4e3a80e0866e/docs/api-reference.md)
and [client configuration](https://github.com/mozilla-ai/otari/blob/3cca8d6759e3b91c1f6817a8d53d4e3a80e0866e/docs/use-with-opencode.md).
Configure an authorized account and model privately:

```sh
export SOURCE_TRAIL_MODE=otari
export OTARI_API_KEY=your-private-inference-key
export OTARI_MODEL=your-account-model-selector
export OTARI_REGION=us  # or eu, matching the account
python3 -m source_trail --db var/hosted.sqlite3 suggest examples/notes.json --goal 'Find the opening and visitor requirements' --key hosted-workshop-001
```

This sends the goal, full bounded documents and anchors to **hosted Otari**, and
may consume account credits. Review source permissions and privacy first. It
uses `POST https://api.otari.ai/api/v1/chat/completions`, or
`https://eu.api.otari.ai/api/v1/chat/completions`, with Bearer authentication.
The `/api` prefix is required; older search snippets omitting it are stale.
Region/endpoint hosts are allowlisted; redirects are refused, including region
misdirection. No arbitrary URL endpoint, web-search/fetch, MCP or code-execution
tool is exposed or declared. JSON output support/model availability still depend
on the actual account/provider; an unsupported model/request fails closed.

The model returns only `anchor_ids`. The same local gates then produce quotes
from the original packet, independently checking every annotated disagreement.
No real key or model was used during development; only an injected HTTP contract
transport was tested. Successful contract tests are not remote inference evidence.

## Audit and retry boundary

An idempotency key binds packet, goal and configured provider/model/region.
SQLite reserves it **before** calling a hosted provider. Parallel/repeated calls
cannot issue a second request under that key. Successful replay returns the saved
report, even after restarting. A pending, failed or rejected attempt is not
automatically retried: the provider may already have charged. Inspect Otari usage
and the local audit before deliberately making a new request with a new key.

Audit rows store input hashes/counts, provider configuration, outcome and, when
returned on success, the sanitized `Otari-Request-ID`, six-decimal `cost_usd` and
outbound request hash. Missing cost is **unknown**, not zero. Audit data omits raw
goals, documents, provider exceptions and API keys. The SQLite result contains
accepted quotes/review candidates, so the **ledger is private content**, not a
redacted file safe to publish. Its file mode is 0600. HTTP errors are sanitized.

## Local JSON API

Set a private `SOURCE_TRAIL_API_TOKEN` of 32–256 visible ASCII characters, then:

```sh
python3 -m source_trail --db var/requests.sqlite3 serve --port 8796
```

The server binds only `127.0.0.1`. Authenticate private routes with
`Authorization: Bearer <token>`:

| Route | Input / behavior |
|---|---|
| `GET /health` | Public mode metadata only |
| `POST /v1/review` | `{ "packet": ..., "selection": {"anchor_ids": [...]}}`; pure local gates, no provider |
| `POST /v1/suggest` | `{ "packet": ..., "goal": "..." }` and `Idempotency-Key`; configured provider only |
| `GET /v1/audit` | Private request outcomes and hashes |

No request may change the configured mode, model, key, region or endpoint.
This is a local development service, not a production authentication/TLS gateway.

## Verify and package

```sh
python3 scripts/verify.py
python3 scripts/package.py
python3 -m source_trail verify output/REPORT_SHA256.json
```

21 tests cover exact/Unicode spans, invalid imports, hidden opposing annotations,
unsupported model claims, content hashes, the official Otari request contract,
configuration/redirect/tool rejection, error sanitization, concurrent/persistent
idempotency, no automatic paid retry, local HTTP and CLI holds, pilot failure
classification/denominators and byte-identical reproduction. The source ZIP in
`dist/` excludes runtime ledgers, outputs, secrets and virtual environments.
No workflow/remote CI or successful hosted-inference claim is included.

MIT license; [comparison sources and licenses](docs/landscape.md). The
[Apart competition record](docs/competition.md) gives the November 16 19:59
Beijing deadline, preexisting-work disclosure and required official-template PDF,
abstract and limitations/dual-use appendix. A repository alone is not an entry.
No account registration, signup, terms acceptance or submission was performed.
