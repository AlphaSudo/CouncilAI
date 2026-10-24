# Compare and responsive conversation scrolling

Compare is a presentation of an existing council, available beside Simple/Explain in a chat header. It does not create a council, rerun a step, change a review protocol or dispatch a provider request. Simple/Explain remain available in the conversation.

## Reading the flow

- The opening question stays above the board in a bounded scrollable area. **Expand question** opens its full text, with text-size and copy controls.
- Model columns line up by chronological stage, cycle and discussion round. The usual three seats appear adjacent; two or four selected seats use the same layout. Narrow screens pan horizontally inside the board.
- Each response stays in its original author's seat, with the actual author/model on the reply. Earlier replies retain their author when a seat changes models. Unknown authors and conversation-wide notes remain visible as full-width rows.
- Model response boxes are bounded so two stage rows fit a sufficiently tall desktop window; the board scrolls down to subsequent stages. Each box can scroll through its response independently. The final synthesis spans the board.
- **Inspect** opens one response in an expanded reader with text zoom, exact source Markdown copying, saved usage and timing details. Escape closes the reader first; **Conversation** or a second Escape returns to the chat with its draft and original reading position intact.
- Public opening/final-answer previews update from the existing snapshots. An inspected preview remains open when its saved response replaces it, preserving text zoom. Private reasoning is not exposed. Recorded skipped stages and missing replies are labelled; the UI does not manufacture a response or agreement.
- Saved source citations use the existing Sources inspector, returning from the Compare surface to make it accessible.

## Scrolling changes

Elapsed and retry countdown clocks now own their state locally. A one-second clock tick no longer rerenders the entire conversation. Saved Markdown/KaTeX bodies are memoized by their text and source action; the source action is stable across snapshots. Incoming progress bursts coalesce over 250 ms without indefinitely postponing a refresh. The two-second read-only polling fallback is retained. Automatic transcript scrolling uses an immediate position update instead of an overlapping smooth-scroll animation; explicit navigation may still request smooth movement.

The changes do not alter provider latency, request limits, stored message text, exports, billing, the $24 aggregate cap, or backend execution. They do not truncate or summarize answers. Readers who scroll away from the bottom are not pulled down by incoming messages.

## Verification

`apps/web/e2e/council-compare.spec.ts` covers aligned columns, the whole saved flow, expansion/zoom/copy, nested Escape/focus recovery, unchanged drafts, zero inference requests for view changes, stream-to-receipt handoff, per-cell scroll preservation, actual replacement authors, multiple cycles, extra seats and narrow-screen panning. `council-scrolling.spec.ts` checks history position during progress polling, new answer delivery and final status recovery.

The same offline fixture was measured before and after: 18 saved replies containing 216 math paragraphs, repeated full snapshots every two seconds and a one-second request clock, observed for 6.6 seconds after initial render. In this local browser run, long tasks fell from 11 (2,475 ms total, 310 ms maximum) to 0. The longest animation-frame interval fell from approximately 300 ms to 18 ms. These are synthetic interface measurements, not model-generation or universal device performance claims. Both measurements made zero provider calls. Raw results are in `docs/validation/council-compare/scroll-before.json` and `scroll-after.json`.

Build with `npm run build --prefix apps/web`. Run the focused browser tests from `apps/web` with `npx playwright test e2e/council-compare.spec.ts e2e/council-scrolling.spec.ts`. The QA server uses an isolated temporary database and synthetic models. Existing conversation, source navigation, copy, Simple/Explain, home layout, answer delivery and timing tests cover the affected surrounding interface.

Acceptance: 25 distinct browser cases passed across the surrounding and focused runs. The final nine-case run passed all five Compare cases and repeated the four existing copy cases after fixing modal clipboard fallbacks. Production build and local health check passed. The validation register and count method are in `docs/validation/council-compare/validation.json`.
