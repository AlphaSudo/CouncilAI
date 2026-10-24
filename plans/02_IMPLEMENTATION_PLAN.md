# ZeroWall Detailed Implementation Plan

**Version 1.01 extension:** [Generic council scrutiny and evidence](07_IMPLEMENTATION_PLAN_1.01.md) is implemented with four direct provider seats and an opt-in reviewed protocol. [Release evidence](../docs/releases/1.01.md) distinguishes software validation from pending independent answer-quality and external acceptance gates. It does not mark the pending gates below complete.

**Updated October 18:** core releases use the local workstation and Token Factory inference. No self-managed GPU, AI Cloud account, remote worker, SSH key, inference server, or GPU notebook is a prerequisite. A [free-GPU research extension](optional/04_MEMORY_WALL_GPU_PROTOCOL.md) is optional after the core works.

The plan covers versions **0.1 through 1.00**, with an estimated **72-92 focused engineering hours** plus contingency. Checkboxes now distinguish implemented/local validation from pending live/external acceptance; see [implementation evidence](../docs/IMPLEMENTATION_STATUS.md). Requirements refer to [the traceability register](03_REQUIREMENTS_AND_RELEASE_GATES.md); numerical rules are in [the core protocol](04_RESEARCH_PROTOCOL.md).

**Free live integration evidence:** an isolated OpenRouter run now demonstrates four real private commitments, atomic reveal, four valid cross-reviews and a numerical tool, with $0 reported for all eight calls. This extends software validation; Token Factory billing authorization, target-provider acceptance, scientific quality/performance and external release gates remain pending. [Recorded findings and failed attempts](../docs/validation/openrouter-live-check.md).

The interface supports this provider directly with immutable selection, a $0 allowance, separate spending records, attempt limits and labeled API evidence. A second real eight-call run completed the research UI workflow and left an inconclusive draft for the human director. The exported calculation and decision gates reproduce offline. Latest validation passes 108 backend tests and six browser tests. Free chat now has durable bounded retries, actual quota checks and disclosed continuation with at least two available models; see [reliability findings](../docs/validation/free-reliability-findings.md). Pending research/external checkboxes retain their original scope.

## Council chat correction

The original workbench did not put the requested group conversation on the main screen. The following correction makes it the default entry point; [usage instructions](../docs/COUNCIL_CHAT.md) describe the visible sequence.

- [x] Put the prompt composer and saved conversations on `/`; preserve the research tools under `/?workspace=research`.
- [x] Require at least two distinct selected model IDs and show actual identities on each reply.
- [x] Give each participant the same question without peer replies during its opening answer.
- [x] Assemble the shared reference baseline from the saved opening answers.
- [x] Run ordered discussion turns with preceding peer context and visible challenges/revisions.
- [x] Preserve director interventions and apply them to subsequent turns.
- [x] Complete the selected discussion schedule unless the director pauses, stops or requests synthesis early; model readiness alone cannot skip rounds.
- [x] Produce an attributed final synthesis with unresolved disagreement, human acceptance and transcript download.
- [x] Validate isolation, sequencing, recovery and request limits in backend checks, and the visible workflow on desktop/mobile in browser checks.
- [ ] Independently assess answer quality; a completed conversation does not establish a correct research result.

## 1. Working rules for each release

- [x] Explain the problem, proposed implementation, files to change, and acceptance gate before coding.
- [x] Read the approved mission, budget, and prior decision revisions before dependent work.
- [x] Preserve source notes; keep generated evidence and credentials out of tracked application source.
- [x] Default to labeled fixtures/offline development until billing/key and budget prerequisites pass.
- [x] Run meaningful checks around authority, context isolation, cost reservation, numerical logic, and recovery.
- [x] Demonstrate actual behavior and attach evidence before marking a requirement complete.
- [x] Record remaining uncertainty and the next dependency in `docs/releases/<version>.md`.
- [x] Never infer completed work from a target date or use optional hardware access to block a core gate.

A release record contains the version, date, implemented IDs, demonstration, validation commands, evidence paths, known limitations, and next dependency.

## 2. Version 0.1 Freeze mission and API feasibility

