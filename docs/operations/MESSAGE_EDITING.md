# Edit and regenerate a council request

Every sent user message has an Edit action in the conversation. Edit the saved text and choose **Edit & regenerate** to request a fresh council cycle in the same chat. The initial question and later follow-ups can both be edited, including requests whose model response failed. Submitting unchanged text also permits an explicit fresh run.

The editor has its own draft. Opening it, typing, cancelling or pressing Escape does not call a model or replace the main composer's unsent text. Submissions that fail validation keep the edit open. While the council is running, the editor can request **Pause after this response**. Regeneration waits until the active request and worker have finished; it never cancels a healthy in-flight model call to apply an edit.

## Context and history

- Original messages, answers, receipts and publications are immutable history. The UI labels messages outside the selected revision **Earlier version** and the replacement **Edited request**.
- Editing reconstructs the context that preceded the selected message. Later replies from that old version are excluded from future prompts. A corrected opening replaces the root question; a corrected follow-up retains preceding public context and the original root question.
- Every new message records its revision path. Editing an already edited message, or returning to an older historical message, reconstructs that message's own preceding context. Reloading does not lose this relationship.
- The frozen original protocol prompt and its hash remain intact. The new review contract contains the corrected question. Existing scoped/unified reviews start a new cycle; earlier legacy/discussion councils adopt the current council workflow for the new cycle only.
- The normal full council stages run again: independent answers, extraction, scrutiny, author revisions, recheck and synthesis. Existing provider availability, source, context, thinking and budget policies still apply.
- Pending retries and queued steering belonging to the replaced request are superseded. Old response attempts are not replayed. The source library remains shared and its provenance is preserved.

## Charges

Regeneration is an explicit new request. Prior settled charges and unknown-charge reservations remain counted, including charges on replaced answers. Only unused held finishing allowances are released. No refund, charge reconciliation or automatic retry is implied. The editor discloses any earlier unknown charge before its submission authorizes a new attempt. The aggregate existing-credit spending cap remains enforced.

## API

`POST /api/chats/{chat_id}/messages/{message_id}/regenerate`

Requires the ordinary director session, an `Idempotency-Key`, and:

```json
{
  "text": "The corrected request",
  "expected_revision": 12,
  "authorize_retry_with_unknown_charge": true
}
```

The revision must match the current chat. The message must be a user message belonging to that chat. Active requests reject the mutation before any history or job changes. Successful submission appends a replacement, saves its context path and enqueues exactly one new cycle. A repeated identical idempotency key returns the saved result without appending or enqueueing again. Ordinary message length limits apply.

Implementation: `council_message_edits.py` manages revision paths, `council_chat.py` filters active prompt messages while projecting the full labelled history, and the existing review cycle controller executes the new run. The `chat.message_revised` audit event links the old and new message IDs. The full transcript and accounting remain available.

Validation uses isolated scripted councils and synthetic provider HTTP/SSE responses. No paid requests are required to test this feature.
