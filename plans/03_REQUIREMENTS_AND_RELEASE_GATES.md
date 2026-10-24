# ZeroWall Requirements and Release Gates

**Scope revision October 18:** core releases use Token Factory inference and local tools. All requirements below are core unless explicitly marked optional. Self-managed GPUs, AI Cloud resources, free notebooks, CUDA, model hosting, and hardware profiling are not prerequisites or core release gates.

Every implementation status starts **Planned**. Requirements are satisfied by actual acceptance evidence, not by this document. Exact trial rules are in [the core protocol](04_RESEARCH_PROTOCOL.md); spending authority is in [Budget and access](05_BUDGET_AND_ACCESS.md).

## 1. Product and research traceability

| ID | Core requirement | Release | Acceptance evidence |
| --- | --- | --- | --- |
| Z01 | Freeze mission objective, deliverable, sources/tasks, constraints, rubric, budget, and step dependencies. | 0.1-0.2 | Approved revision, valid acyclic graph, current prerequisite checks. |
| Z02 | Four logical research seats, human director, non-voting orchestrator. | 0.1, 0.3-0.4 | Role definitions, real model identities, director actions, no orchestrator vote. |
| Z03 | Private independent Commit-Reveal before cross-review. | 0.3 | Prompt snapshots, pre-reveal endpoint inspection, atomic four-seat barrier. |
| Z04 | Real Token Factory routing follows the director's exact ordered allowlist, with explicit capabilities, reuse, and fallback. | 0.1-0.3 | Model/price manifest, disabled optional DeepSeek, unlisted-model rejection, capability probe, runtime traces, visible model IDs. |
| Z05 | Structured challenges address mechanism, controls, confounders, trade-offs, and evidence. | 0.4 | Reviews cite actual hypotheses and recommendation changes. |
| Z06 | Human concerns reach all researchers and remain until disposition. | 0.4 | Concern revisions, four acknowledgements, blocked stale approval. |
| Z07 | Preserve dissent and human final authority; evidence gates outrank agreement. | 0.4, 0.7 | Majority/unresolved decisions, minority report, failed-gate enforcement. |
| Z08 | Persistent decision memory, assumptions, dependencies, and reopening. | 0.2-0.4 | Restart recovery and stale-descendant propagation with immutable history. |
| Z09 | Falsifiable hypotheses and retained negative results. | 0.5, 0.7 | Predictions, kill rules, evidence-linked states, retrievable failures. |
| Z10 | Rank typed bounded experiments by information value, impact, feasibility, and cost. | 0.5 | Visible scores, director override, capability/limit validation. |
| Z11 | Trade-off cards represent synergy, conflict, constraint conversion, hidden-cost removal, adaptive hybrid, and new operating point. | 0.5, 0.7 | Schema coverage and expected/observed pros/cons for actual candidates. |
| Z12 | Causal graph and bottleneck timeline link proposed changes to observable user outcomes. | 0.5, 0.7 | Evidence-linked edges and distinct measured/inferred/untested states. |
| Z13 | Reframe after contrary evidence, failed transfer, repeated low-information ideas, or director request. | 0.5, 0.7 | Changed hypothesis, causal interpretation, scope, or next experiment. |
| Z14 | Primary objective plus validity/quality/cost gates and secondary latency metrics. | 0.1, 0.7 | Frozen rubric and deterministic pass/fail/unknown/invalid; no weighted-score bypass. |
| Z15 | Controlled baseline/A/B/A+B comparison of supported context/routing treatments. | 0.1, 0.5-0.7 | Matched task manifests, request records, ablation, and bounded interaction claim. |
| Z16 | Fair baseline, repeated/paired measurements, uncertainty, and separate confirmation. | 0.1, 0.6-0.7, 0.9 | Complete attempted schedule, exclusions, raw data, disclosed pilot limits. |
| Z17 | Provenance-recorded local numerical/API execution with restart-safe attempts. | 0.1, 0.6 | Approved typed plan, actual tool/API artifacts, request/model/config hashes, terminal attempt status. |
| Z18 | Distinguish measured, calculated, imported, inferred, and untested findings. | 0.1, 0.5-0.8 | Method/units/provenance and no certification of backend hardware behavior from API timings. |
| Z19 | Export complete research findings and reproducibility pack. | 0.8-0.9 | Required artifacts, checksum verification, offline analysis, bounded live rerun instructions. |
| Z20 | Cover eight vision views and director interventions coherently. | 0.2-0.8 | Full browser walkthrough across four workspaces and tabs. |
| Z21 | Complete a real mission and assess council usefulness without assumed superiority. | 0.7, 0.9 | Real inference/local experiment loop and a disclosed-budget single-model comparison or explicit evaluation limitation. |
| Z22 | Durable aggregate budget, request reservations, token/cost/latency records, and stop behavior. | 0.1-0.3, 0.6-0.9 | All attempts counted; concurrent/ambiguous spend handled; no dispatch above authorized allowance. |