**Target:** Oct 18. **Effort:** 4-6 hours.  
**Dependencies:** source plans; Token Factory project and key readiness; verified credit/overage behavior.  
**Requirements:** Z01-Z02, Z04, Z14-Z18, Z22, O02, H09.  
**Outcome:** a bounded hosted-inference mission and a safe minimal real-call path; no infrastructure provisioning.

### Work checklist

- [x] Record the user's decision in `docs/decisions/001-local-token-factory-scope.md`: core inference is hosted; free hardware experiments are optional.
- [x] Record the existing default project and GitHub username without treating account IDs as API credentials.
- [ ] Verify the $25 credit source/expiry and account overage settings; do not promise automatic account-wide stop at zero.
- [x] Record $25 aggregate existing-credit authorization, $0 new personal payments, and an operational stop below $25.
- [x] Prepare `.env.example` with placeholders and ignore local secret files before storing a real key.
- [x] Define a manual/single-process reservation record for the initial probe; unresolved request charges remain reserved.
- [ ] Load the [director's ordered allowlist](06_MODEL_SELECTION.md), verify exact account-visible IDs and current prices, preserve priority, and leave optional DeepSeek disabled.
- [ ] Freeze a tiny probe plan with maximum input/output, call count, maximum possible cost, and no unreserved automatic retries.
- [ ] Run a minimal real NVIDIA response only after these checks; preserve sanitized request/response, usage, latency, and cost metadata.
- [ ] Verify optional structured-output and streaming capabilities instead of assuming every model supports them.
- [x] Create the first mission: evaluate research-output cost/latency and evidence quality under declared context/routing treatments.
- [x] Create canonical task/source packets and expected factual/numerical checks, separated from model-visible instructions.
- [x] Define baseline, A-only, B-only, and A+B request strategies; keep hardware controls out of their schema.
- [ ] Freeze the initial operating envelope, task rubric, small pilot size, budget allocation, and stop rules.
- [x] Reserve confirmation task IDs before tuning a candidate; label pilot findings appropriately.
- [x] Record memory-wall statements as hypotheses, calculated bounds, or attributed external evidence until optional measurements exist.

### Expected artifacts

```text
docs/decisions/001-local-token-factory-scope.md
benchmark/model_manifest.json
benchmark/tasks/{exploration,confirmation}/manifest.json
benchmark/configs/{baseline,a,b,ab}.yaml
benchmark/protocols/hosted_research_v1.yaml
artifacts/feasibility/<run-id>/{request,response,usage,manifest}.json
```

### Exit gate

- [ ] The mission and request treatments are precise, measurable, and inside the authorized budget.
- [ ] One real NVIDIA call on Token Factory has valid provenance and bounded accounting.
- [x] Missing billing/key prerequisites keep live execution blocked, while offline coding may continue.
- [x] No GPU allocation, cloud project, model download, or paid infrastructure is required to pass.

## 3. Version 0.2 Build local persistence and budget enforcement

**Target:** Oct 19. **Effort:** 8-10 hours.  
**Dependencies:** 0.1 contracts and verified live-call prerequisites.  
**Requirements:** Z01, Z04, Z08, Z17, Z22, O01-O03, H01.  
**Outcome:** a persistent local mission, robust provider adapter, durable spend control, and a minimal browser workspace.

### Backend and budget

- [x] Create a locked Python project, FastAPI startup, validated settings, health/readiness, structured logs, and correlation IDs.
- [x] Create SQLite migrations for missions/revisions, steps/dependencies, rounds/submissions, concerns, hypotheses, plans, runs/attempts, artifacts, decisions, model calls, reservations, and audit events.
- [x] Commit each state change and audit event in one transaction; reject stale revisions.
- [x] Validate the step graph as acyclic and ensure prerequisite IDs exist.
- [x] Implement draft/read/edit/freeze mission APIs and director authentication for modifying actions.
- [x] Persist aggregate settled, reserved, and ambiguously charged usage across restarts.
- [x] Reserve maximum estimated input/output cost before dispatch, including provider-specific billed token categories and retries.
- [x] Fail closed if prices, request bounds, or remaining authorized credit are unknown.
- [x] Prevent parallel calls from reserving the same remaining balance; test concurrent boundary requests.
- [x] Stop new dispatch at the operational cutoff and expose the reserved reconciliation buffer.
- [x] Add a local job queue with one active executor and restart-safe attempt ownership.
- [x] Ensure cancelled or timed-out network requests do not release ambiguous charges automatically.

### Provider adapter and visible shell

- [x] Implement the configured Token Factory base URL and exact ordered allowlist, sanitized metadata, timeout, cancellation, and bounded rate-limit backoff; reject unlisted or disabled models before dispatch.
- [x] Validate response schemas; keep automatic repairs disabled and use an explicit newly reserved missing-seat continuation while preserving invalid raw output. See implementation decision 002.
- [x] Disable hidden SDK retry spend or route every attempt through the reservation layer.
- [x] Record model identity, prompt/context hash, timestamps, usage source, estimated versus actual cost, and attempt status.
- [x] Define shared JSON Schemas and frontend types from a consistent source.
- [x] Scaffold React/TypeScript/Vite with mission list, draft form, details, budget status, and step navigation.
- [x] Implement durable server-sent events with sequence-based reconnect and duplicate suppression.
- [x] Add `scripts/doctor.py` that checks configuration without printing secret values.

### Exit gate

- [x] Mission, events, and budget reservations survive restart.
- [x] Concurrent/stale mutations cannot overwrite constraints or oversubscribe the budget.
- [ ] A real model call is traceable without secret leakage.
- [ ] The browser reconnects consistently and the local app runs without cloud infrastructure.

## 4. Version 0.3 Implement private Commit-Reveal

**Target:** Oct 20. **Effort:** 7-9 hours.  
**Dependencies:** 0.2 model calls, revisions, budget, and events.  
**Requirements:** Z02-Z04, Z08, Z22, O01.  
**Outcome:** four independent research submissions reveal together from one immutable context.

### Work checklist

- [x] Build immutable context snapshots from mission, step deliverable, approved dependency decisions, concerns, and source hashes.
- [x] Preserve hard constraints and blocking concerns when packing context; record any summarization/omission policy.
- [x] Create role instructions for Hardware/Physics, Driver/Runtime, Inference Engine, and Model/Algorithms.
- [x] Require mechanism, prediction, test/control, affected layers, kill criterion, and uncertainty in each submission.
- [x] Store actual model IDs separately from logical seat IDs; disclose reused models and fallbacks.
- [x] Reserve the full bounded initial round before scheduling its calls, or show that only individual authorized attempts can dispatch safely.
- [x] Launch separate current-round calls with no peer content or peer-derived summaries.
- [x] Validate and persist private submissions with context, prompt, model, schema, and content hashes.
- [x] Limit pre-reveal endpoints/events to status, model identity, elapsed time, and sanitized errors.
- [x] Implement an atomic barrier requiring four valid current-context submissions and no stale concern revision.
- [x] Publish one complete reveal event; make duplicate requests idempotent.
- [x] Preserve valid seats across failure/restart; retry only failed seats with separately reserved costs.
- [x] Start a clearly identified new round if the roster/model/context changes materially.
- [x] Build waiting/revealed UI states and keep self-reported confidence separate from measured uncertainty.

### Exit gate

- [x] Prompt/API inspection finds no early peer-answer leak.
- [x] A failed or missing seat blocks reveal without losing valid submissions.
- [x] Restart after the third submission completes the same round without duplicate paid calls.
- [ ] A real four-seat round reveals useful falsifiable proposals and honest model identities.

## 5. Version 0.4 Add cross-review and director governance

**Target:** Oct 21. **Effort:** 8-10 hours.  
**Dependencies:** 0.3 revealed submissions and current-context tracking.  
**Requirements:** Z05-Z08, Z20, O01-O02.  
**Outcome:** the council handles challenges and human concerns without forced unanimity.

### Work checklist

- [x] Require review responses to cite challenged hypothesis IDs, controls, confounders, cross-layer costs, evidence needed, and recommendation changes.
- [x] Implement human concerns with affected objects, blocking policy, severity, source, and required response.
- [x] Require every active researcher to respond to the current blocking concern set.
- [x] Increment concern revisions and invalidate affected decision drafts; preserve in-flight results and their charges.
- [x] Generate an inspectable disagreement map with source references and editable grouping.
- [x] Preserve minority mechanisms and proposed discriminating tests even when the synthesis favors another path.
- [x] Support resolved, accepted bounded risk, deferred with reason, and blocked-pending-evidence concern dispositions.
- [x] Prevent accepting a required hard-gate failure as a discretionary risk.
- [x] Record strong/conditional consensus, majority with dissent, and unresolved as advisory agreement states.
- [x] Separate approval of an experiment from approval of a scientific finding.
- [x] Validate director authority, current revisions, concern closure, and dependency validity at approval.
- [x] Implement pause/resume, fresh independent round, and explicit cancellation of undispatched calls.
- [x] Reopen a prior decision as a new revision; invalidate affected descendants while preserving history.
- [x] Build concern/dissent panels and meaningful stale-context/blocked states.

### Exit gate

- [ ] A mid-round concern reaches all seats and blocks stale approval.
- [x] A majority decision retains its minority prediction and reopen trigger.
- [x] Reopening a prerequisite marks dependent decisions stale.
- [x] Unresolved discussion produces an evidence task instead of unbounded additional calls.

## 6. Version 0.5 Build research memory and experiment planning

**Target:** Oct 22. **Effort:** 8-10 hours.  
**Dependencies:** 0.4 governance and the frozen core experiment schema.  
**Requirements:** Z09-Z13, Z15, Z18, Z20, O02.  
**Outcome:** falsifiable hypotheses become bounded local/API experiments with visible trade-offs.

### Work checklist

- [x] Implement hypothesis revision/state history: proposed, testing, supported, falsified, blocked, superseded.
- [x] Link hypotheses to author/model/context, mechanism, source facts, predicted signature, and kill rule.
- [x] Implement trade-off cards with expected and observed pros/cons, hidden costs, mitigations, complexity, and valid operating region.
- [x] Represent the six discovery categories without requiring discovery of every type in the MVP.
- [x] Index negative results by hypothesis and normalized task/config/model/protocol hashes.
- [x] Use local domain-concept/lexical similarity as a duplicate suggestion, not authority to suppress an experiment; expose its approximation limits. See implementation decision 002.
- [x] Build causal nodes/edges connecting context/model choices to request count, output validity, measured latency, tokens, cost, and user result.
- [x] Label each node/edge measured, calculated, imported, inferred, or untested.
- [x] Define typed experiment plans with a falsifiable question, treatment/control, fixed task/source packet, repeat/order schedule, validators, limits, and approval.
- [x] Register allowed local numerical, evidence-validation, comparison, and Token Factory trial capabilities.
- [x] Reject unsupported provider settings and model-written shell commands before approval.
- [x] Rank experiments using disclosed information-value, impact, feasibility, and cost components; allow director override.
- [x] Create baseline/A/B/A+B request strategies and up to two evidence-motivated refinements only if budget permits.
- [x] Require a reframe when repeated proposals add no information, results contradict assumptions, or the director requests it.
- [x] Build Experiment Board and Research Map views over actual typed records.

### Exit gate

- [ ] A real objection becomes an approved, capability-valid test with a measurable prediction.
- [x] Missing controls or unsupported parameters block execution.
- [x] Every queued plan traces to a hypothesis, trade-off card, source packet, and mission revision.
- [x] The executor requires no external machine or additional service account.

## 7. Version 0.6 Execute local tools and Token Factory trials

**Target:** Oct 23-24. **Effort:** 8-10 hours.  
**Dependencies:** 0.5 plans and 0.2 durable budget/executor contracts.  
**Requirements:** Z15-Z18, Z22, O01-O03, H01-H02.  
**Outcome:** approved experiments create complete real evidence under the existing-credit limit.

### Work checklist

- [x] Implement registered capability handlers with typed arguments, allowed paths, size/time limits, and no arbitrary shell interpolation.
- [x] Validate mission/plan approval, hashes, actual model capabilities, and remaining reserved budget before execution.
- [x] Route every inference trial and escalation through the shared Token Factory adapter and cost ledger.
- [x] Execute fixed-order/balanced paired task blocks with controlled client concurrency and recorded request order.
- [ ] Run the selected context/model-routing treatments without assuming backend scheduling or hardware control.
- [x] Collect raw request manifests, exact model IDs, parameters, send/response/final timestamps, chunk events when available, usage, status, and errors.
- [x] Preserve per-attempt request IDs and distinguish ambiguous timeouts, rate limits, invalid outputs, and valid negative results.
- [x] Implement local source-ID checks, numerical/formula validation, constraint checks, and declared quality-rubric evaluation.
- [x] Implement analytical-bound tools with explicit inputs, units, assumptions, and calculated-evidence labels.
- [x] Import provided external artifacts only with source/provenance and unchanged raw content; never present them as newly executed measurements.
- [x] Normalize units and required fields deterministically; mark missing usage/cost/timing explicitly unknown.
- [x] Write raw artifacts, hashes, validator results, usage settlement, and terminal manifests to local storage.
- [x] Cancel undispatched requests immediately; keep already-dispatched maximum cost reservations until reconciled.
- [x] Recover local jobs after restart without automatically resending ambiguously completed requests.
- [x] Stop new work before the operational spending cutoff and produce an inspectable budget-exhausted outcome.

### Exit gate

- [ ] A real approved API experiment produces complete source/request/response/usage manifests.
- [x] A numerical tool reproduces a declared calculation without a model call.
- [x] Unapproved capabilities, requests exceeding limits, and unbounded costs fail before dispatch.
- [x] Cancellation and restart preserve evidence and financial reservations.
- [x] No hardware rental, model download, notebook, or cloud worker is needed.

## 8. Version 0.7 Close the evidence and reframe loop

**Target:** Oct 25. **Effort:** 8-10 hours.  
**Dependencies:** comparable 0.6 artifacts and 0.4-0.5 research state.  
**Requirements:** Z07, Z09-Z16, Z18, Z21, O01.  
**Outcome:** deterministic evidence changes the research direction and produces a bounded finding.

### Work checklist

- [x] Calculate complete-workflow latency, request count, token usage, attributable cost, valid-task rate, and rubric results from raw artifacts.
- [x] Keep TTFT/chunk timing optional and honestly named; do not manufacture per-token or backend timing.
- [x] Implement trial/task-level paired effects with frozen method, seed, exclusions, and sample count.
- [x] Separate pilot observations from any sufficiently powered confirmatory claim; allow descriptive/inconclusive results.
- [x] Implement pass/fail/unknown/invalid for each deterministic gate and prevent unknown required gates from confirming a result.
- [x] Compare baseline, A, B, and A+B on the preregistered metric scale; do not call a baseline improvement synergy by default.
- [x] Build the feasible Pareto set for quality/cost/latency with visible residual trade-offs and failed-gate exclusions.
- [x] Present the council with structured findings and evidence references, rather than a model-generated substitute for measurements.
- [x] Require comparison against predictions, changed assumptions, alternate explanations, and unresolved concerns.
- [x] Update hypothesis states and causal graph only with evidence-linked reasons.
- [x] Record the observed application bottleneck separately from speculative provider-internal explanations.
- [x] Trigger a reframe after failed local-to-user transfer, surprising quality cost, repeated weak ideas, or director instruction.
- [x] Produce a decision with dissent, limits, operating envelope, next action, and reopen triggers.
- [ ] Compare the council with a strong single-model planning baseline only within a disclosed separate evaluation budget; do not assume superiority.

### Exit gate

- [x] Failed or unknown hard gates cannot be overridden by agreement.
- [x] Evidence changes a recommendation, causal interpretation, or next experiment.
- [ ] Complete Frame -> Commit -> Reveal -> Review -> Execute -> Evaluate -> Reframe -> Decision on real API/local artifacts.
- [x] A rejected/inconclusive finding passes the software loop gate when its evidence and labels are valid.

## 9. Version 0.8 Complete the interface and reproducibility reports

**Target:** Oct 26. **Effort:** 8-10 hours.  
**Dependencies:** 0.7 complete loop and stable schemas.  
**Requirements:** Z18-Z22, O02-O03, H05, H10.  
**Outcome:** a coherent director workflow and exportable evidence pack.

### Work checklist

- [x] Complete Mission, Council, Experiments, and Findings workspaces with consistent step navigation.
- [x] Cover all eight vision views: Mission Room, Council Round, Diversity/Conflict Map, Experiment Board, Evidence View, Bottleneck Map, Decision Ledger, Breakthrough Report.
- [x] Expose concerns, pause/resume, fresh independent round, frozen constraints, approved tools, reframe, and reopen.
- [x] Show actual model IDs/reuse, context revision, live/replay/fixture mode, and settled/reserved/unknown budget.
- [x] Build baseline/single/combined comparisons with units, task scope, uncertainty, quality outcomes, and raw links.
- [x] Keep measured, calculated, imported, inferred, and untested research content visually distinct.
- [x] Make empty/loading/stale/blocked/invalid/budget-exhausted states understandable and keyboard-accessible.
- [x] Assemble reports from a fixed mission revision and deterministic gate state, not unverified prose alone.
- [x] Export final research plan/map, hypothesis registry, trade-off cards, evidence map, decision/concern/assumption registers, minority report, negative results, and next actions.
- [x] Generate JSON, Markdown, escaped self-contained HTML, and a portable ZIP with hashes and method versions.
- [x] Implement `verify_pack.py` and `reproduce.py --analyze-only` without a provider key or network call.
- [x] Document a live Token Factory rerun as a separate credit-consuming action requiring local credentials and the budget guard.
- [x] Sanitize secrets while retaining the technical provenance needed for inspection.
- [x] Review English wording, desktop layout, chart labels, and keyboard controls.

### Exit gate

- [x] The director completes a mission through the browser without manual model-answer copying or database edits.
- [x] An exported pack verifies and reproduces the same metrics and verdict offline.
- [x] The standalone report contains every required artifact with accurate evidence labels.

## 10. Version 0.9 Reproduce and harden the working test build

**Target:** Oct 27-28. **Effort:** 8-10 hours.  
**Dependencies:** 0.8 app/export and remaining approved Token Factory credit for any live confirmation.  
**Requirements:** Z16-Z22, O01-O04, H01-H05.  
**Outcome:** clean setup, restart/budget safety, inspectable evidence, and a functioning evaluation build.

### Work checklist

- [x] Freeze selected strategies before confirmation tasks are revealed to tuning workflows.
- [ ] Run the preregistered small confirmation schedule only if its full maximum cost fits the remaining budget.
- [x] Retain all attempts, failures, exclusions, and incomplete blocks; do not rerun until results look favorable.
- [ ] Compare day/time/model metadata and disclose hosted-service drift or unavailable backend revision information.
- [ ] Have a second operator verify pack hashes and reproduce analysis from a clean checkout.
- [ ] Exercise restart during partial commits, reveal, local execution, ambiguous API completion, and pending approval.
- [x] Test concurrent cost reservation, stale prices, hidden retries, underestimated output, and budget-boundary rejection.
- [x] Test invalid metrics, report escaping, secret redaction, and pre-reveal access boundaries.
- [ ] Verify no raw API key, authorization header, or private account credential appears in artifacts or repository history.
- [x] Document local database/artifact backup and restore.
- [x] Package the working local test build with setup and fixture/replay/live modes clearly separated.
- [ ] Select and verify free judging access or an acceptable functioning test-build distribution path; do not assume paid hosting.
- [ ] Preserve the judged release and document access through December 15 without exposing an unlimited public inference budget.
- [ ] If core work is complete and time permits, optionally inspect free notebook availability for extension X1. It is not a gate and creates no payment authority.

### Exit gate

- [x] Clean setup and offline reproduction work without cloud/GPU accounts.
- [ ] Bounded real Token Factory operation works with local credentials when authorized credit remains.
- [ ] No critical state, privacy, numerical-integrity, or spending-reservation issue remains.
- [x] The evaluation build/access instructions are tested from a fresh session.

## 11. Version 1.00 Package and submit

**Target:** Oct 29, with Oct 30 reserved. **Effort:** 5-7 hours.  
**Dependencies:** 0.9 working release candidate.  
**Requirements:** all core Z, O, and H requirements.  
**Outcome:** a complete hackathon entry reflecting the product's actual capabilities.

### Repository and documentation

- [ ] Add a root open-source LICENSE and verify public-host detection.
- [x] Finalize README: purpose, architecture, local prerequisites, Token Factory key setup, billing limits, run/test/reproduce commands, and limitations.
- [x] Explain that NVIDIA models run through Token Factory and local tools execute the scientific calculations/API tests.
- [x] Keep optional free hardware experiments documented separately; do not imply they were executed.
- [ ] Include source/assets, model/API/data permissions, notices, and documented large-artifact access.
- [ ] Link the final report to the release tag/commit and sanitized evidence pack.
- [ ] Review files/history for credentials and disclose pre-existing work where applicable.

### Demo story

Target 2:50, with visible live/replay/fixture labels:

| Time | Show | Evidence |
| --- | --- | --- |
| 0:00-0:15 | A research decision has conflicting proposals and hidden trade-offs. | Actual task and source packet. |
| 0:15-0:35 | Mission, constraints, acceptance rubric, and existing-credit cap. | Approved mission revision. |
| 0:35-0:55 | Four private proposals followed by reveal. | Actual model identities and submissions. |
| 0:55-1:15 | A human concern becomes a discriminating experiment. | Stored challenge and typed plan. |
| 1:15-1:45 | A short real local/API action and genuine saved trial evidence. | Request/tool artifacts and budget ledger. |
| 1:45-2:10 | Compare task quality, cost, latency, and validity. | Deterministic gates and uncertainty. |
| 2:10-2:35 | Reframe, dissent, bounded decision, and reproducibility export. | Ledger, causal map, and pack. |
| 2:35-2:50 | Explain the user value and actual NVIDIA/Token Factory integration. | Working architecture and call records. |

- [x] Use the outcome actually observed; do not preassign a correct minority or fake consensus reversal.
- [ ] Clearly mark historical results and time compression.
- [x] Do not show hardware-performance claims without corresponding optional real measurements.
- [ ] Record the functioning application and upload a public YouTube video under three minutes.

### Submission

- [ ] Select Coding and Agentic Engineering and explain the agent's tool execution and experimental decision loop.
- [x] Complete project description, measured outcome, limits, and platform feedback.
- [ ] Verify working demo/test-build URL, public repository/license/README, and public video.
- [x] Include English instructions, third-party permissions, and pre-existing-work disclosure as applicable.
- [ ] Verify entry eligibility, representative, required fields, and submission confirmation.
- [ ] Target Oct 29 at 18:00 Cairo and recheck links before Oct 30 at 19:00 Cairo.
- [ ] Preserve the judged release and the documented free testing/access path through Dec 15.

**Exit gate:** required submission artifacts and working access/test build are verified. Optional extension X1 is not required for submission.

## 12. Optional extension X1 free hardware experiment

Run this only after the core is working, if it would strengthen a research claim and time permits. Use the [optional protocol](optional/04_MEMORY_WALL_GPU_PROTOCOL.md).

- [ ] Verify a genuinely free Kaggle/Colab or borrowed compatible environment, actual hardware, allowed use, package support, and session limits.
- [ ] Export a bounded experiment specification and execute it through the notebook's supported interactive interface.
- [ ] Freeze a fresh hardware/model/engine/workload envelope; core API timings are not hardware baselines.
- [ ] Preserve raw measurements and explicit missing telemetry; import checksummed artifacts into ZeroWall.
- [ ] Certify hardware statements only to the extent the collected evidence supports them.
- [x] Leave the extension unstarted if access is unavailable; do not purchase capacity or block core releases.

## 13. Meaningful validation and handoff

| Area | Required checks |
| --- | --- |
| Independence | No early peer/browser answer access; four-seat barrier; same-context hashes. |
| Governance | Concern propagation, dissent, stale revisions, dependency invalidation, director authority. |
| Spend | Pre-dispatch reservations, concurrent requests, all retries, ambiguous charges, restart, absolute cap. |
| Experiments | Typed capabilities, matched tasks, raw provenance, deterministic metrics, invalid/missing outcomes. |
| Reproduction | Hash validation, offline verdict reconstruction, clean local setup, separately authorized live rerun. |
| Product | One real full mission, reconnect, accurate modes/labels, exports, working evaluation instructions. |

At handoff, record current mission/protocol/model-price revisions, passed gates, actual evidence paths, unresolved charges/uncertainty, remaining budget, and next dependency. GPU availability never appears as a core handoff blocker.
