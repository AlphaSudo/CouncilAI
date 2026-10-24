# Council 1.06 implementation and acceptance checklist

Date: October 23, 2026. **Status: software implemented and validated; B08 test-order exception is recorded below.**

Design authority: [Council 1.06 plan](12_ANSWER_FIRST_COUNCIL_1.06.md). See [operations and state contracts](../docs/operations/ANSWER_FIRST_COUNCIL_106.md), [acceptance evidence map](../docs/validation/answer-first-1.06/acceptance.md), [offline demo and measured controller pilot](../docs/validation/answer-first-1.06/demo/demo-and-performance.json), and [genuine live receipts](../docs/validation/answer-first-1.06/live-completion.json). The new live council and one same-chat explanation completed after a real malformed extraction was downgraded; this was partial review, not a complete review-quality pass.

Human quality tasks are frozen and **unlabelled**. B08 has a recorded test-order exception: the expanded A01–A08 corpus was added during implementation, not entirely before dispatch changes. This cannot be claimed retroactively.

Golden rule: **ordinary harness/review problems cannot cancel a healthy model response, hide received public text, fail the conversation, require another paid format attempt, or force a new chat.** Honest incomplete review is an acceptable result. Financial, authorization, actual provider/context and storage-integrity boundaries still apply to actions and dispatch.

## WP0 — Freeze the baseline and define compatible state

Outcome: implementers know what must remain unchanged and what counts as degradation rather than a failed answer.

- [x] **B01** Snapshot representative current chats, source versions, raw receipts, model overrides, usage cards, calls, reservations and exports; record hashes without copying credentials into evidence.
- [x] **B02** Add regression fixtures for the actual failures: missing observation reasons, null ratio text, long prose, list/object family descriptions, supplemental fields and repeated JSON. Preserve original source/model attribution.
- [x] **B03** Freeze the public-answer, stage-result, review-warning, annotation-coverage and decision-brief record contracts. Define every terminal state and its scheduler consequence.
- [x] **B04** Define independent `generation_state`, `review_state` and evidence/support projections. Remove “review incomplete means chat failed” from the new execution path.
- [x] **B05** Classify failures by handling: cosmetic normalization, individual annotation quarantine, whole-sidecar degradation, provider failure, authorization/funding stop and unrecoverable storage failure. Do not rely on matching a human error string.
- [x] **B06** Freeze the new internal protocol/policy/descriptor identifiers and mixed-history dispatch. Keep the product name Council and avoid a version/mode selector.
- [x] **B07** Record the active policy: Super lead, Beam and DeepSeek; Lightning optional; 262,144 shared context; existing thinking choices; $24 aggregate existing credit; $0 additional payments.
- [ ] **B08** Write failing acceptance tests A01–A08 before changing dispatch or persistence. A schema exception injected after provider completion must expose the present interruption bug.

Evidence: baseline manifest, record-contract examples, migration decision and initial fault-test results. No provider inference is needed.

## WP1 — Make public answer delivery durable

Outcome: public text survives even when every annotation fails.

- [x] **D01** Persist the producing call/receipt and public reply before attempting review interpretation. Ensure a later review rollback cannot roll back the saved answer.
- [x] **D02** Provide bounded durable public streaming/replay with sequence IDs and original model/seat/cycle attribution. Reconnect must not duplicate text or dispatch a new request.
- [x] **D03** Preserve partial public text and its actual completion/timeout state. An empty provider result must remain empty/unavailable, not become a fabricated answer.
- [x] **D04** Keep secret redaction and source permissions on the delivery path. Handle sensitive strings spanning chunk boundaries; never persist or expose private reasoning text.
- [x] **D05** Separate raw internal review payloads from readable public debate/final messages. Simple must not show metadata JSON merely because annotation failed.
- [x] **D06** Isolate sidecar exceptions from stream cancellation and the executor's global chat-failure branch. Logging an internal review error must not change an active model's cancellation condition.
- [x] **D07** Implement crash reconciliation for the interval between answer persistence and annotation completion. Reuse a complete matching receipt locally; never replay an already billed request by accident.
- [x] **D08** Preserve explicit user Pause/Stop behavior and application shutdown recovery. Review warnings cannot simulate those controls.

