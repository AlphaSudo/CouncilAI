# Council review assessment for version 1.02

Date: October 19, 2026. Original status: **planning assessment**, retained as the design record.

Implementation amendment: the [1.02 release](../releases/1.02.md) now records the implemented software, conservative live fallbacks, provider failures and pending independent quality. Planning-stage statements below describe the assessment when written; they are not current acceptance evidence.

The proposed work is in [the 1.02 implementation plan](../../plans/08_IMPLEMENTATION_PLAN_1.02.md). This assessment uses the supplied Arabic review and reads the current repository and saved integration conversation. It does not adopt the reviewer's numerical scores as measurements.

## Main judgment

The review identifies a real failure mode: a council can preserve uncertainty correctly while failing to make a useful, scoped decision. The remedy is to separate **objection resolution, evidential support, remaining risk, and decision suitability**. Making the critic more permissive by itself would exchange excessive rejection for unsupported approval.

Keep the existing architecture, independent openings, author repairs, provenance, durable execution and server publication policy. Improve the content contracts and the policy's distinctions inside the current bounded schedule. Evidence and test audits are functions within existing calls, rather than additional mandatory model seats.

This is a generic reasoning and decision increment. Backup workflows supply a regression example; they do not become the council's default domain.

## Sources and limits of this assessment

| Source | What it establishes |
| --- | --- |
| User attachment, `Pasted text.txt`, supplied October 19. | The reviewer's suggestions and observations, translated and evaluated here. Original byte SHA-256: `b81391325c89eff96b100f32095b0ec2977b4222dcbc616755d67ec8757bf3e5`. |
| `src/zerowall/contracts.py` and `council_review.py`. | Existing extraction, scrutiny, repair, recheck and synthesis DTOs, prompts, admission rules and call schedule. |
| `src/zerowall/review_policy.py`. | Current deterministic publication rules; model opinions do not become external verification. |
| `src/zerowall/review_exports.py`, `quality.py`, `apps/web/src/ReviewPanel.tsx`. | Current replay, evaluation and inspection behavior that the increment must preserve. |
| Saved conversation `chat_667561af9fa14d34`, read without mutation. | The actual openings, eight extracted claims, eight recheck assessments and two saved syntheses in the local integration run. |
| [1.01 release evidence](../releases/1.01.md) and [integration summary](../validation/reviewed-council-main-app.json). | Software acceptance and integration history. Independent answer-quality evidence remains pending. |

The attachment refers to `n3.txt`; that underlying file was not supplied with this request. Its quoted observations were checked against the available saved conversation where possible. This is a diagnosis of that run and the current implementation, not an independent benchmark of all council answers. No provider request, source retrieval, experiment or hardware measurement was performed for this assessment.

## Findings checked against the repository

1. **All eight rechecks really returned `issue_remains`.** The latest synthesis led with an unresolved comparison. Several reasons asked for assurance that discipline, scripts or checks would always work, even after conditions were added. This supports better scope comparison and risk classification. It does not show that all eight repairs were sound.
2. **The code is not strictly binary.** Recheck already permits `rebutted_as_assessment`, `narrowed`, `withdrawn` and `no_issue_as_assessed`. Policy recognizes two of those as answers to a challenge, but does not treat `narrowed` as a potentially completed scoped repair. Conditional recommendations are already allowed. The problem spans prompts, coarse DTOs, policy and synthesis behavior.
3. **Extraction currently selects source passages.** The server preserves exact offsets and hashes, but the admitted claim text is the whole selected quote. A passage can contain several assertions or JSON/Markdown scaffolding. Exact provenance does not establish atomicity or fidelity of the extracted meaning.
4. **The timing anecdote is present.** Opening message `message_bde2f0f0138f403a` says its personal tests took about 30 seconds for a manual copy, 5 seconds for a snapshot and 3 seconds for restoration. No linked execution artifact establishes those measurements. Its proposed 80% timing threshold is also present. These are unsupported model-reported results, not evidence of an actual council experiment. The planning assessment does not establish deliberate fabrication.
5. **The omission was disclosed but insufficiently actionable.** Extraction coverage says observed results and other details were omitted from some openings. Disclosure is useful; it does not substitute for a prominent provenance warning about a claimed experiment. A check must inspect the original openings, rather than only admitted claims.
6. **The sample contains similar claims, not proven duplicates.** Differences about setup, versioning, restore behavior, reliability and maintenance can matter. A semantic grouping proposal is useful; deleting or merging records across authors would lose attribution and potentially hide disagreement.
7. **Some revised assertions still overreach.** Hash verification alone does not establish a general reliability advantage, and a scheduled script does not literally eliminate forgetfulness or every failure. Scope-sensitive recheck must still identify these defects. The reviewer's suggested final answer is a useful style example, not an automatically correct reference answer.
8. **A claim budget and generic evaluation harness already exist.** The cap is four claims per author and sixteen per cycle. Eighteen developer-authored protocol cases and an offline quality summarizer exist. Independent human semantic evaluation has not yet established that 1.01 improves answer quality. Version 1.02 should extend these components.

## Decisions on the suggestions

