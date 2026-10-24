# ZeroWall Masterplan

**Implemented, October 23:** [Council 1.06 — answering first, review alongside it](12_ANSWER_FIRST_COUNCIL_1.06.md), with its [checklist](12_ANSWER_FIRST_COUNCIL_1.06_CHECKLIST.md) and [release evidence](../docs/releases/COUNCIL_1.06.md). Durable public commits, separate stage results, partial annotation admission, recovery and natural synthesis build on the earlier council. The Super/Beam/DeepSeek baseline, 262K context and $24 shared existing-credit authority remain. Independent human quality evaluation is unperformed.

**Current implemented increment:** [Council 1.05 — cost, knowledge and research](11_RESEARCH_MEMORY_AND_COST_1.05.md) adds the token/price calculator, cumulative accounting, shared source library, bounded web research and measured context reuse. The current review workflow and Simple/Explain views are retained. See [release evidence and limits](../docs/releases/1.05.md).

**Retained review foundation, October 19:** [Unified Council 1.03](10_UNIFIED_COUNCIL_1.03.md) defines the retained current review workflow. It combines discussion and the 1.01/1.02 review capabilities into one product workflow named Council, removes version/mode choices from the planned UI and incorporates generic audit enhancements. That foundation shipped in application 1.3.0 and is extended by 1.05 above; live full-review reliability and independent answer quality remain pending. The original release scope below remains historical traceability.

**Updated:** October 18, 2026  
**Release target:** 1.00  
**Track:** Coding and Agentic Engineering  
**Inference:** director-approved open models through Nebius Token Factory, including verified NVIDIA runtime use  
**Application and tools:** existing local workstation  
**Spending authority:** at most $25 of existing Token Factory credit; $0 additional personal payments

ZeroWall is a human-directed research council. Four research seats formulate hypotheses independently, reveal them together, challenge assumptions, run bounded experiments, and preserve evidence, negative results, dissent, and decisions across a project. The director can raise concerns, pause, reframe, and reopen a decision.

The core release requires **no self-managed GPU, AI Cloud account, GPU rental, free GPU notebook, model download, or inference-server installation**. Token Factory hosts the models. Local code manages the research process and executes approved numerical, evidence-validation, and API experiments.

The memory-wall investigation remains a research topic. Hardware measurements are an **optional later extension**, using free resources if available. Until such measurements exist, hardware conclusions remain hypotheses or analyses of explicitly attributed external evidence.

## 1. Plan package

| Document | Purpose |
| --- | --- |
| [Blueprint and roadmap](01_BLUEPRINT_AND_ROADMAP.md) | Architecture, research protocol, contracts, persistence, interface, and release dependencies. |
| [Implementation plan](02_IMPLEMENTATION_PLAN.md) | Detailed engineering tasks and acceptance gates for versions 0.1 through 1.00. |
| [1.01 council extension](07_IMPLEMENTATION_PLAN_1.01.md) | Implemented generic scrutiny, repairs, scoped evidence, direct provider seats, constrained synthesis and evaluation tooling. Independent quality evaluation remains pending. |
| [1.02 scoped review and decisions](08_IMPLEMENTATION_PLAN_1.02.md) | Implemented atomic assertions, grouping, provenance/test audits and scoped decisions; made the default in application 1.2.2. Reliable live final compliance and independent quality remain pending. |
| [Unified Council 1.03](10_UNIFIED_COUNCIL_1.03.md) | Current forward plan: one named experience, independent ideas, targeted deliberation, author revisions, generic checks, useful synthesis and persistent follow-ups. Software implemented; independent evaluation remains pending. |
| [Cost, knowledge and research 1.05](11_RESEARCH_MEMORY_AND_COST_1.05.md) | Implemented: 20 features and completed software checklists; 387 backend tests, 28 browser scenarios, bounded live search/Gemini compatibility pilots. Optional paid cache/summary and model concurrency gates remain closed; independent answer quality remains pending. |
| [Requirements and release gates](03_REQUIREMENTS_AND_RELEASE_GATES.md) | Product, operational, and hackathon traceability. |
| [Core research protocol](04_RESEARCH_PROTOCOL.md) | Experiments measurable through Token Factory and approved local tools. |
| [Budget and access](05_BUDGET_AND_ACCESS.md) | Account readiness, credit verification, hard spending authority, and optional integrations. |
| [Model selection](06_MODEL_SELECTION.md) | Exact director-specified order, optional DeepSeek status, published price references, and runtime verification limits. |
| [Optional memory-wall protocol](optional/04_MEMORY_WALL_GPU_PROTOCOL.md) | A later free-GPU experiment; excluded from core release prerequisites and acceptance gates. |

Visual overviews: [system blueprint](diagrams/zerowall-blueprint.svg), [release roadmap](diagrams/zerowall-roadmap.svg).

Implementation checkboxes now link local acceptance evidence. See [current implementation status](../docs/IMPLEMENTATION_STATUS.md); live runtime and external release gates remain pending. A date, diagram, or fixture is not evidence of genuine model execution.

