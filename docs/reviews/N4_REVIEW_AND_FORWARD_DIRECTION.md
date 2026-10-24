# N4 review: diagnosis and forward direction

The product must evolve through 1.01 and 1.02. Preserving old records is a compatibility requirement, not a reason to make an older workflow the current default.

## What actually happened

The supplied `n4.txt` contains independent openings, three discussion-round headings and two partial syntheses. It contains no extraction, scrutiny, repair or recheck stage headings. The currently open saved conversation, `chat_5d06a0522f694176`, likewise has `mode=discussion`, `protocol.version=discussion_v1`, and no review record. These observations establish that those runs bypassed the claim-review pipeline; they do not establish that its implementation was removed.

The application had two incorrect entry defaults for the user's intended workflow: `CouncilChat.tsx` selected Discussion, and its review-method selection initially chose 1.01. The API also defaulted to Discussion/1.01. The prior continuity patch preserved those defaults and continued the existing Discussion conversation. That was an integration failure. It was not a restoration of the 1.01 review engine as a replacement for 1.02.

The forward correction makes 1.02 the normal UI and API default. Existing transcripts retain their actual method. An explicitly submitted 1.02 follow-up starts a new review cycle in the same chat, archives the previous protocol and preserves every earlier message and publication. Merely loading an old conversation does not relabel its answers or dispatch inference.

## Suggestions compared with the repository

| Reviewer concern | Present in 1.02 | Actual remaining gap |
| --- | --- | --- |
| Atomic claims and stable IDs | Atomic assertions, source spans, per-author coverage, stable IDs and revisions | The bounded initial profile cannot guarantee extraction of every material assertion in a long source. Coverage gaps must remain visible. |
| Claim classification | Reasoning kind, quantitative/causal/etc. properties, scope and evidence obligation | Typed equation and resource descriptions need more explicit representation. |
| Semantic deduplication | Equivalent/related/conflicting claim groups preserve authors and revisions | Claim groups are fallible assessments; distinct solution-family ranking needs its own criteria. |
| Dedicated falsification | A separate scrutiny role targets each claim with objections and candidate counterexamples/tests | Stronger auditable subchecks are needed for equations, resources and literature assertions. An extra role name alone will not solve this. |
| Author repair | Retain/rebut/narrow/revise/withdraw, original source/history, revised scope and uncertainty | Validate semantic fidelity with independent examples; successful schema admission is insufficient. |
| Adjudicated recheck | Original and current revisions, closure basis, ordinary risk, missing evidence and new issues | More explicit proof/check provenance is needed. Model resolution remains an assessment. |
| Separate risk and evidence | Separate review state, evidence state, assumptions, blockers, residual risks and suitability | Preserve this separation; do not return to blocking every useful conditional option because it has residual risk. |
| Evidence provenance | Full-source observation warnings, source-linked evidence, human scope assessment, integrity checks | A generated literature reference is not automatically retrieved or verified. The existing observation scanner is not a literature verifier. |
| Constrained final synthesis | Current claim/revision references, eligibility guards, supported-section restrictions and immutable publications | Scientific correctness and prose faithfulness require separate evaluation. A valid reference graph does not prove an equation. |
| Equation/numerical audit | No general typed equation-audit subsystem | Add explicit quantity kinds, units, assumptions, derivation references and bounded numeric checks. |
| Resource accounting | Mission constraints and claim assumptions exist | Add a generic ledger of inputs, outputs, boundaries, costs and unaccounted resources. |

The relevant implementation remains in `council_review_v2.py`, the scoped DTOs in `contracts.py`, `review_policy_v2.py`, `review_provenance.py`, and the existing review inspector. The v2 engine reuses the durable 1.01 schedule and extends it. Deleting these components and starting over would discard useful implemented behavior.

A direct archive comparison also confirms that `council_review_v2.py`, `review_policy_v2.py`, `review_provenance.py` and `quality_v2.py` are byte-identical to the saved `ZeroWall-1.02-preview.zip`. This is concrete evidence that the 1.02 implementation was retained while its entry point was wrong.

## What to accept, adapt or reject