Acceptance: A01, A05, A08, A09 and A18. Evidence must compare exact public content, call counts and money rows before/after faults and restart.

## WP2 — Continue through incomplete review

Outcome: review produces valid records and honest gaps; it does not become an obstacle to the next answer.

- [x] **R01** Retain the existing tolerant JSON/prose normalization and raw-value audit trail. Normalized presentation must not change substantive assertions or silently delete notes.
- [x] **R02** Add record-level savepoints/dependency validation so independent valid annotations survive a bad neighboring record. Invalid records remain available as unlinked notes with their original content.
- [x] **R03** Keep source, author, revision and evidence checks authoritative for linked data. Continuing answer delivery must never turn an unknown ID or model-granted permission into valid evidence.
- [x] **R04** Treat wholly non-JSON review output and previously unseen descriptive representations as a degraded sidecar, not a failed chat. Preserve readable public prose; keep raw structured data inspectable.
- [x] **R05** Record terminal stage results independently of chat-message presence. Successful, partial, degraded and skipped stages must each make finite progress without regenerating the same turn.
- [x] **R06** Define the fallback input packet: original question, actual public responses/source spans, existing valid annotations, missing-review coverage and material unresolved issues. Do not create fake atomic claims to fill gaps.
- [x] **R07** For each dependent stage, implement one explicit choice: use the truthful public-text variant of its planned request, or skip metadata-only work and move toward synthesis. Record the choice and actual calls.
- [x] **R08** Missing author/finding coverage remains incomplete or unresolved. Do not silently mark objections answered, discard a mandatory concern, or require perfect JSON coverage to deliver a conditional conclusion.
- [x] **R09** Add automatic local reconciliation of an unchanged, completed rejected receipt. Reuse existing request/artifact/context/settlement guards and idempotency. This must not create a paid repair request.
- [x] **R10** Prevent a formatting warning from showing an error banner, enabling retry-by-default, requiring Resume, or emitting “start a new council.”
- [x] **R11** Preserve the complete original message and charges even if a user subsequently chooses to retry a model that genuinely failed. Format recovery and paid retry are different actions.

Acceptance: A02–A07, A10 and A19. Test both partial annotation failure and complete extraction/critic/recheck failure, not only the known family-list case.

## WP3 — Make scrutiny selective and avoid premature steering

Outcome: fewer repetitive objections and stronger review of the issues that matter to the user's decision.

- [x] **I01** Build a local task frame from explicit user content and saved constraints. Keep the original question immutable; inferred assumptions remain labeled suggestions/questions.
- [x] **I02** Preserve opening independence and the frozen evidence snapshot. No peer response, reviewer note, new discovery or ranking leaks into an unfinished independent opening.
- [x] **I03** Replace defensive opening boilerplate with lightweight proposal/reasoning/assumption/failure-condition guidance. No hard word count or required checklist field can reject a response.
- [x] **I04** Preserve original claims, exact source spans and separate authors while grouping equivalent mechanisms. Related/conflicting variants stay distinguishable; repetition creates no additional evidence.
- [x] **I05** Add explainable critical/major/moderate/minor prioritization with origin and decision-impact rationale. Treat uncertainty/centrality scores as heuristics, not calibrated facts.
- [x] **I06** Select applicable auditor lenses in the existing scrutiny request: logic/calculation, constraints, resource boundaries, provenance, engineering and test validity. No six-call default fan-out.
- [x] **I07** Make the existing critic explicitly attempt falsification without promoting a competing design, demanding zero risk, or inventing a defect. “Attack did not defeat the claim” is valid.
- [x] **I08** Group duplicate objections against a shared dependency. Route consequential questions to the original author between completed turns; keep low-impact wording issues as notes.
- [x] **I09** Preserve one normal repair turn per relevant author, original/revised assertions, withdrawal and remaining uncertainty. Keep late new ideas visibly unreviewed instead of silently substituting them into an old proposal.
- [x] **I10** Refine recheck so objection resolution, evidence sufficiency, ordinary residual risk and applicability are separate. Unknown metadata cannot count as a successful check.
- [x] **I11** Add finite stopping decisions at completed-turn boundaries for repeated arguments, diminishing returns and evidence/test-dependent uncertainty. A stop decision proceeds to synthesis and leaves the chat available.
- [x] **I12** Keep optional focused exchange inside the existing call/attempt/credit plan. Domain, novelty or question length alone cannot silently authorize more agents or paid requests.

