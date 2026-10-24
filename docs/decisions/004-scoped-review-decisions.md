# Decision 004: Scoped review without automatic verification

Date: October 19, 2026. Implementation: 1.02 preview (`reviewed_v2`).

The development backup comparison closed no objections and missed an unsupported model-reported timing anecdote. Its original passages and publication decisions remain in `benchmark/review_v1_baseline.json`. This fixture has development provenance and is not independent semantic gold. Hash verification alone does not establish backup completeness or a general reliability advantage; several sample repairs therefore remain legitimately debatable.

Keep the legacy engine and policy in `council_review_v1.py` and `review_policy_v1.py`. Dispatch explicitly by frozen protocol/policy. Version 1.01 publications must reproduce their original hashes. Omitted protocol selection retains v1; v2 is an explicit choice for new reviewed chats. Cross-protocol cycles are not supported.

Version 2 stores objection resolution, evidence strength, assumptions, residual risk and decision suitability separately. A model can assess an objection as answered; it cannot create empirical support, withdraw another author's claim, certify truth or waive a spending/execution guard. A partial repair, material new issue, stale dependency or missing required external evidence stays visible. Human risk acceptance does not promote evidence.

An atomic assertion is a model interpretation with exact original source spans retained separately. Its qualifiers must remain attached. Semantic grouping is reversible and revision-bound; it does not merge authors, multiply evidence or confer consensus authority. Claim descriptors guide relevant questions rather than prove deductions or definitions.

Provenance checks inspect full openings and later author replies. Local cues are incomplete and can misclassify quoted or hypothetical text; model audit classifications remain fallible. Neither a trace-looking string nor supplied log becomes an approved tool execution. Partial source support does not certify the entire assertion: whole-claim coverage requires an explicit scoped human assessment, valid provenance and the other publication gates.

The initial v2 profile permits **two atomic claims per author, eight per four-model cycle**, rather than v1's four/sixteen. Splitting consumes that budget. The output ceiling remains 4,096 tokens, the required-context bound 90,000 bytes, and the schedule `2N + 4` plus three shared retry attempts. Density fixtures establish record/byte envelopes; actual tokenizer and reasoning quality must be checked with real responses. No byte-to-token equivalence is claimed.

The first live scrutiny request received Groq HTTP 413: its account reported an 8,000-token-per-minute request limit and an 8,253-token request. The original packet repeated openings, source units and quoted claim provenance. The projection now sends source units once for extraction, full openings once for scrutiny and compact current claims. Exact source spans remain in the durable ledger/export. The failed attempt and original payload remain saved; no paid upgrade or model substitution was used. This integration run includes development recovery and is excluded from held-out quality evaluation.

Visual thesis: retain the council's calm typographic workspace and restrained green accent. Content hierarchy: prompt and direct answer first, compact state labels next, source/evidence details in the existing inspector. Interactions: reuse the existing drawer reveal, expandable provenance/groups and focus restoration; add no ornamental motion or new dashboard. This applies the frontend skill's app guidance.

Actual-model compatibility and independent quality are separate gates. Eight held-out candidate task pairs and a rubric are frozen before live pilot collection. The offline scorer never dispatches inference or unlocks providers. Missing labels and zero denominators remain unknown. Preview remains opt-in while independent quality is pending or inconclusive.
