# Context compaction and the context ring

## Operating behavior

Token Factory councils retain the 262,144-token shared input/output context window. Automatic lossless compaction prepares large review requests at about 80% input usage, or earlier if the response allowance and a 16,384-token headroom buffer require it. This threshold starts an optimization; it is not a smaller context limit. A request without useful repetition can still use the full configured window.

Click the **Context** ring beside the composer to inspect the latest prepared request. The ring uses the local published model tokenizer's input estimate, including framing, plus reported completion tokens when available. Completion includes reasoning and is added once. The response reservation is shown separately; it is not added as if it were generated output. Provider-reported input is displayed separately in Explain mode. Missing output usage remains unknown.

This is per-request telemetry, not the accumulated conversation bill, live draft measurement or a prediction of the next stage's size. Each model can tokenize the same text differently; Explain mode lists its most recent measurement. An unmeasured chat has a neutral ring instead of a false zero.

**Compact context** enables compaction preparation for subsequent review requests, including smaller ones. It takes effect at a request boundary. It does not interrupt a running response, enqueue another turn, retry a request or spend a summarization call. **Restore automatic compaction** in Explain mode returns to threshold-based behavior. The latest ring measurement changes when a new request is prepared, not merely when the preference changes.

## What is compacted

The implementation stores recurring exact strings once in a text dictionary. References can replace a complete repeated field or exact text embedded in a longer field. The model receives a decoding instruction and the dictionary alongside the ordinary stage payload. Its required response format stays unchanged.

Before adoption, the application reconstructs the complete stage payload and compares it with the original. Every source passage, qualifier, claim, objection, revision, identity and coverage relationship must match. The response schema and current stage instructions remain inline. The source packet prefix, native tool schemas, assistant/tool call pairs, signatures and generation controls are not rewritten.

The full assembled request, including decoding overhead, is counted with the selected model's tokenizer. Packing is adopted only when it saves at least 256 input tokens and reduces serialized request bytes. Small or unique requests remain unchanged when packing would cost more. Candidate work is bounded to 256 strings. Collisions with reserved reference-field names cause packing to be skipped.

Raw independent openings keep their requested baseline format. Saved output-recovery requests keep their original public context and tool continuation. Structured review admission, source validation, evidence policy and publication checks run as before.

## Persistence and money

Each dispatched compacted request has a `context_compaction` receipt linked to its call. It records original and packed payload hashes, before/after token estimates and byte sizes, the trigger, dictionary size and reconstruction result. The provider artifact contains the encoded request. `context_compaction.expand` reconstructs its stage payload offline; a research-wrapped request uses the JSON after `Current stage:`. Checkpoints are included in existing research/review exports.

Compaction runs before context fitting and credit reservation. Existing conservative financial bounds apply to the complete actual outgoing request at the existing rates. Token savings do not guarantee a provider cache hit or a particular invoice reduction. Provider-reported cache usage and prices remain authoritative for cost reporting.

The $24 existing-credit cap, unknown-charge reservations, settled historical calls, saved messages and original sources are unchanged. This feature makes no automatic paid summary, format-repair, fallback or retry call.

## Limits

This is reversible lossless compaction, not an LLM-generated summary. It cannot make unique required material arbitrarily small or extend the model's physical context window. If required input still exceeds that window after preparation, admission stops before sending or charging another request. No required objection is discarded to force it to fit.

The first deployment supports measured Token Factory requests across all four configured models. Other provider interfaces continue to use their existing context behavior. Hosted models' ability to use the new reference format has synthetic transport coverage; no paid live compaction experiment was performed during implementation.

## Open-source research and adaptation

[OpenCode's compaction documentation](https://dev.opencode.ai/v2/docs/compaction/) describes a summary checkpoint with retained recent context, configurable reserve space and manual requests applied at safe boundaries. It explicitly identifies summarization as lossy and notes that compaction cannot fix a request dominated by fixed instructions.

[Pi's implementation](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/src/core/compaction/compaction.ts) separates preparation from session persistence, reserves capacity, retains recent material and avoids separating tool results from their calls. Its default reserve is 16,384 tokens and its recent-context setting is 20,000 tokens.

The Council adapts the capacity reserve, safe boundary, preserved tool grouping, recoverable checkpoint and measured usage ideas. It uses its existing structured review state and exact text references instead of adding a paid lossy summarizer to the critical scientific review path. The implementation is written for this repository; no external agent dependency or code copy was introduced.

## Verification

- Exact reconstruction of prose, embedded passages, sources, schemas and controls.
- Net tokenizer savings across all four configured models.
- Automatic threshold, manual preparation, no-gain and reserved-name collision paths.
- Preservation of raw openings, saved recovery requests and native tool pairs.
- Idempotent manual requests without calls, jobs, ledger or transcript changes.
- Dispatch receipt and reservation accounting for the actual compacted request.
- Missing usage remains unknown and viewing telemetry is read-only.
- Simple/Explain browser behavior, keyboard dismissal and mobile popover visibility.

See `tests/test_context_compaction.py`, `apps/web/e2e/context-compaction.spec.ts` and the [validation record](../validation/context-compaction.json). The three inspected saved real requests did not justify packing after overhead; they were left untouched, as recorded in [the offline previews](../validation/context-compaction-saved-previews.json).
