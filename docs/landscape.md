# Existing citation/annotation work and this implementation

Checked 2026-11-05 against the primary README/license files. Exact quotes and
source references are established techniques; no unique-invention claim is made.

| Primary source / version | License | Existing capability / comparison |
|---|---|---|
| [mozilla-ai/otari](https://github.com/mozilla-ai/otari/tree/3cca8d6759e3b91c1f6817a8d53d4e3a80e0866e), commit `3cca8d6759e3b91c1f6817a8d53d4e3a80e0866e` | [Apache-2.0](https://github.com/mozilla-ai/otari/blob/3cca8d6759e3b91c1f6817a8d53d4e3a80e0866e/LICENSE) | Gateway authentication, models, budgets, usage/traces and optional tools already exist. Source Trail does not reimplement that infrastructure; it calls the documented hosted Chat Completions protocol without tool access and adds local output/quote gates. No Otari code/SDK is copied or bundled. |
| [Hypothesis h](https://github.com/hypothesis/h/tree/18e30d6b1feda29f291140e29dbdedd33c45fb47), commit `18e30d6b1feda29f291140e29dbdedd33c45fb47` | [BSD-2-Clause](https://github.com/hypothesis/h/blob/18e30d6b1feda29f291140e29dbdedd33c45fb47/LICENSE) | Mature web annotation app/API; its separate browser client attaches annotations to documents. We lack browser/PDF annotation, collaborative accounts, robust relocation and the full ecosystem. Our narrow workflow is private bounded text packets, exact quotes and explicit user-labeled disagreements checked before notes are accepted. Design comparison only; no source/assets copied. |

[W3C Web Annotation's Text Position Selector](https://www.w3.org/TR/annotation-model/#text-position-selector)
also establishes start/end text selectors. It is a design reference, not copied
implementation, and this custom packet format does not claim W3C interoperability.
The full source hashes/pins are in [source-versions.json](source-versions.json).

The implementation is independently authored using Python's standard library.
It is not a fork. The substantive user value is limiting model authority to
selection of immutable source anchors, binding every released quote to exact
Unicode offsets and complete-source hashes, exposing opposing user annotations
even if a selection leaves them out, and retaining a private request ledger that
will not automatically repeat a possibly billed request.

This is deliberately less capable than semantic research assistants: no
free-form synthesis, source discovery, fact checking, contradiction inference,
fuzzy anchors, URL retrieval, public collaboration or automated publication.
User position labels can be incomplete/wrong; exact excerpts can lack context.
The restrictions are explicit rather than presented as solved reasoning.

21 meaningful tests and the verify script exercise input/span bounds, claims
withheld under disagreement, unsupported replies, exact hosted protocol/region
contract, no tools/redirects, no key/exception disclosure, persistent/concurrent
idempotency, API and CLI behavior, independent-oracle pilot failure counts and
byte-identical experiment reproduction. All provider tests use injected
transports; actual hosted-model success, registration and submission remain
unevidenced. The [16-case pilot](pilot.md) is an independently implemented
ablation using original synthetic data and the existing core; no upstream
benchmark cases or evaluation code were copied. Everything is explicitly
preexisting November 5 preparation for [Apart](competition.md), not future
sprint-period research. Its full-gate misses and false holds are public.
