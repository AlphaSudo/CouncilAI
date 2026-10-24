# Forward plan 1.03: generic audit records on top of 1.02

**Historical draft, consolidated October 19:** implement [the unified Council plan](10_UNIFIED_COUNCIL_1.03.md). It incorporates sections A-H below and adds one product entry point, bounded deliberation, useful final answers and same-chat follow-ups. This document is retained for traceability, not a second implementation track.

This plan extends the existing 1.02 engine and policy. It does not replace them with 1.01, restart the project, or specialize the product to solar physics. Its source assessment is [the N4 review analysis](../docs/reviews/N4_REVIEW_AND_FORWARD_DIRECTION.md).

## A. Activate the implemented workflow

- [x] Make Scoped review 1.02 the ordinary browser and API default.
- [x] Display the actual active method in every conversation.
- [x] Let an explicit 1.02 follow-up start a review in the same conversation.
- [x] Preserve earlier messages, protocol hashes, 1.01 review records and publication snapshots.
- [x] Use fresh review-cycle source IDs and cycle-specific baselines; do not retroactively certify earlier discussion.
- [x] Preflight the full review schedule and daily allowance; loading an old conversation must dispatch no inference.
- [x] Test the normal entry point and both Discussion-to-1.02 and 1.01-to-1.02 transitions.

This is the immediate integration correction. The additional audit capabilities below are planned work, not already implemented or scientifically validated.

## B. Typed audit records and complete coverage accounting

Implementation: extend the claim descriptors with optional equation, numeric quantity, resource, citation and comparison-family records. Bind every record to exact source spans, claim IDs, revisions, scope and origin. Preserve unsupported and hypothetical material explicitly. Keep original text separate from normalized forms.

- [ ] Define strict DTOs for quantities, equations, calculation inputs, resources and citation assertions.
- [ ] Record coverage for material equations and numbers outside the initial extracted claims.
- [ ] Mark overflow or missing representations as incomplete coverage rather than silently claiming a complete audit.
- [ ] Retain the bounded profile and allow explicit additional review batches when the question exceeds it.
- [ ] Reject invented source spans and references; preserve qualifiers and dependency revisions.

Acceptance: a source containing more material than fits the profile produces a visible coverage limitation. No omitted assertion acquires an accepted status through the final prose.

## C. Equation and numeric checks

Implementation: add a bounded local check service with declared capabilities. Separate deterministic arithmetic/unit checks from model critiques of derivation or applicability. Use a parsed, allowlisted representation; do not execute arbitrary model-supplied code. Keep each check's inputs, assumptions, method/version, result and limitations.

- [ ] Represent quantity kinds as well as dimensions, including angle versus index, energy versus energy rate, fractions versus percentage points.
- [ ] Check arithmetic, declared units and explicitly supplied limiting cases where the representation permits it.
- [ ] Record sign conventions, accumulation terms and boundary ports for balance equations.
- [ ] Require derivation/source support separately from dimensional consistency.
- [ ] Treat failed parsing or missing assumptions as unknown, not an automatic mathematical refutation.
- [ ] Test a valid Carnot calculation beside a misapplied radiative-bound claim; test correct Faraday rotation beside an incorrect quantity interpretation.

Acceptance: `93.3 - 86.8` yields 6.5 percentage points, while a valid 95% Carnot calculation is not rejected merely for containing 95%. A dimensionless result alone cannot establish the correct physical quantity or mechanism.

## D. Constraint and resource accounting

Implementation: attach a generic boundary ledger to relevant claims. Record required inputs, useful outputs, consumed resources, environmental reservoirs, maintenance and omitted terms. Instantiate it for CPU/memory/network budgets, money/time/people and physical energy/material systems as appropriate.

- [ ] Require numerator, denominator, boundary and conditions for ratios and efficiency-like assertions.
- [ ] Distinguish passive/static requirements, driven operating inputs and maintenance costs.
- [ ] Bind numerical resource values to actual sources, assumptions or measurements.
- [ ] Preserve unknown inputs and test whether they can change the decision.
- [ ] Keep ordinary residual risk separate from violated requirements and missing decision-changing resource terms.

