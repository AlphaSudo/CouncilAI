# Council enhancement review for version 1.01

Date: October 18, 2026. Status: design review, not implementation or scientific validation.

Implementation amendment, October 19: the director subsequently requested four direct provider seats and removal of OpenRouter for current work. The [release record](../releases/1.01.md) implements that instruction, superseding this assessment's initial two/three-seat limit. Software and offline scoring tooling are implemented; independent semantic quality evidence remains pending.

The supplied reviewer had no repository context. This assessment compares the suggestions with the current code and keeps the council generic. The proposed implementation is in [the 1.01 plan](../../plans/07_IMPLEMENTATION_PLAN_1.01.md).

## Assessment

The strongest recommendation is to make claims, objections, repairs, and evidence inspectable instead of hoping that a longer argument produces a reliable conclusion. A dedicated critic is useful as a function. Its conclusions remain fallible model assessments.

The existing chat already provides independent openings, a shared reference baseline, ordered discussion, actual model identities, saved messages, director interventions, partial synthesis, and bounded provider recovery. It does not yet provide a typed claim ledger or enforce claim-level evidence requirements on the final answer. That is the main 1.01 opportunity.

The research workspace already has frozen briefs, hypotheses, structured submissions and cross-reviews, concerns, typed experiments, evidence artifacts, decision gates, reframes, and reproducible reports. The change should connect those ideas to chat without forcing every ordinary question through the research workspace's four specialized seats or its API performance experiment gates.

## Decisions on the review

| ID | Suggestion | Decision | Repository-grounded adaptation |
| --- | --- | --- | --- |
| D01 | Keep opening answers independent. | Keep; already implemented. | Preserve the existing opening context isolation. Seeing replies in the UI does not give another model access to them during its opening. Distinct model IDs do not establish statistical independence of their errors. |
| D02 | Require a fixed proposal format. | Adapt. | Ask for a concise answer, assumptions, material claims, rationale, limitations, and a way to test the answer. Energy, entropy, equations, and physical mechanisms are optional task-specific fields. Ask for inspectable justification, not private internal reasoning. |
| D03 | Extract atomic claims. | Accept. | Add versioned claim records with exact source spans, scope, assumptions, dependencies, and evidence links. Keep extraction omissions visible as a coverage limitation. A model's decomposition is not a complete semantic proof of coverage. |
| D04 | Add a falsification-only critic. | Accept with limits. | Use a scrutiny phase that targets explicit claims, gives a concrete objection or candidate counterexample, and states what would resolve it. It cannot select a winner or declare its own attack authoritative. It may state a minimum repair condition without replacing the proposal. |
| D05 | Run five specialized auditors plus a separate counterexample hunter. | Combine in 1.01; defer separate seats. | One bounded scrutiny call uses applicable checks for reasoning, constraints, evidence, resources, feasibility, and counterexamples. Record what was not checked. Separate roles are functions first, not a requirement for many additional models or calls. |
| D06 | Apply a mandatory list of physical laws. | Reject as the generic default. | Only explicit task constraints and applicable, sourced domain checks belong in a review. Solar conversion, thermodynamics, quantum constraints, GPU telemetry, and memory-wall experiments remain future domain profiles. This review does not validate the supplied physics examples or formulas. |
| D07 | Audit all resources and hidden costs. | Generalize. | Track relevant money, time, data, permissions, dependencies, operating conditions, and other inputs and outputs. Unknown cost is unknown, not zero. A physical resource ledger can be added later without changing the core claim protocol. |
| D08 | Separate established, demonstrated, extrapolated, and speculative claims. | Adapt. | Separate evidence origin, review opinion, and publication status. Demonstrated claims need actual scoped evidence; imported measurements remain imported. Labels such as established require an explicit evidential basis rather than a model's confidence. |
| D09 | Add adversarial limit and counterexample tests. | Accept as proposals; execute through existing authority. | Use generic boundary, assumption-removal, known-case, sensitivity, resource, and failure-path tests. A suggested test is not a test result. Only allowlisted, typed local tools run; no arbitrary generated code or automatic network research. |
| D10 | Give the proposer a repair opportunity. | Accept. | Preserve the original claim, specific objection, response, revision, withdrawal, and remaining uncertainty. New assumptions create a visible conditional revision; a changed goal requires a new contract revision. Repaired claims require a recheck. |
| D11 | Judge with hard gates rather than voting. | Accept for enforceable checks; limit semantic authority. | Server policy checks provenance, revision freshness, required evidence, and honest labels. It cannot prove arbitrary mathematics, engineering feasibility, or scientific compatibility. A model-reported defect is an open issue until adjudicated with an explicit basis. |
| D12 | Restrict successful-result sections while retaining rejected and unresolved proposals. | Accept with generic labels. | Prevent unsupported claims from being presented as established results. Keep withdrawn, contradicted, disputed, and incomplete ideas visible in separate sections. An unresolved hypothesis can still be useful; absence of evidence does not prove impossibility. |
| D13 | Attach a verdict and confidence from 0 to 100. | Reject numerical confidence as a gate. | Use review outcomes with reasons and evidence. A future calibrated confidence feature would require its own evaluation. Retained self-reported confidence, if ever displayed, must be marked uncalibrated. |
| D14 | Set thresholds such as mathematical validity below 60 means invalid. | Reject. | These thresholds have no supplied calibration or validated scoring procedure. Use pass, fail, unknown, and justified not-applicable for narrowly defined checks. Never average away a failed mandatory check. Existing human performance rubrics remain scoped to their original experiments. |
| D15 | Add an epistemic judge and constrained synthesizer. | Adapt. | A recheck call reports proposed dispositions. Deterministic policy then computes publication permissions. A final model writes within those permissions; a server-rendered claim/evidence table remains authoritative. No extra model receives unilateral approval power. |
| D16 | Require three to five proposers and many parallel reviewers. | Reject as mandatory architecture. | Support two or three selected models for the initial reviewed profile. The current API permits up to four models in ordinary chat; that remains available. Preserve the existing queue, database, provider guards, and cost limits. |
| D17 | Describe the lighter design as four roles. | Clarify the counts. | These are four role categories, including three proposer seats plus verifier, falsifier, and judge/synthesizer. That is six assignments if each uses a separate seat. Role categories are not model identities, calls, or independent evidence sources. The implementation plan specifies actual call counts. |
| D18 | Prevent consensus from substituting for proof. | Accept. | Agreement may be reported as agreement with attribution. Evidence and scoped validation determine support. Neither consensus nor the absence of an objection is a verification result. |

