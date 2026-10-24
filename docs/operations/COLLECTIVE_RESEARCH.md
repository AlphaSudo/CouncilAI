# Collective web research

The council cooperates on evidence discovery before writing independent answers. Each selected model contributes a public search direction, discovers sources through Tavily, and adds those sources to the same conversation library. After the research boundary closes, every opening answer receives the same frozen source inventory and selected readable passages. No opening answers are shared during discovery.

## The user flow

1. Submit a question with **Search On**. This is the default for new configured Token Factory and direct-provider councils.
2. **Researching together** shows each model and its complementary angle: foundations, approaches, challenges, and optionally applications for a fourth participant.
3. Each model chooses one short query. Query planning runs with at most three concurrent requests. Model query text is research intent, not a public answer or private reasoning transcript. If a planner cannot return a usable query, an explicitly labelled assigned-angle query is used instead. No automatic model retry is made.
4. Tavily searches run concurrently. Results are merged by canonical URL with all contributing models retained. Round-robin selection prevents the first researcher from consuming every page slot. The shared pool contains all discoveries, with at most six unique URLs selected for batch extraction.
5. Tavily Extract Basic saves page text in the library. Duplicate URLs are extracted once, and recent identical searches or extraction batches can reuse saved results. Partial extraction leaves clearly labelled search excerpts; a missing page is never presented as a full read.
6. The common evidence snapshot is frozen after researchers and extraction finish. Each model's independent answer receives this snapshot and an identical selection of public source passages, including supplied documents. Shared papers carry contributor attribution. The existing review and discussion stages follow normally, with per-reply search still available.

The research module becomes a compact **Shared research** disclosure after completion. Expand it to inspect each query, whether it was model chosen or a fallback, the sources each model found, saved-page status and shared contributors. Page buttons open the ordinary Sources inspector. Compare also exposes the shared research collection.

## Boundaries and resilience

- Research plans use separate durable contributions and attempt purposes. They are not inserted into the answer transcript or live answer stream.
- Each cohort is scoped to a chat and review cycle. Follow-ups and edited requests start new cohorts; earlier queries, sources, answers, charges and publications remain available as history.
- A query-planning attempt is never automatically replayed after an unknown outcome or restart. Its reservation remains counted. Failed planning uses the assigned research angle; it never pretends that a model generated the fallback query.
- Searches and extraction use the existing broker, artifact hashes, query cache, bounded public destination checks and monthly free-credit admission. Before model planning starts, known free allowance must be sufficient for the parallel discovery batch.
- Tavily Extract requests are Basic, Markdown, and limited to six public URLs. Six URLs reserve two free credits conservatively; five or fewer reserve one. Per-URL failures are saved even when the HTTP request succeeds. Original provider responses are retained. Extracted text is labelled provider extraction, with original-page completeness unverified.
- The research barrier can finish with limited coverage. Planning, search, quota and extraction failures are disclosed without replacing or interrupting model answers. Earlier unknown model charges remain included in the total budget.
- Pause preserves completed plans and searches. Resume reuses them. If research is switched off while paused, remaining discovery is skipped and the already saved corpus becomes the common opening snapshot. Later opening answers retain the same frozen pool even if new web research is switched off between replies.
- The packet includes bounded passages, not a claim that every full document was read. Full saved documents and omitted passages stay in the shared library. Citation admission still requires an actual exposed passage. Retrieval and agreement are not experimental verification.

## Request and cost accounting

A usual three-model cycle uses three short model planning requests plus ten ordinary council replies. Those planning requests consume three slots from the existing five-request research allowance. They do not raise the twenty-attempt ceiling, the $24 aggregate existing-credit cap, or authorize additional payment. A four-member cycle uses four planning slots. The remaining optional model-tool continuations must fit the existing allowance.

Planning requests have a separate 8,192-token combined completion envelope and a 1,024-token advisory reasoning target because their deliverable is one query. These controls do not cap the subsequent independent answers. Provider reasoning controls remain advisory where the endpoint does not enforce them. Planning receipts, actual token usage, known costs and unknown reservations all contribute to conversation totals.

The implementation parallels the research work only. Opening answers still use the existing sequential model admission; no unapproved parallel-answer mode or peer-answer reveal was introduced.

## Hackathon demonstration

The core demonstration is cooperative acquisition, followed by independent judgment: submit a solar-conversion question, watch three research angles gather different primary sources, inspect a paper found by multiple models, open its saved page, then compare the independently written answers using the pooled evidence. The same workflow applies to software design, memory bandwidth, policy analysis or other subjects; no solar-specific assumptions are hardcoded.

Useful evidence for a presentation:

- The actual model-chosen queries and overlapping source attribution.
- Simultaneous planning/search timing, deduplicated URLs, extraction receipts and a common snapshot ID.
- Which full pages were saved, which items remain snippets, and which passages each answer actually saw.
- Search/extraction reuse and measured token/cost totals, without assuming provider prompt-cache hits.
- A failed researcher or unavailable page that leaves an honest partial research pool and a working answer flow.

This integration is intended for the [Best Use of Tavily prize](https://nebiusglobalaihackathon.devpost.com/). API references: [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search) and [Tavily Extract](https://docs.tavily.com/documentation/api-reference/endpoint/extract).

## Validation

`docs/validation/collective-research-live.json` records a real Tavily run: three concurrent searches, eight unique URLs, six extracted pages and eight readable pooled passages. Only model query planning was simulated; there were no paid model calls. Five conservative free-credit units were reserved, with pay-as-you-go usage reported as zero. Immediate usage telemetry can lag.

Provider HTTP/SSE tests separately execute all model adapter paths, check actual three-way planning and search concurrency, enforce the source barrier before the first opening, verify identical opening snapshots, preserve supplied sources, exercise unknown planning charges, pause/resume, search-off recovery, partial extraction and same-chat follow-ups. Browser checks cover progress, contributor attribution, page access, partial coverage and narrow layouts.

The advanced request field `collective_research: false` permits a per-reply-only integration test or API consumer. The ordinary UI uses the collective workflow when search is enabled; no version chooser is exposed.