Acceptance: A11–A15 and A23. Semantic quality claims require labeled evaluation, not just successful workflow execution.

## WP4 — Deliver a natural, useful conclusion

Outcome: the user gets an answer even when some review is incomplete.

- [x] **S01** Build a decision brief from the user's actual criteria, valid review records, real public responses and available source versions. Include missing coverage and unresolved decisive issues.
- [x] **S02** Compare alternatives under common boundaries without inventing scalar utility weights, prices, measurements, penalties or unit conversions.
- [x] **S03** Ask the lead synthesizer to answer naturally in Markdown. Do not require a strict JSON envelope or a fixed nine-section template for a public final answer.
- [x] **S04** Permit conditional and explicitly unreviewed ideas when useful. Remove a judge whitelist that makes missing annotations censor otherwise deliverable model output.
- [x] **S05** Distinguish a preferred practical choice, strongest theoretical option, speculative alternative and ranking-reversal condition when the task needs them. Do not force all four into every answer.
- [x] **S06** For unresolved major/critical disagreements, deliver the strongest justified comparison, conditions and next useful test. Do not synthesize false certainty or withhold the entire answer.
- [x] **S07** Keep source/evidence labels accurate. Retrieved text, a model assertion, a local calculation and an executed measurement must not be collapsed into “verified.”
- [x] **S08** If the lead genuinely fails, retain the previous model responses and provide an explicitly attributed partial result using existing local rendering. Do not fabricate a successful lead response or send an unauthorized substitute request.
- [x] **S09** Never let a post-answer review annotation replace, erase or silently rewrite a completed final response. Any later assessment is a versioned annotation/update.

Acceptance: A06, A12–A16, A20 and A23. Final-answer usefulness is assessed independently of ledger completeness.

## WP5 — Preserve long conversations, tools and budget

Outcome: repeated follow-ups remain reliable and affordable without new-chat resets.

- [x] **M01** Exercise at least three explicit same-chat follow-ups with mixed successful/degraded stages. Preserve original messages, actual model identities, effective Beam override, dissent and source versions.
- [x] **M02** Keep the 20-attempt window tied to an explicit request/cycle, not lifetime chat history. Advancing locally after a warning does not reset actual usage or grant extra attempts.
- [x] **M03** Queue steering received during a response for a future turn/context revision. Do not inject new instructions into the active provider request or silently reframe the current answer.
- [x] **M04** Keep 262,144 shared context and current provider-specific thinking/output controls. Compaction retains the user objective, constraints, material objections, dissent, current revisions and source anchors.
- [x] **M05** Preserve shared-source opening barriers and deterministic research exposure. Cache reuse is measured where reported; missing telemetry is unknown.
- [x] **M06** Convert search/fetch/library/calculator unavailability into typed tool results at valid model-requested boundaries. Let the model finish with available information; do not fabricate successful retrieval or execution.
- [x] **M07** Prevent repeated identical failing searches/fetches and unbounded tool continuation. Keep the existing research allowance and actual tool-credit accounting.
- [x] **M08** Add a conservative feasible finishing reservation before optional review. Use the actual selected models, price snapshot and final-context bounds; avoid an arbitrary new per-chat spending cap.
- [x] **M09** Preserve the $24 aggregate cap, $0 additional-payment authority, pre-dispatch reservations and unknown-outcome holds across every branch. No model-granted financial authority and no automatic ambiguous retry.
- [x] **M10** Keep cumulative input/output/reasoning/cache/cost totals correct for attempted, skipped, partial, locally recovered and completed stages. Count reasoning once; distinguish holds from settled usage.
- [x] **M11** If funds or provider capacity cannot support another request, deliver saved material and the real limitation. Do not stop the delivery path or pretend a failed request succeeded.

Acceptance: A09, A16–A22. Include a restart and duplicate UI submission during one multi-turn case.

