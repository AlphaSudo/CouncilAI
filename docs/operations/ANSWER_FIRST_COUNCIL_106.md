# Answer-first Council operations

New councils use internal protocol `reviewed_v4`, policy `generic-publication-v4`, delivery descriptor `answer-delivery/1` and annotation descriptor `answer-first/1`. These identifiers do not appear as product choices. Historical v1/v2/v3 publications retain their recorded policies; an explicit new request can adopt the new engine while archiving the previous protocol and publication.

The provider still owns generation. The controller saves a redacted public message and its receipt reference in a committed transaction **before** interpreting review data. A separate transaction attempts annotations. Each independent annotation can be quarantined under its own savepoint; invalid source IDs, authors, dependencies, evidence and revisions acquire no authority. Complete original payloads remain inspectable in delivery/admission records and exports. A final Markdown answer has no required JSON envelope or publication whitelist.

## State contracts

| Dimension | Values and meaning |
| --- | --- |
| Generation | `not_requested`, `responding`, `complete`, `partial`, `unavailable`. Complete describes receipt of public output, not its truth. |
| Review | `pending`, `complete`, `incomplete`, `unavailable`. A completed assessment may still contain unresolved disagreements. |
| Stage progression | `success`, `partial`, `degraded`, `skipped` are terminal. `pending` requires local reconciliation before a new dispatch. |
| Support | Source-bound assertions, model assessments, retrieved passages, declared-input checks and human support assessments remain distinct. A public message alone remains unassessed. |

Additive records: `answer_intent`, `answer_delivery`, `public_stream`, `stage_result`, `review_warning`, `review_quarantine`, `review_check_note`, `chat_steering`, `finishing_reserve`. Their references include actual call/model, cycle, turn, context hash and receipt. JSON Schemas for stage results, warnings and selective scrutiny are exported in `contracts/`.

## Failure handling

Cosmetic variants normalize locally, retaining originals. Individual invalid annotations remain unlinked. In the current workflow, unusable extraction/scrutiny annotations no longer skip the public debate: the remaining planned critic, author-response and recheck turns continue in readable Markdown using the actual saved answers. No claim IDs, evidence, author revisions or formal closure are manufactured from this prose. The final answer uses the actual discussion and keeps formal review labelled incomplete. There is no extra formatting retry or added discussion round. This continuity state is scoped to the affected cycle and clears for the next healthy turn. Historical earlier-profile publications remain frozen with their original outcomes.

Unknown or stale references never count as source support. A claimed repair without an author revision stays unresolved. An unassessed family remains unreviewed. A critic can report an unsuccessful falsification attempt without manufacturing a defect or establishing truth. Minor findings stay as notes; substantive repair remains at most one normal turn per relevant author. Default review ends at the completed recheck boundary; obtaining new external evidence can be an explicit follow-up.

A genuine provider failure records partial or unavailable generation. Other public responses survive. A failed lead yields a clearly attributed local partial result, never a fabricated successful lead or unauthorized substitute. Funding/permission/integrity boundaries still prevent unsafe dispatch. Unknown charges remain counted; no ambiguous request is automatically replayed. Pause and Stop preserve their actual user intent.

## Streaming and restart

Public streaming flushes on bounded progress ticks, in chunks of at most 16,384 characters with monotonic sequence IDs. A suffix that could be part of a credential is withheld until safe redaction is possible. Private reasoning text never enters these records; activity and provider-reported counts remain separate.

The normal view includes only the active stream, with a bounded preview. Authorized clients can replay `/api/chats/{chat}/streams/{call}?after=0&limit=64`. Pages contain at most 64 chunks, a next cursor and a completion flag. Reconnect/read calls never dispatch inference.

At startup, completed matching receipts and pending public commits are reconciled locally. Exact intent/request/context/model/artifact/settlement checks prevent stale or duplicate reuse. Recovery is idempotent and cannot edit settled calls or financial rows. An ambiguous network attempt is not eligible for automatic receipt recovery.

## Conversation, context and spending

The shared context window remains **262,144 tokens**, with the existing provider-specific thinking controls. The 4K reasoning choice is advisory; exceeding it does not cancel a healthy response. Provider combined output limits remain real. Lossless context packing retains questions, obligations, dissent and source anchors; final-answer packing requests Markdown rather than encoded metadata as output.

Steering during generation is queued. All independent openings retain the same starting question/evidence; later notes become visible at a completed-turn/opening barrier. Completed answers remain immutable when a later cycle starts. Request windows retain the 20-physical-attempt ceiling, rather than applying a lifetime cap to the chat.

Before optional review, the selected lead's prices/output bounds, actual saved final packet and annotation-growth allowance reserve finishing credit. This is **not an input byte limit or a new conversation spending cap**. If the actual final admission needs a larger conservative envelope, it can expand transactionally within existing authority. Insufficient optional capacity routes to the affordable final, or to an honest local partial result when another request is impossible. The aggregate **$24 existing-credit cap and $0 additional-payment authority** remain unchanged. Holds are neither spent usage nor request attempts.

## Verification and limits

Run `python scripts/validate_answer_first_106.py` for an offline eight-cycle demonstration, including an injected extraction fault, duplicate submission, restart recovery and replayable exports. All model replies in that demonstration are explicitly synthetic. Human answer-quality tasks and scoring are frozen in `benchmark/answer_first_106_quality.json`; no human quality improvement has been established.

The release evidence is in `docs/validation/answer-first-1.06/`. The previous live bridge receipt is historical evidence, not a completed new-protocol council. Genuine new-protocol provider results are recorded separately when completed. No GPU, kernel, hardware-efficiency or guaranteed-latency claim is made.
