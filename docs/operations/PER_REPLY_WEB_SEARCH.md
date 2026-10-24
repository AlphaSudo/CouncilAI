# Web search before council replies

The current UI adds [collective research](COLLECTIVE_RESEARCH.md) before the opening answers: selected models plan complementary queries concurrently, search in parallel and save pooled pages through Tavily Extract. The per-reply mechanism described here remains the search layer for later discussion stages, and an advanced API option for isolated use. The three-model full cycle now normally includes three short planning calls from the existing five-call research allowance.

New Token Factory and direct-provider councils default to search **On** when Tavily is configured. **Search On / Off** is visible beside the thinking, context and send controls in the main composer. No Customize or Sources dialog is required. The optional public topic in Customize can override automatic query construction.

The earlier integration often performed no searches: search defaulted to off, the neutral search skipped blank topics, and raw Token Factory openings intentionally offered no model tool loop. The new `per-reply-search/1` execution policy runs the broker before generation. It does not spend a second model request asking whether to search.

## Execution

1. Before each ordinary model reply, derive a short query from the public question or optional topic. Add a stage focus: overview, definitions, challenges, alternatives, verification or final comparison. Queries are limited to 400 characters. The entire transcript, attachments and reasoning are not uploaded as queries. Explicitly turning search on authorizes this query construction.
2. Run the existing bounded Tavily Basic broker. It checks the free allowance, preserves search credit reservations and refuses paid provider-native search or fallback. Recent identical queries reuse the saved result. Opening models share the same neutral query and frozen source snapshot; peer answers are never included in opening search queries.
3. Save snippets in the shared source library, prioritize their passages in the evidence packet, and create the normal source read receipts. Search snippets retain that label; they are not full-document reads or verification.
4. Add a system instruction to use relevant supplied passages, cite real source references, request additional bounded research if necessary, and disclose missing evidence. Every model transport receives this instruction, including raw Token Factory openings. Existing reasoning controls remain intact.
5. Save a per-reply search receipt and attach actual search status to the model attempt and public reply. **Web searched**, **Cached search**, and **Web search unavailable** are distinct. Explain and expanded readers show the actual query and limitation; Compare also shows search status.

Search failures, empty results and exhausted search allowances do not discard or stop a model answer. The prompt discloses the limitation and the existing supplied sources remain usable. A failed or unknown identical external action is never automatically repeated. Explicit model-output recovery reuses its saved context without replaying prior tools. A frozen explanation or resynthesis does not silently claim a new evidence check.

## Toggle behavior

Turning the switch during generation stores a preference for the next model request. The in-flight response keeps its original research lease and is not cancelled or invalidated. The setting applies before the next turn and persists into subsequent questions and edited requests. Turning search off prevents new external searches; already saved source passages remain available. Merely viewing or switching inspection modes dispatches no search or model request.

Historical councils retain their original execution semantics until search is explicitly enabled with the new switch. Their saved replies and bills are not rewritten. Explicitly disabled new councils remain off across subsequent requests. The $24 aggregate existing-credit limit and $0 additional-payment authorization remain unchanged.

## Efficiency and limits

The usual three-model full review has ten model replies. The automatic broker makes six distinct phase queries; the other four replies reuse recent identical results. No additional model turns are introduced by automatic search. Models retain at most the existing five bounded optional tool continuations when admitted. Per-window search credit admission scales to the selected council size, at most twenty; the existing local monthly ceiling and verified provider free allowance still apply.

The live check in `docs/validation/per-reply-search-live.json` used the actual configured Tavily key, returned three search results, saved three readable passages, and verified assembly of the search instruction and evidence packet. It made no paid model inference calls. Provider usage telemetry can lag; the immediate before/after counter is not proof that an external search cost zero credits. The broker retains a one-credit dispatch reservation.

Full model paths are separately exercised with synthetic provider HTTP/SSE replies: every seat and review stage, all transport families, caching, failures, on/off switching during generation, repeated requests, and the existing edit and unknown-charge recovery paths. These tests establish integration behavior; they do not claim answer-quality improvement.

Provider references: [Tavily Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search) and [usage endpoint](https://docs.tavily.com/documentation/api-reference/endpoint/usage).