The 1.01 increment prioritizes a **generic council** before domain specialization. Its [review assessment](../docs/reviews/COUNCIL_REVIEW_1.01.md) separates reusable controls from physics-specific suggestions. See [implementation evidence](../docs/releases/1.01.md) for the completed software and pending quality gates; a design document alone is not acceptance evidence.

The [1.02 increment](08_IMPLEMENTATION_PLAN_1.02.md) adds software for scope-sensitive recheck and unsupported-observation warnings. Its [review assessment](../docs/reviews/COUNCIL_REVIEW_1.02.md) keeps the implementation generic; [release evidence](../docs/releases/1.02.md) separates passing software checks from pending live/semantic quality. It adds no mandatory model calls or domain specialization.

## 2. Source reconciliation and scope decision

| Source | Current interpretation |
| --- | --- |
| `thinking.txt` | Preserve independent Commit-Reveal, cross-review, human concerns, governed steps, persistent decisions, dissent, and reopening. Its AgentProof recommendation is superseded. |
| `th2.txt` | Preserve the research council, falsification, cross-layer reasoning, explicit trade-offs, and repeated reframing. |
| `ZeroWall_Vision_Document_AR.docx` | Preserve ZeroWall's identity, research disciplines, eight views, scientific artifacts, and human control. |
| `hackathon.txt` | Preserve track fit, real NVIDIA/Nebius use, public repository, working build, English materials, and submission deliverables. |
| Director's October 18 instructions | Remove dedicated GPU access from the core plan. Use Token Factory inference and local application execution. Consider free GPU experiments only later, if needed. |

This instruction supersedes the earlier mandatory Nebius AI Cloud worker and GPU-feasibility gates. It does not turn Token Factory into a controllable hardware benchmark environment.

## 3. Product and engineering decisions

1. **Four logical research seats:** Hardware and Physics; Driver and Runtime; Inference Engine; Model and Algorithms. Their lens can span the full stack even when some underlying mechanisms are not observable through the hosted API.
2. **Human director:** approves mission constraints, bounded tool permissions, final conclusions, and any prospective scope changes.
3. **Non-voting orchestrator:** owns state, context, barriers, retries, budgets, and audit events.
4. **Independent first submissions:** use the same shared mission/evidence revision, separate role instructions, and no peer answers before reveal.
5. **Model selection:** preserve the director's order: `nvidia/Nemotron-3.5-Super-VL`, `zai-org/GLM-5.3-Flash`, then `nvidia/Nemotron-3_5-Lightning`. `deepseek-ai/DeepSeek-V4.1-Flash` is optional and disabled. The [model policy](../config/model_policy.json) permits no unlisted automatic substitutions; seat reuse and actual identities remain visible.
6. **Local execution:** Python API and task executor, React/TypeScript interface, SQLite persistence initially, and local versioned artifacts. No paid hosting or database service is required.
7. **Deterministic authority:** code computes metrics and evaluates gates. Models interpret and propose; consensus cannot override a failed scientific gate.
8. **Bounded API use:** every request and retry reserves its maximum estimated cost before dispatch. The absolute aggregate authorization is $25 of existing credit, with an operational stop below that amount.
9. **Supported experiment surface:** request context, API model routing, application scheduling, numerical calculations, fixture validation, and supplied dataset analysis. Use only parameters the chosen endpoint actually supports.
10. **Deferred hardware work:** no kernel, driver, memory-bandwidth, power, or GPU-memory measurements are required for 1.00. Optional measurements need their own recorded environment and protocol.

## 4. What the first release proves

The first mandatory evidence mission tests **hosted research-workflow efficiency and evidence quality**. The council proposes and evaluates a bounded change to context packing and/or model routing, using a fixed set of research tasks with inspectable sources and scoring rules.

The local executor sends real Token Factory requests, records complete responses, timestamps, token usage and cost, runs deterministic validators, and compares baseline, A, B, and A+B. The council revisits its prediction when results show a cost, latency, quality, or evidence-validity trade-off.

This supplies an executable demonstration without renting infrastructure. It measures the complete application/API workflow and does not claim access to the provider's hardware, scheduler internals, or physical memory traffic. The exact matrix, task count, model IDs, and claim thresholds are frozen after a small budgeted capability probe.

Memory-wall research can also use analytical models and properly attributed external artifacts. Those are labeled calculated or imported evidence. They do not become new hardware measurements merely because the council discusses them.

## 5. Core user journey

The director creates a mission, freezes its goal, deliverable, constraints, evidence packet, acceptance rubric, and budget. Four researchers submit independent hypotheses. Reveal exposes the complete set together. Cross-examination identifies disputed mechanisms and turns a concern into a measurable question.

The director approves a typed local experiment. The executor validates the plan and budget, makes permitted API calls or local calculations, and preserves raw artifacts. Deterministic analysis produces metrics and gate results. The council updates its causal model, records rejected assumptions and dissent, and proposes the next test or a bounded conclusion.

The director approves or reopens the decision. The report includes the research map, hypothesis registry, trade-off cards, concern/assumption registers, minority report, negative results, evidence, and reproducibility instructions.

## 6. Success conditions

### Product success

