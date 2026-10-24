# Review reply admission and local recovery

An HTTP response can complete and settle its charge while its structured review content fails admission. A failed review batch never becomes an accepted contribution merely because the provider completed it. The raw provider artifact, original call, usage and financial reservation remain saved.

The current Council uses `council-admission/1` for conservative extraction normalization:

- The observed descriptive reasoning labels `calculation` and `quantitative` become `unclear`, rather than being guessed into deduction or empirical evidence. Original labels and exact field paths remain in an admission record linked to the reply.
- An explicit null audit tolerance becomes the string `unknown`. It does not become zero or an inferred numerical tolerance. A numerical check without the required typed inputs remains unknown.
- Duplicate mechanisms, identical claim memberships, or purportedly distinct families splitting equivalent grouped claims are retained as disputed candidates. Both sides are excluded from distinct-approach counts; valid source-bound assertions still proceed. A later current recheck must give a consistent grouping before the candidates can count as distinct. An optimistic boolean cannot override a duplicate grouping.

No source IDs, author coverage, claim text, dependency references, revisions, evidence links or required objections are guessed or omitted. Those validations and batch rollback remain strict. Unsupported structures still stop admission. The error now names the failing phase and field/reference/coverage check, with raw input excluded from schema diagnostics. No extra inference is performed to repair formatting.

The original raw content is never overwritten. Admission records retain the raw-content hash, normalized-output hash, changed paths, original values, replacements and reasons. Public extraction notes disclose uncertainty and disputed groupings; later review prompts retain those notes. Historical publications keep their saved snapshots and policy decisions.

## Recovering a completed review reply

Trusted local operators can use `review_reply_restore.restore_completed_review` to admit an already completed extraction, scrutiny, repair, recheck or synthesis reply under the current transport policy. This is a local operation, not a model tool or automatic paid retry. It requires a verified complete matching provider artifact and request hash, the latest attempt for the current exact turn/model, unchanged user/source/review context, an idle Council and its already settled original reservation. Stale, partial, unknown-outcome or superseded replies are refused.

Successful restoration appends the admitted public reply in the same chat, writes an audit record and leaves the chat **paused** at the next review stage; a restored final synthesis completes its chat. It does not enqueue work, modify calls or charges, release unknown reservations, renew billing authorization or change the $24 cap. Repeated restoration is idempotent. The director chooses when to Resume the next ordinary review step.

The October 22 saved Nemotron Super extraction was validated on a disposable database copy before local recovery: six source-bound claims, three preserved families, two disputed families and three audited formatting normalizations. Tests cover full workflow continuation, exact uncertainty preservation, strict rollback for bad sources/coverage/schema, duplicate-family recheck behavior, idempotent local receipt recovery, unchanged financial records and stale-context refusal. See the [validation record](../validation/review-admission-recovery.json).

Scrutiny accepts an optional `evidence_obligation` note as model commentary. Its exact text is retained in the finding and public reply. It cannot create evidence, human verification or publication permission. The completed GLM scrutiny reply was recovered locally with all six findings and its exact note retained; no calls, charges or existing claims were changed. See [the GLM recovery record](../validation/glm-scrutiny-recovery.json).

The current Council no longer rejects prose for exceeding editorial character targets in individual fields. Supplemental public notes are retained separately from authoritative fields, with conservative enum spelling normalization and unchanged source, author, coverage and revision checks. See [Council harness behavior](COUNCIL_HARNESS.md) for the complete policy and [the repair recovery record](../validation/harness-resilience-recovery.json) for the saved GLM repair.