## WP6 — Present warnings without making the user operate the harness

Outcome: Simple stays calm; Explain provides complete evidence.

- [x] **U01** Render the public response while review is pending or incomplete. Avoid blank answer panels and a permanent generic “council is responding” state after actual delivery.
- [x] **U02** Show a concise relevant note such as “Some review details are unavailable” when it affects interpretation. Keep field paths, JSON, validators and stack information in Explain.
- [x] **U03** Distinguish “answer complete, review partial” from “provider returned no answer” and “waiting for authorized credit/capacity.” Do not display all three as the same red failure banner.
- [x] **U04** Remove Resume/Retry requirements for cosmetic/sidecar warnings. Keep explicit recovery controls only where there is a genuinely new request or unresolved external/action boundary.
- [x] **U05** Show actual model identity, public text, copy controls, elapsed time, usage and source inspection accurately for partial and locally recovered results.
- [x] **U06** Keep Simple/Explain a view switch with zero provider/tool calls. Preserve draft text, scrolling, selection and the same conversation when switching.
- [x] **U07** Verify compact widths, one main page scroll area, dark backgrounds, capped composer height, readable math and keyboard access. Do not reintroduce a version selector or technical clutter.
- [x] **U08** Add accessible warning/detail disclosures and meaningful progress states. A live reasoning indicator must not imply public answer text already exists.

Acceptance: A01–A03, A06, A16, A20 and A24 with desktop and narrow-viewport browser evidence.

## WP7 — Migration, proof and release

Outcome: a reviewable release with truthful evidence and recoverable historical chats.

- [x] **V01** Adopt 1.06 only for a new explicit cycle or safe idle transition. Never modify an in-flight request or reinterpret an old published answer's policy silently.
- [x] **V02** Verify historical v1/v2/v3 exports and mixed-history transcripts reproduce original provenance, decisions, hashes and costs. New warnings cannot retroactively certify old claims.
- [x] **V03** Back up the data directory/SQLite state before migration. Restore a copy and prove historical messages/calls/reservations are preserved.
- [x] **V04** Pass A01–A24 and relevant inherited suites; build the production UI and test a clean credential-free demo setup.
- [x] **V05** Capture measured controller overhead, time to public text, complete-answer latency, review token share, attempts and warning/stop rates on a fixed corpus. Report provider latency separately.
- [x] **V06** Freeze held-out human quality tasks and scoring for material errors, false rejection, attribution, novelty, decision usefulness and synthesis fidelity. Keep failures and unlabelled cases in denominators.
- [x] **V07** Prepare an offline/replayable demo of a real user question plus an honestly labeled injected formatting failure and a same-chat follow-up. Copy/export must match the displayed public answer.
- [x] **V08** When live testing is performed within existing authorization, record genuine exact-model/provider receipts, source use, actual/estimated/unknown cost and any failures. Do not equate a synthetic fixture with a real completed council.
- [x] **V09** Verify the hackathon's current submission and technology-use requirements before submission. Record actual Token Factory/NVIDIA lead use; do not claim unmeasured GPU/kernel/hardware results.
- [x] **V10** Write release notes stating delivered behavior, disabled/deferred work and remaining independent quality/latency limits. Link evidence for each acceptance claim.

## Acceptance scenario register