- A real mission completes without manually copying model answers between chats.
- All four initial submissions persist before any peer-answer content is published.
- Human concerns reach every researcher and block stale approvals.
- A disputed hypothesis produces an approved local/API experiment.
- Evidence changes a recommendation, causal interpretation, or next action.
- The research history, budget reservations, negative results, and decisions survive restart.
- A second operator reproduces the numerical analysis from exported artifacts without a provider key.

### Evidence success

- Real endpoint responses are distinguishable from fixtures, imported evidence, and replay.
- Comparisons hold task inputs and scoring rules fixed and disclose model/routing differences as treatments.
- Benefits are reported with quality, validity, cost, latency, failures, and uncertainty.
- Inconclusive or adverse outcomes remain valid findings; no positive speedup is promised.
- Hardware-level statements are not certified from API observations alone.

## 7. Rebased release calendar

All dates are in Africa/Cairo. None of these releases is marked complete.

| Target | Version | Outcome |
| --- | --- | --- |
| Oct 18 | 0.1 | Confirm credit controls, API capabilities, mission, and local execution contracts. |
| Oct 19 | 0.2 | Persistent local application, model adapter, budget ledger, and mission shell. |
| Oct 20 | 0.3 | Independent Commit-Reveal. |
| Oct 21 | 0.4 | Cross-review, concerns, decisions, and step governance. |
| Oct 22 | 0.5 | Hypotheses, trade-off cards, and typed experiment queue. |
| Oct 23-24 | 0.6 | Real Token Factory/local experiments and raw evidence capture. |
| Oct 25 | 0.7 | Gate evaluation, interaction analysis, and reframe loop. |
| Oct 26 | 0.8 | Complete research workspaces and reproducibility reports. |
| Oct 27-28 | 0.9 | Independent analysis reproduction, recovery, and working test build. |
| Oct 29 | 1.00 | Licensed public repository, short video, and submission. |
| Oct 30 | Buffer | Link/access/submission fixes before the deadline. |

The proposed effort is **72-92 focused engineering hours**, plus contingency. The schedule remains intensive. Cut optional features before weakening the budget guard, evidence integrity, or final deliverables.

The official deadline is October 30, 2026 at 17:00 UTC, **19:00 Cairo on that date**. Target submission on October 29 at 18:00 Cairo. [Official rules](https://nebiusglobalaihackathon.devpost.com/rules)

## 8. Critical path and scope cuts

**Critical path:** credit-source/overage verification -> scoped API key -> bounded capability probe -> persistent council -> typed experiments -> evidence and reframe -> reproducible test build -> submission.

| Trigger | Response |
| --- | --- |
| API key or billing controls not ready | Build contracts and interface with labeled fixtures. No live spend and no false live-integration pass. |
| Preferred model unavailable or unaffordable | Stay within the ordered allowlist and verified request budget; stop if safe selection is unavailable. Never silently enable optional DeepSeek or substitute an unlisted model. |
| Live budget runs low | Stop new experiments before the absolute cap; use saved genuine artifacts for replay and offline verification. |
| No candidate improves the workflow | Report a rejected hypothesis, measured conflict, or inconclusive finding. |
| UI work threatens the core loop | Keep four workspaces with tabs; cut animation and decorative graph layouts. |
| Free GPU unavailable | No impact on core release gates. Leave optional extension X1 unstarted. |

## 9. Optional extension X1 after the core works

If hardware experiments would strengthen the research case, investigate a free Kaggle/Colab notebook or another explicitly free compatible resource. Availability, package support, telemetry, and session limits must be checked then. No paid GPU signup, payment method, or allocation is a prerequisite for core development.

Export a bounded experiment plan, run it through the provider's supported interactive notebook flow, and import the actual measurements. Record hardware/software provenance and apply the optional protocol. Do not host ZeroWall on a free notebook or convert it into an always-on remote worker.

A failed or unavailable optional experiment cannot prevent release 1.00. Any claim about physical performance still requires real comparable hardware evidence.

## 10. Readiness and submission

Current readiness: Devpost joined; Token Factory balance reported; default project available; GitHub username `AlphaSudo`; a nonempty local API key entry is present. Key validity, model access, and billing are not yet tested. Keep `default-project`. Verify the $25 credit origin and overage behavior before live calls. Full details are in [Budget and access](05_BUDGET_AND_ACCESS.md).

Calling an NVIDIA open model through Token Factory satisfies the event's platform requirement; the application need not also run on AI Cloud. [Official FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs)

Deliver the working application/test build, public licensed repository, setup README, English project description, public YouTube video under three minutes, and feedback on the services actually used. Keep the tested release and free judging access/test-build instructions available through December 15, 2026. A paid public host is not an assumption; the chosen access approach must be verified before submission. [Official rules](https://nebiusglobalaihackathon.devpost.com/rules)

## 11. Implementation working agreement

Before each release, explain the design choice, files to change, and risk being resolved. During coding, share material findings and trade-offs with the director. At completion, demonstrate the behavior, link acceptance evidence, record limits, and identify the next dependency.

Planning edits do not authorize account creation, credit redemption, paid upgrades, external messages, publication, or submission. The user has explicitly prohibited additional personal payments.
