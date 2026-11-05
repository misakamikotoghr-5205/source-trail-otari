# Optional demonstration — not the required Apart research report

A 3–5 minute video is optional for Apart. The official-template PDF and other
required material in [competition.md](competition.md) remain necessary. Explain
that all current code and pilot results are **preexisting 2026-11-05 work**.

1. Show a fictional packet and complete context. Run local `review` and inspect
   exact Unicode offsets, quote text and full-source hashes. This is deterministic
   extraction, not model inference or semantic verification.
2. Show the disagreement packet. Selecting only the favorable bring-your-own
   quote still holds all claims because the opposite human annotation is present.
3. Run `python3 experiments/pilot.py --out output/recorded-pilot-v1`. Inspect
   `cases.json` and the three-policy n/N table. Show wrong same labels, a missing
   opposing annotation and compatible text with wrong differing labels. Explain
   both missed intended reviews and unnecessary holds without claiming truth.
4. Explain the weak comparator, whole-packet cost, synthetic sampling and author
   oracle limitations. Separate this preparation from any genuinely new work
   later performed during the sprint. Do not invent participants or results.
5. Optionally demonstrate persisted fixture replay. Actual Otari use is separate
   and unnecessary for Apart; never show a fixture as a hosted request. If a user
   later authorizes a hosted demonstration, hide secrets/private documents and
   report actual request evidence honestly.

No video, hosted call, future sprint study or official submission was created
by writing this script. Mozilla's earlier requirements are only a historical
candidate record in [mozilla-candidate.md](mozilla-candidate.md).
