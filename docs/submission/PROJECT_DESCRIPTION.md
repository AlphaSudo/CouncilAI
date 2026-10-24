# ZeroWall — submission draft

## Tagline

Research together. Answer independently. Reach a decision you can inspect.

## The problem

Engineers comparing unfamiliar approaches need more than a plausible answer. They need assumptions, competing explanations, supporting sources and what changes when a requirement changes. Repeating a question across model tabs makes comparison slow and loses the trail between evidence and recommendations.

## What ZeroWall does

ZeroWall is a human-directed council for engineering and research decisions. Ask one question; selected models first contribute complementary web-search directions. Tavily searches run concurrently, duplicate URLs are merged, and Tavily Extract saves readable content from selected pages into a shared conversation library. Every independent opening receives the same frozen source inventory and selected passages, without seeing peer opening answers.

The council maps claims, raises challenges, records author responses and revisions, performs scoped checks, and synthesizes an answer. Follow-up questions and message editing stay in the same conversation. Simple presents a calm reading experience; Explain exposes execution details. Compare places model perspectives alongside each other, with complete-response inspection and copy controls.

Public answers are preserved before structured review. Recoverable annotation problems produce limitations rather than erasing replies. Search excerpts and extracted pages remain distinguishable; neither retrieval nor agreement is presented as experimental validation.

## Implementation and platform use

React/TypeScript is served by FastAPI. Local mode uses SQLite; the opt-in Vercel/Supabase path uses Postgres, private Storage and a separate worker Daemon. One coordinated executor owns dispatch. Actual cloud acceptance is still pending. The current default council uses:

- **`nvidia/Nemotron-3.5-Super-VL`**, lead, through **Nebius Token Factory**.
- **`reflection/beam`**, through Nebius Token Factory.
- **`deepseek-ai/DeepSeek-V4-Flash-0731`**, through Nebius Token Factory.

Token Factory supplies hosted inference; a separate GPU instance is not required. Local records include completed calls for all three current models, including NVIDIA Nemotron. Before submission, select and scrub the precise receipts supporting the recorded demo; completed-call counts alone do not establish a complete council or answer quality.

Tavily supplies cooperative search and extraction. Queries and model contributions are retained; duplicate URLs avoid repeated extraction, and sources are reused throughout the conversation. Model and research calls are accounted for. Provider-reported token/cache categories appear where available, with unknown values left explicit. Current local authorization uses existing credit, a $24 aggregate ceiling, and $0 additional personal payment. This is not a universal visitor quota or a provider billing-control guarantee.

## Track and award fit

**Best Apps and Agents** is the primary track: a decision-support application powered by Nemotron. The additional award target is **Best Use of Tavily**: cooperative evidence acquisition followed by independent judgment, with shared provenance and reuse.

## Evidence and limitations

Recent regression records cover provider selection, answer preservation, review recovery, comparison, collective research, thinking controls, context display and responsive layouts. These are software checks, not proof that councils consistently outperform a single model.

A separate genuine Tavily diagnostic recorded three concurrent searches, eight unique URLs and six extracted pages. Its model query planning was simulated and it made no paid model calls; identify that accurately if referenced. Use the actual end-to-end recorded council for the product demonstration.

Latency, reasoning behavior and reported usage vary. Thinking targets are advisory where endpoints lack enforcement. Timeouts can leave charges unknown; maximum reservations remain counted and unknown requests are not automatically replayed. The app is currently used locally. Opt-in hosted mode adds explicit access and persistent-service configuration, but remains single-director; public deployment and multi-user isolation are not claimed.

## Feedback based on development

Token Factory enabled distinct hosted models without operating a GPU server. Explicit model IDs and usage receipts made integration inspectable. Long reasoning-only responses and endpoints delaying an HTTP response complicated interactive latency and completion budgeting. Separate, consistently documented reasoning controls and uniform cache/usage reporting would make orchestration easier. This is integration feedback, not a provider benchmark ranking.

Tavily made the common research pool practical through parallel searches and batch extraction. Contributor attribution, deduplication before extraction, and distinguishing excerpts from saved pages made tool activity visible rather than an opaque search claim.

## Fill before publishing

- Public repository and recognized MIT license links.
- Working hosted application or downloadable test-build URL, with complete free testing instructions and an access plan through December 15, 2026.
- Public YouTube URL below three minutes, using genuine runtime footage.
- One actual decision or revised recommendation from the recorded run; no invented customer outcome or quality gain.
- Entrant/team information and confirmed development-period disclosure.

Publication, hosting, video upload and Devpost submission have not been performed by this document.