The six discovery categories are representational capabilities. Core acceptance does not require discovering every category or a globally novel breakthrough. A measured negative result or inconclusive finding can demonstrate the research method.

Z17 is explicitly amended from the previous cloud-GPU-specific requirement to local/API experimental provenance. Earlier hardware metrics and environment gates apply only to optional extension X1.

## 2. Operational traceability

| ID | Core requirement | Release | Acceptance evidence |
| --- | --- | --- | --- |
| O01 | Durable state, idempotent transitions, attempt ownership, cancellation, and recovery. | 0.2-0.7, 0.9 | Failure-injection records and no duplicate ambiguous API dispatch. |
| O02 | Director-approved capabilities, authentication, key isolation, credit-only spending authority. | 0.1-0.6, 0.9 | Unauthorized/unbounded actions rejected; no arbitrary shell or secret leak. |
| O03 | Artifact integrity, escaped reports, backup/restore, and clean local setup. | 0.2, 0.6, 0.8-0.9 | Checksums, offline reproduction, documented restore, fresh checkout. |
| O04 | Working free judging access/test build through the judging period. | 0.9-1.00 | Tested distribution/access instructions and preservation through Dec 15, 2026; no paid-host assumption. |

Application budget controls do not prove provider-wide protection from card charging. Verify account behavior and credit source separately before live usage; unknown prerequisites block dispatch.

## 3. Hackathon traceability

The supplied `hackathon.txt` provides the requirements below. The official FAQ confirms runtime NVIDIA inference through Token Factory can meet the platform requirement without deploying the app on AI Cloud. [Official FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs)

| ID | Core requirement | Release | Acceptance evidence |
| --- | --- | --- | --- |
| H01 | Use at least one NVIDIA open model at runtime through Token Factory. | 0.1-0.2, 0.6, 1.00 | Real model identity and sanitized request/response/usage trace. |
| H02 | Fit Coding and Agentic Engineering through actual tool/config/code execution and evidence-driven planning. | 0.5-0.7, 1.00 | Typed local/API experiments and evidence changing the next action. |
| H03 | Provide a working demo or functioning test-build URL. | 0.9-1.00 | Fresh-session setup/access check and clear instructions. |
| H04 | Public repository containing needed source/assets and a visible open-source license. | 1.00 | Public repository URL and recognized root license. |
| H05 | README explains setup, run, test, Token Factory use, budget, and reproduction. | 0.8-1.00 | Successful clean-checkout workflow. |
| H06 | Public YouTube demonstration under three minutes showing the functioning product. | 1.00 | Verified visibility, duration, product footage, and real integration. |
| H07 | Project description and concrete feedback on services actually used. | 1.00 | Complete submission fields and specific technical explanation. |
| H08 | Disclose pre-existing work and comply with third-party permissions/licenses. | 0.1, 1.00 | Provenance, notices, permitted data/assets, change-period statement. |
| H09 | Register, review eligibility/rules, designate representative if needed, and submit on time. | 0.1, 1.00 | Entry checklist and submission confirmation. |
| H10 | English UI, instructions, reports, description, and video/captions. | 0.8-1.00 | Final materials review. |