Accept the need for a regression corpus built from concrete failures; explicit equation, numeric, constraint, resource and provenance checks; author repair; independent recheck; constrained publication; and tests for false rejection. Accept the distinction between conditionally usable proposals and externally supported assertions.

Adapt the proposed thirteen stages into logical gates with records and coverage reporting. They do not require thirteen extra model calls or thirteen supposedly independent agents. Keep generic logic reusable across software design, planning, engineering and physical hypotheses. Apply numerical and physical checks only when their required representations are present; record missing inputs rather than inventing them.

Adapt semantic merging into provenance-preserving relations. Similar wording does not establish equivalent scope, assumptions or independent support. Never let repetition increase evidence strength. A request for five approaches can produce fewer than five independent families, with variants listed separately, if the reviewed material does not justify five.

Reject treating a model labelled “Epistemic Judge” as a truth authority. Publication permission must still come from versioned application policy operating on recorded assessments and appropriately scoped evidence. Reject the reviewer's numeric grades and claimed improvement percentages as measured evaluation results: no independent scoring procedure, denominator or validated reference set was supplied.

Reject using all ten suggested scientific verdicts as unquestionable gold labels. Some are good candidate defects, but each needs an exact source passage, declared assumptions and a justified expected result. The rendered `n4.txt` duplicates some mathematical text and breaks formulas across lines; prefer the original stored text or a review pack before building equation tests. The reviewer is another fallible source.

## Scientific spot-checks and limits

There is primary research supporting angular restriction and photon recycling as useful design directions under specified device assumptions. A detailed-balance GaAs study predicts efficiencies above 38% for a particular single-junction configuration and discusses tracking and losses; it does not demonstrate a practical 93.3% one-sun converter. Use the paper for its actual scope, not as general confirmation of the council's conclusion. [Kosten et al., 2013](https://www.nature.com/articles/lsa20131).

The 86.8% and 93.3% bounds depend on conversion architecture and assumptions. A primary thermal-photonics paper distinguishes reciprocal multicolor and nonreciprocal limiting constructions. Therefore, the original framing and the reviewer's preferred conclusion both need qualification; an auditor must not assume that their difference is universally just an angular-mismatch penalty. [Park et al., author-hosted primary paper](https://energyzhao.github.io/pdf/Park%20et%20al.%202022%20Nano%20Letters.pdf).

For Faraday rotation, the documented `V B L` relation describes a polarization rotation angle. However, SI treats radians as dimensionless: a dimension-only engine may fail to distinguish angle from refractive-index change. The useful check is quantity kind and derivation, not a guaranteed dimensional contradiction. [Thorlabs Faraday-rotation documentation](https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=12211&tabname=Optical+Isolators).

Likewise, a Carnot expression can be valid for its declared heat-engine boundary while being misapplied as a radiative-exergy bound. An entropy balance requires a declared sign convention, all transfer ports and any accumulation term. A static magnetic bias must be distinguished from driven coils and maintenance losses. A reference string proves neither that a paper exists nor that it supports a performance number. These distinctions are essential negative controls for the proposed auditors.

The arithmetic difference between 93.3% and 86.8% is 6.5 percentage points. That calculation is independently checkable; it does not prove the applicability of either bound to the proposed device.

## Evaluation discipline

Use the ten suggested defects as candidate cases, paired with valid controls. Separate arithmetic errors, model-boundary errors, missing derivations, unsupported empirical assertions and speculative mechanisms. Do not conflate unsupported with false, or model-assessed closure with external verification. Locate each alleged defect in the source before reporting recall.

An 8/10 target is a proposed acceptance threshold, not achieved recall. Both defect detection and false rejection need independently reviewed labels and held-out cases. Fixed scripted model outputs are appropriate for testing routing and policy gates, but cannot measure intelligence or scientific recall. The existing independent 1.02 quality gates remain open.

The concrete next implementation work is consolidated in [the unified Council plan](../../plans/10_UNIFIED_COUNCIL_1.03.md). It incorporates the audit requirements from the earlier draft and combines discussion and review in one current workflow. The immediate routing correction was implemented separately so that the existing 1.02 functionality is actually used.