| ID | Scenario | Required observable result |
| --- | --- | --- |
| **A01** | Healthy public stream plus a review exception | Public text continues and is saved byte-for-byte after redaction; the review exception cannot cancel the stream or fail the chat. |
| **A02** | Known cosmetic variations, including family lists/objects | Normal completion, original structured values retained, no paid format repair, Resume step or new-chat instruction. |
| **A03** | Entire extraction reply is prose or an unknown schema | Stage becomes degraded once; original reply remains inspectable; a truthful fallback route reaches synthesis without inventing a complete ledger. |
| **A04** | Mixed valid and invalid linked annotations | Valid independent annotations remain; invalid IDs/revisions are quarantined; no false source/evidence authority; answer stays visible. |
| **A05** | Crash after public receipt commit, before annotations | Restart reconciles the same receipt locally exactly once, without regenerating the answer or changing financial rows. |
| **A06** | Synthesis is natural Markdown or has unusable metadata | Readable final answer is delivered; review qualifications are accurate; no strict JSON publication rejection. |
| **A07** | Repair/recheck omits a finding or references a stale claim | Public response is retained, omitted issues remain open, subsequent synthesis is qualified; no fabricated closure or whole-chat failure. |
| **A08** | Sidecar raises an unexpected programming exception | The answer path survives; a bounded diagnostic is saved; no exception-driven retry loop or silent corruption. |
| **A09** | User Pause/Stop and concurrent steering | Pause blocks new dispatch while preserving current output; Stop follows explicit intent; future steering does not alter active context. |
| **A10** | Repeated identical payload, different payloads and bad references | Identical metadata is deduplicated. Ambiguous/invalid metadata is unreviewed rather than guessed. Public answer progression remains available. |
| **A11** | Independence and delayed source discovery | All openings receive the frozen common evidence revision; no peer answers/rankings leak; later sources appear only at a valid barrier. |
| **A12** | Correct unconventional proposal and a failed falsification attempt | Novelty is retained and not penalized for unfamiliarity; the critic is allowed to fail; no invented empirical support. |
| **A13** | Ordinary residual risk versus decisive defect | Ordinary risk becomes a condition/note; a genuine decisive defect changes the recommendation or comparison without blocking answer delivery. |
| **A14** | Duplicate mechanisms and majority agreement | Separate authors/source records survive; duplicate families are not padded into a requested count or treated as independent evidence. |
| **A15** | Repeated criticism with no new information | The coordinator records diminishing returns/evidence need and reaches synthesis at a turn boundary; no indefinite debate. |
| **A16** | Lead provider returns partial/no public text | Other answers/partials/receipts remain visible; a clearly attributed partial result is available; no fabricated lead answer or automatic ambiguous retry. |
| **A17** | Search/fetch quota, timeout and unsupported calculation | Typed unavailable/unknown tool result, bounded continuation, no fake citation/check and no whole-chat failure due to an optional tool. |
| **A18** | Redaction across stream chunks and public/private fields | Configured secrets never reach persisted/exported public output; private reasoning text is neither stored nor displayed. |
| **A19** | Local recovery applied twice | Same result/message, zero new inference, unchanged prior messages/calls/reservations; reconciliation schedules at most one authorized next step. |
| **A20** | Three explicit follow-ups in one chat | History, selected model override, sources, outstanding issues and cumulative usage remain intact; attempt windows do not become a lifetime chat cap. |
| **A21** | Low remaining credit and unknown prior outcome | Global $24 cap and holds remain enforced; finishing work is not starved by optional review; saved responses are still delivered. |
| **A22** | Context pressure near the configured window | Actual provider/context bounds hold; compaction keeps material obligations/source anchors, discloses omissions and does not silently rewrite the question. |
| **A23** | Hidden cost, false citation, arithmetic/unit error, causal overclaim | Available checks affect claim support/ranking honestly; unsupported checks remain unknown; the final result addresses the user rather than returning only an audit log. |
| **A24** | Simple/Explain, copy/export, restart and narrow viewport | Same answer and usage in both views, no extra API calls from inspection, calm warnings, readable math and complete replayable output. |

## Release sign-off

- [x] Every ordinary review-fault scenario delivers available public answers without a forced new chat, a formatting Resume requirement or a paid format-repair call.
- [x] Source, revision, evidence-origin, authorization and spending invariants remain intact even when review degrades completely.
- [x] The default execution adds no framing, judge or specialist-auditor model calls beyond the existing plan.
- [x] The deployed product demonstrates a useful answer and a same-chat follow-up; evidence clearly separates real provider results, synthetic fault tests and human quality labels.
- [x] The release record distinguishes implemented software from unproved model quality and provider latency, with no claim of guaranteed hackathon success.


Final evidence: **654 backend checks passed** in the credential-free clean environment; **51 unique browser cases passed** across the full run and the targeted cleanup rerun. [Machine-readable release report](../docs/validation/answer-first-1.06/release.json). B08 remains unchecked because its chronological condition cannot be claimed retroactively. Human answer-quality labels remain unperformed; the corpus/scoring were frozen as V06 requires.
