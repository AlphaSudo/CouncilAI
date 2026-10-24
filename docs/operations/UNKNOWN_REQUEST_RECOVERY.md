# Recover an interrupted council request

The reported second-cycle failure in `chat_109c5a772e674cb2` was a transport interruption, not a model refusal. Nemotron Super's call `call_8b4d0634c1ca478e` ended with `RemoteProtocolError` after 37.815 seconds. No HTTP response, stream event or public answer text was recorded. Its configured inactivity timeout was 90 seconds, so this was not that timeout expiring. The measured request context was 11,230 tokens within the unchanged 262,144-token council window.

The application conservatively retained a maximum reservation of $0.246692. That is not a confirmed provider charge. No receipt can establish that the provider did no work, so the reservation cannot simply be erased or the request replayed automatically.

The controller previously treated this boundary as a completed council and appended an empty local synthesis. It now pauses with `pending_request_recovery`, preserving the failed logical turn. Loading a chat, restarting the executor or viewing its receipts dispatches no retry. After acknowledging that the earlier possible charge remains counted, the director can choose:

- **Retry response:** make a new physical request for that same turn. Earlier successful replies are not repeated. The previous call and unknown reservation remain unchanged. The existing attempt and $24 aggregate-credit boundaries still apply.
- **Continue without the failed model:** explicitly exclude its unfinished opening and reassign its review roles among the remaining selected models. Its absence is disclosed and never treated as agreement. The unknown reservation stays counted.

A successful saved response clears the pending recovery. Stop clears it without releasing an unknown charge; a new cycle does not inherit it. Remote protocol failures now distinguish an interruption before a response from one during a response, instead of displaying only a generic unknown-outcome message.

Startup locally reopens only the earlier empty-completion bug: the chat must be current-profile, completed due to a provider boundary, unaccepted, not explicitly finished, have no current-cycle model replies or active jobs, and have an unknown latest scheduled call. It restores a paused state and retry target, keeping the old notice, question, all replies, receipts and financial rows intact. It appends an audit event and does not enqueue work. This repair is idempotent and respects a caller's chat scope.

Verification uses synthetic HTTP/SSE and an isolated browser QA server. Tests cover first and later interrupted openings, acknowledgement before retry, preservation of earlier answers and reservations, explicit exclusion, local recovery idempotence, no automatic dispatch, and the existing review/stream/copy interface. These tests do not claim the hosted provider can never disconnect.