Use the official rules for any conflict with the saved brief. Physical AI footage, Serverless deployment, LangSmith, Tavily, and Toloka/Tendem are not core integration requirements for this plan. [Official rules](https://nebiusglobalaihackathon.devpost.com/rules)

## 4. Artifact completeness

- [x] Approved research plan, mission envelope, and task/source manifests.
- [x] Research/causal map with evidence status and operating limits.
- [x] Hypothesis registry with predictions, kill criteria, and state history.
- [x] Expected/observed trade-off cards and retained alternatives.
- [x] Typed experiment queue and all execution attempts.
- [x] Raw request/tool artifacts with model/config/task/method hashes.
- [x] Metrics, uncertainty, validator results, and deterministic gates.
- [x] Decision ledger with reasons, dissent, conditions, and reopen triggers.
- [x] Concern register with dispositions and remaining blockers.
- [x] Assumption register with tested/untested status.
- [x] Minority report and negative-results history.
- [x] Bottleneck timeline and recorded reframes.
- [x] Budget ledger with settled/reserved/unknown attempts and remaining authorization.
- [x] Next actions with owner/capability, expected evidence, and completion criterion.
- [x] Reproducibility pack, checksums, offline commands, and optional live rerun limits.
- [x] Method and limitations distinguishing API observations from unobserved hardware mechanisms.

## 5. Release gates

| Version | Mandatory gate |
| --- | --- |
| 0.1 | Credit source/overage controls reviewed; bounded NVIDIA API probe recorded; mission/rubric/treatments frozen. |
| 0.2 | Local mission and budget persist; concurrency/restart reservations work; model call and UI events are traceable. |
| 0.3 | Four real private submissions reveal atomically with no early access or duplicate paid regeneration. |
| 0.4 | Cross-review, all-seat concern response, dissent, stale approval rejection, and dependency reopening work. |
| 0.5 | Falsifiable hypotheses produce approved capability-valid local/API experiment plans. |
| 0.6 | Real local/API execution preserves complete raw evidence and bounded spend through cancellation/recovery. |
| 0.7 | Deterministic gates, ablation, and evidence cause a recorded reframe or bounded conclusion. |
| 0.8 | Eight vision views and all required reports are usable; exported analysis reproduces offline. |
| 0.9 | Clean local setup, independent analysis, financial/recovery checks, and working evaluation build pass. |
| 1.00 | All core requirements and submission links/materials are verified; release/access instructions are preserved. |

- [ ] Every core requirement links actual evidence before completion.
- [x] Failed/unknown required gates retain their true labels despite director approval of the report.
- [x] No core gate waits for an external GPU, cloud quota, or free notebook.
- [x] No hardware result is inferred from Token Factory request timing alone.

## 6. Optional extension X1

This extension can use free notebook/borrowed hardware after the core works, if needed. It is not a core prerequisite and may remain unstarted.

- [ ] Verify genuinely free access, actual hardware, supported packages, allowed use, and session limits.
- [ ] Freeze a separate environment/model/engine/workload and measurement protocol.
- [ ] Preserve raw measurements, uncertainty, exclusions, telemetry gaps, and external provenance.
- [ ] Import results with correct measured/imported labels and certify only supported claims.
- [ ] Make no paid allocation or upgrade, and do not block release if access fails.

## 7. Judging evidence and change control

| Criterion | Evidence to show |
| --- | --- |
| Technological Implementation | Real NVIDIA/Token Factory calls; independent protocol; local typed tools; budget safety; evidence, recovery, and reproduction. |
| Design | One coherent mission flow, director controls, useful errors, visible trade-offs, and inspectable results. |
| Potential Impact | Specific research/engineering audience; measured coordination effort and task cost/quality/latency outcomes. |
| Quality of the Idea | A cross-layer objection becomes a discriminating experiment; evidence changes the research direction and retains minority insight. |

Do not claim universal multi-model superiority, provider hardware optimization, global Pareto optimality, or a world-first discovery from a small API case study. Record every requirement change with its source, affected IDs/revisions, and which prior evidence remains valid. The October 18 scope revision preserves the research council while removing mandatory hardware execution.
