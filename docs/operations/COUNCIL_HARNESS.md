# Current Council harness behavior

## Prose guidance and structural validation

The current Council accepts complete prose in extraction, scrutiny, author repair, recheck, synthesis and targeted follow-up scoping. Editorial maxima such as a 240-character objection are no longer admission rules. Names, mechanisms, explanations, uncertainty, tests and answer blocks keep their text intact. Historical DTOs retain their original validation rules for legacy workflows.

Source IDs, author identity, current claim revisions, required coverage, dependencies, evidence relationships, action enums and bounded list cardinalities remain validated. A reply cannot establish human verification, supply invented references or close an unrelated objection. Atomic admission still rolls back the complete batch when these checks fail. Current author repairs use their current validated DTO directly, then run the existing author and revision algorithm; they are not parsed again by a legacy DTO.

A 4 MiB UTF-8 envelope bounds each structured review **output** before JSON parsing. It neither truncates replies nor reduces the 262,144-token Token Factory input/output context window. Independent opening prose is outside this structured-reply envelope. Existing model context limits, generation allowances and financial admission remain in force.

The generation policy retains the 4,000-token reasoning instruction and 32,768 combined reasoning-and-answer review allowance. Extraction and scrutiny use a soft 3,000-token public-output target; exceeding that target alone does not invalidate a complete reply. The $24 existing-credit cap and unknown-charge reservations are unchanged. No automatic paid format-repair request or retry was added.

## Conservative transport normalization

Current responses normalize literal enum spellings only when case or surrounding whitespace gives an exact, unique match. No category, identity, reference or decision is inferred.

Unknown supplemental fields named `note`, `notes`, `rationale`, `commentary`, `summary`, `explanation`, `limitations` or `evidence_obligation` can be separated from typed objects when their values are null, text or lists of text. Their full values, exact paths and reasons are retained in admission records linked to raw and normalized hashes. Other unknown fields and wrong types remain rejected.

Supplemental notes are labeled unverified public model commentary. They do not become evidence, claim revisions, authoritative findings or human assessment. Final synthesis notes remain in the admission record outside the reviewed answer. An already defined field continues to use its declared schema and semantics; a supplemental note cannot replace a missing required field.

The earlier extraction rules also remain: unsupported descriptive reasoning labels stay `unclear`, null audit tolerances stay `unknown`, and conflicting approach families remain disputed rather than being counted as distinct.

## Optional calculations

Source-bound calculation descriptors can retain unsupported expressions, decimals or unit descriptions without rejecting unrelated claims. The calculator still enforces its own expression, node, depth, decimal, magnitude and power limits before execution. Unsupported calculations produce an `unknown` check, never an arithmetic pass or proof of the claim. Original descriptor text remains in the review and export for inspection.

## Local receipt recovery

`review_reply_restore.restore_completed_review` supports completed replies from all five review stages. It requires an identified complete Token Factory response, its integrity-checked artifact, exact original request hash, latest matching current turn, unchanged source/user context, an idle chat and its settled original reservation. Unknown outcomes and stale or superseded replies cannot use this path.

Recovery appends one locally admitted message in the same chat. It preserves original messages, call and financial rows, historical claim versions, settings and unknown reservations. It schedules no work. The chat stays paused for the remaining stages, or completes if the recovered reply is the final synthesis. A restoration ID makes repeat application idempotent.

## Verification

`tests/test_council_harness_resilience.py` exercises the complete Token Factory workflow using synthetic HTTP responses with long valid prose, supplemental fields, enum case differences and peer challenges. It requires a final answer without synthesis fallback and verifies the exported review pack. Further cases cover targeted follow-up, later-stage local recovery, unsupported calculations and the output safety envelope.

Adversarial cases still reject stale revisions, missing objection coverage, self-challenges, invented IDs and extra human-verification authority. Existing tests cover source provenance, evidence, money accounting, historical protocol compatibility and replay. These checks establish local harness behavior; they do not certify model answer quality or guarantee hosted endpoint latency.