## Additions needed beyond the review

These are engineering safeguards derived from the repository and its observed failures, not claims that the reviewer explicitly specified them.

1. **A frozen review contract.** Extend the existing frozen chat protocol with explicit constraints, evidence requirements, applicable checks, role assignments, limits, and versions. Keep ordinary prompt entry simple; never invent director-approved requirements from a model's interpretation.
2. **Separate opinions from authority.** Model assertions, human assessments, tool observations, evidence provenance, and server eligibility decisions need different fields. This prevents a critic or a source document from granting itself verification authority.
3. **A bounded claim scope.** Start with up to four material claims per proposer. Preserve the original answer and display extraction coverage and omitted material. Overflow cannot silently become reviewed content.
4. **Dependency and revision invalidation.** Evidence for an old claim cannot certify a repaired claim with changed assumptions. A dependent conclusion must become stale when a premise changes or loses support.
5. **Context preservation.** Mandatory constraints and unresolved objections cannot disappear because an older message falls outside the recent-transcript window. Build a compact review packet from durable structured records.
6. **Provider degradation rules for every phase.** Losing a model during scrutiny or recheck must not silently turn an unreviewed draft into a reviewed result. Reuse bounded retries; surface a partial result or wait for an explicit continuation choice.
7. **A conservative synthesis fallback.** Typed output, allowed claim references, and deterministic labels can constrain rendering. They cannot establish that every paraphrase is semantically faithful. If synthesis parsing or reference checks fail, publish an evidence-labelled ledger summary without another hidden API call.
8. **A generic evaluation harness.** Test wrong critics, plausible false claims, unsupported novelty, missing citations, goal drift, incomplete coverage, and provider failures. Evaluate usefulness as well as caution so that the system does not improve apparent safety merely by refusing to answer everything.

## What the research supports, and what it does not

Multiagent debate improved factuality and reasoning on tasks studied by Du and colleagues. That supports testing the approach, not assuming a universal benefit for ZeroWall's current models and questions. [Primary paper](https://arxiv.org/abs/2305.14325).

Huang and colleagues found that intrinsic reasoning self-correction without external feedback can fail or worsen answers in their evaluated settings. This supports adding checkable feedback and a harness; it does not establish that all critique or revision is useless. [Primary paper](https://arxiv.org/abs/2310.01798).

Kadavath and colleagues report useful self-evaluation signals under particular setups and difficulties with calibration on new tasks. Therefore, this plan does not treat a casually prompted confidence percentage as a calibrated probability for this council. [Primary paper](https://arxiv.org/abs/2207.05221).

The engineering inference is modest: review functions are worth building, while their actual quality must be measured. None of these papers validates the reviewer's specific physics criticism, the proposed numerical score thresholds, or guaranteed correctness after debate.

## Scope and compatibility

Version 1.01 is a generic council extension. It adds no required GPU, cloud account, vector database, paid observability service, search subscription, or new credential. Existing conversations retain their recorded protocol and ordinary discussion mode. The initial reviewed mode is opt-in until its software and quality gates are met.

Token Factory remains behind its existing billing-verification gate. The $25 existing-credit ceiling, $0 additional payment rule, and $0 GPU rental budget continue to apply. OpenRouter free availability cannot be guaranteed by a larger review pipeline. No live inference was needed for this design review.