Acceptance: an unsupported “no overhead” assertion remains unsupported; a static bias is not automatically assigned continuous operating power. The same mechanism applies to uncounted cloud fees, memory copies or human review time.

## E. Citation and evidence provenance

Implementation: separate reference identity, retrieved content, exact support passage, conditions and claim relevance. Reuse the existing evidence ledger and scoped relevance assessment. A generated citation begins as a model assertion. Retrieval, when available and explicitly within the account budget, is a distinct recorded operation.

- [ ] Distinguish model assertion, supplied source, assumption, hypothetical example and externally obtained evidence.
- [ ] Record paper/document identity and exact excerpts separately from an assessment of support.
- [ ] Prevent an existing DOI or title from automatically validating a performance number.
- [ ] Preserve conditions, conflicting evidence, partial scope and missing retrieval.
- [ ] Require provenance before attributing a model-reported experiment to actual execution.

Acceptance: invented journal references and unverified performance numbers cannot appear as externally supported facts. A genuine source supporting a narrower result cannot certify a broader claim.

## F. Falsification, repair, recheck and publication

Implementation: extend existing scrutiny and recheck records with the new audit outputs. Retain a dedicated critic role focused on claims, counterexamples and failure tests. Reuse the existing original-author repair history, scope changes, new-issue handling and pure publication policy.

- [ ] Link each objection to the exact assertion and declared assumptions.
- [ ] Audit candidate-test discrimination, baseline fairness, threshold basis, proxy validity and repeatability.
- [ ] Preserve original claim, objection, author response, revision/withdrawal and uncertainty.
- [ ] Separate addressed objection, partial resolution, conditional usability, unsupported assertion, evidenced contradiction and new objection awaiting review.
- [ ] Keep model assessments distinct from trusted tool observations and human source assessments.
- [ ] Evolve publication semantics under a new frozen policy/protocol version only when these gates change; retain replay of prior 1.01 and 1.02 publications.
- [ ] Ensure unsupported or rejected material is clearly labelled and cannot become a positive supported recommendation through prose or majority repetition.

Acceptance: changing a premise invalidates dependent conclusions until rechecked. A narrowed conditional option with ordinary residual risk remains distinguishable from an unresolved hard requirement. No role name grants truth authority.

## G. Independent approach families

Implementation: extend the current reversible claim groups with explicit family criteria: principal mechanism, boundary assumptions, resource source and distinguishing test. Preserve all original authors and related claims.

- [ ] Separate equivalent assertions, related components, alternate implementations and conflicting mechanisms.
- [ ] Keep grouping revision-bound and invalidate it after material changes.
- [ ] Do not count repeated components as independent solution families solely to reach a requested number.
- [ ] Allow fewer supported families with clearly labelled unreviewed alternatives.

Acceptance: two descriptions of the same angular-filter/cavity mechanism cannot silently count as independent evidence or two independently established approaches. Generic software variants receive the same treatment.

## H. Evaluate without manufacturing a benchmark score

- [ ] Curate the ten N4 targets with exact source passages, assumptions and primary support for expected judgments.
- [ ] Add matched valid controls and disagreements requiring an unknown result.
- [ ] Add non-physics tasks covering the same failure mechanisms.
- [ ] Freeze held-out cases and independent human labels before comparing model configurations.
- [ ] Report defect recall, false rejection, source fidelity, coverage and synthesis leakage with denominators and unknowns.
- [ ] Evaluate live outputs separately from deterministic DTO/routing tests.
- [ ] Treat proposed 8/10, 9/10 and 10/10 thresholds as targets until measured; never report them from canned outputs or keyword matching.

The existing 1.02 independent-quality gates remain open. Promoting 1.02 to the default workflow means using the implemented scrutiny machinery; it does not assert that free models now reliably catch all scientific errors.

## Execution and budget constraints

Start by integrating audit records into the current `2N + 4` model-call schedule and local pure-policy stages. Add calls only when a concrete coverage need and the user's existing limits permit them. Preserve daily accounting, bounded recovery, named model attribution, $0 additional-payment authorization and $0 GPU spending. Do not introduce thirteen extra model calls merely because the review lists thirteen logical stages.
