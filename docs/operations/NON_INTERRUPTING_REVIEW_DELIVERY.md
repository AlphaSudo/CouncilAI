# Review warnings that do not stop council delivery

October 23, 2026. This is an immediate continuation bridge for the current `reviewed_v3` execution path. It delivers part of the planned 1.06 behavior; it does not claim the full 1.06 architecture or checklist is implemented.

The normal execution path now calls `review_delivery.admit_deliverable`. Strict `review.admit` still protects the linked claim ledger and remains available for validation/replay tests. Protocol integrity is checked before interpreting a new reply. Known annotation failures and unexpected sidecar exceptions roll back their admission savepoint, preserve the actual public model output/receipt, and create an explicit incomplete-review record instead of a failed conversation.

An extraction or scrutiny that cannot be admitted skips dependent typed-only steps and moves toward synthesis. A bad author response or recheck remains visible as unreviewed notes. There is no paid format-repair request, silent closure, invented source, model substitution or requirement for a new chat. Remaining review metadata cannot create a successful tool check or author revision. Storage failures and financial/authorization boundaries are still enforced.

The rechecker can no longer stop a current council by claiming an author correction that has no saved revision. Such a closure becomes unresolved with `no_effective_change`, preserving the original reviewer statement and the unchanged author record. An assessor's attempt to withdraw another author's active claim is handled conservatively in the same way. Missing, repeated or stale family assessments are unlinked/incomplete rather than discarding valid finding assessments.

Incomplete review disables automatic focused format-repair exchanges. The lead synthesis receives the actual public messages, valid claims/findings, unresolved decisions and a truthful incomplete-review notice, and is requested to answer in ordinary English Markdown. A public final reply is retained even when structured final review cannot be linked. It is labeled partial/unverified where appropriate, not a successful full review. New explicit cycles clear the active fallback state while preserving prior messages and costs.

`review_reply_restore` uses the same delivery boundary for unchanged complete receipts. Recovery remains idempotent, checks context/request/artifact/model/settlement identity, does not dispatch inference and does not alter previous calls or reservations. A subsequent final synthesis is a normal authorized request, distinct from recovering or retrying the recheck.

Relevant tests: `tests/test_noninterrupting_review_delivery.py` injects faults at all five structured stages, an unexpected sidecar exception, unsupported closure plus absent family checks, multi-turn continuation, local receipt recovery and a protected financial error. Genuine provider failure/latency is not certified by mocked HTTP cases.

Validation completed with 183 regression checks and an 11-check final targeted run: 184 distinct backend checks passed. Existing legitimate focused exchanges still work; a formatting warning does not turn them into paid format-repair loops. Natural Markdown synthesis retains surrounding prose and embedded JSON examples.

The real cycle-two recheck `call_7bdd6783dfad4a47` in `chat_45c739b53a0a42b8` was recovered from its completed receipt without inference. All nine assessments were retained; three objections remain unresolved. Prior calls, public messages and all financial reservations were compared against the backup and remained unchanged. The next stage was synthesis, with no focused format-repair request.

The already-authorized remaining synthesis then completed through the restarted application in one actual Super request (`call_6b7bc8fb44f54f79`), with HTTP 200 and finish reason `stop`. First public text arrived after 4.14 seconds and the request completed in 8.66 seconds, producing 7,740 public characters. Recorded cost estimate was $0.014353 under the unchanged $24 aggregate cap. This was the pending final answer, not a recheck retry. The final message is explicitly partial because review remains incomplete. This one observed provider success does not certify scientific correctness or future latency.

Evidence: `docs/validation/noninterrupting-review-regression.xml`, `docs/validation/noninterrupting-review-final.xml`, `docs/validation/noninterrupting-recheck-live-recovery.json` and `docs/validation/noninterrupting-recheck-live-completion.json`.