| ID | Suggestion | Decision | Adaptation and reason |
| --- | --- | --- | --- |
| D102-01 | Preserve independent answers and the present architecture. | Keep. | Opening isolation, actual identities, local queue, SQLite, artifacts and budgets remain invariants. |
| D102-02 | Distinguish resolved, partly resolved, conditional, unsupported and false. | Accept the distinction; redesign the schema. | Store resolution of a particular objection separately from support for a claim. Unsupported is an evidence condition; conditional is a scope condition; neither is a synonym for resolved. |
| D102-03 | Store residual risk separately. | Accept with a guard. | An ordinary risk alone need not keep a narrower claim unresolved. A material contradiction, unfulfilled hard requirement or missing required evidence cannot be erased by calling it residual risk. |
| D102-04 | Compare the repair with the exact original objection. | Accept. | Recheck must cite original and revised text, identify the disputed part, explain whether the failure mechanism still applies, and distinguish a newly discovered issue. |
| D102-05 | Use a Recheck Adjudicator. | Adapt. | It is a scope-sensitive model assessor. Its output cannot grant truth, execution authority, external support or permission to spend. |
| D102-06 | Split every compound claim into atomic assertions. | Accept as a bounded extraction goal. | Keep exact source spans separately from a short normalized assertion. Require a coherent testable proposition and preserve its qualifiers. A one-verb or one-sentence rule alone cannot establish atomicity. |
| D102-07 | Perform semantic deduplication. | Adapt to reversible grouping. | Group only claims assessed as equivalent in meaning and scope; retain every author, claim ID, revision, repair and dissent. Related or conflicting claims remain distinguishable. Group membership grants no evidence or consensus weight. |
| D102-08 | Classify claims by type. | Accept as descriptive routing. | Use a primary reasoning kind plus overlapping properties such as quantitative, causal, comparative and quantifier. Type can tailor questions and evidence needs, but cannot automatically certify a definition, deduction or existential example. |
| D102-09 | Catch claimed observed results without artifacts. | Accept; high priority. | Audit full openings and later repaired assertions for model-reported measurements. Link the exact passage, identify provenance, and mark missing support. Numbers from supplied evidence, hypothetical examples and deterministic calculations need distinct treatment. |
| D102-10 | Add an Evidence Provenance Auditor. | Accept the function. | Extend extraction/scrutiny and local admission checks. Existing evidence records already retain origins and hashes. Add claimed-result alerts and scoped links; do not add a mandatory new API call. |
| D102-11 | Add a Test Validity Auditor. | Accept the function. | Scrutiny proposes a discriminating test; recheck assesses alignment, falsifiability, baseline fairness, threshold basis, reproducibility and limitations. A reviewed test remains an unexecuted proposal. |
| D102-12 | Apply backup manifest, hash, metadata and restore checks. | Keep as one regression fixture. | Generalize the principle: evidence of presence need not establish completeness, and a proxy metric need not establish the requested outcome. Do not install backup commands or execute suggested shell code. |
| D102-13 | Use the proposed seven-level epistemic ladder. | Reject as one authoritative scale; retain useful distinctions. | The categories overlap. Conditional, partial and empirical describe different axes. Model reasoning cannot grant the labels established, empirically supported or falsified by itself. Use attributed, scoped evidence labels. |
| D102-14 | Give a practical recommendation despite ordinary uncertainty. | Accept with limits. | Lead with an appropriate recommendation, conditions and what would change it. A meaningful unresolved dependency can require a limited answer or no decision. Never force a winning proposal. |
| D102-15 | Distinguish a new objection from an original one. | Accept. | Store a separately linked concern with its review state. Do not rewrite the original resolution criterion or launch unlimited repair rounds. |
| D102-16 | Implement thirteen separate stages. | Reject as mandatory execution. | The listed checks are useful functions. Fit them into extraction, scrutiny, repair, recheck, local policy and synthesis; retain `2N + 4` planned calls. |
| D102-17 | Add weighted scores by task. | Defer. | The director may supply decision criteria. Uncalibrated numerical weights or confidence must not select a winner or override a failed constraint. |
| D102-18 | Add domain auditor plugins. | Defer. | Keep generic applicability fields now. Physics, medical, memory-wall or backup-specific profiles require separately scoped sources, tools and evaluation. |
| D102-19 | Add materiality thresholds and a claim budget. | Extend existing limits now. | Prioritize decision-changing assertions and claimed measurements. Preserve four-per-author/sixteen-per-cycle ceilings and report omitted material. Avoid an uncalibrated numeric materiality score. |
| D102-20 | Adopt the reviewer's overall and component scores. | Decline as acceptance evidence. | No rubric, sample design or calibrated scoring procedure was supplied. Preserve the qualitative diagnosis and test it. |

## Additional engineering work required

- **Protocol and replay versioning.** New interpretation must not rewrite 1.01 publications or change their reproduced decision hashes. Pin legacy policy and dispatch explicitly by contract version.
- **No evidence inheritance through a group.** Similar wording, a majority of authors or an assessed equivalence cannot transfer support, remove a blocker or satisfy another author's repair obligation.
- **No risk laundering.** Keep hard-constraint checks, conflicting assessed evidence, stale dependencies and required evidence visible even when a model proposes closing an objection.
- **Whole-source provenance checks.** A material anecdote cannot escape scrutiny merely because extraction omitted it to fit the claim budget. Automated detection remains fallible and must report its coverage limits.
- **Bounded token feasibility.** Added fields must fit actual response limits. Prototype compact DTOs at the maximum advertised claim count before expanding prompts; do not buy capacity with hidden retries or extra reviewers.
- **Balanced evaluation.** Test both unnecessary rejection and false closure. Measure retention of valid scoped proposals, missed defects, observation attribution, direct usefulness and final faithfulness. More resolved labels are not a success metric on their own.

## Implementation boundary

Version 1.02 needs no new account, credential, paid service, GPU or database. Preserve the four selected direct providers, disabled OpenRouter default, Token Factory billing lock, unknown invoice-cost reporting, local attempt caps and the $0 additional-payment rule.

This turn creates planning documents only. Software changes, live integration and independent quality evaluation remain future checklist items in the linked plan.
