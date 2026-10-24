# Thinking levels and continued council conversations

## Thinking controls

Token Factory councils expose a Thinking selector beside Send inside the composer in both Simple and Explain views. The initial setting is Balanced, preserving the existing controls and approximate 4,000-token reasoning instruction. The approximate marker is deliberate: the instruction is advisory.

| Preset | Reasoning target | Super native setting | GLM / DeepSeek native effort | Lightning |
| --- | ---: | --- | --- | --- |
| Quick | 2,000 | Medium | Low | Thinking enabled |
| Balanced | 4,000 | Medium | Low | Thinking enabled |
| Deep | 8,000 | Enabled, without medium reduction | High | Thinking enabled |
| Maximum | 16,000 | Enabled, without medium reduction | Max | Thinking enabled |

Targets are system instructions, not hard provider token caps. They apply to reasoning only. Raw independent answers retain their open answer length within context and credit limits; the existing 32,768-token combined review completion allowance and stage output guidance remain unchanged. Actual reasoning usage is reported separately and may exceed the requested target.

Generation policy revision 9 adds the user's explicit GLM override: all presets keep GLM at low effort with a 1,000-token advisory instruction and top-level `thinking_token_budget=1000` request. The fixed GLM override is shown in Explain; the table continues to describe the general presets for other models. The tested hosted endpoint overshot the native parameter, so its enforcement remains unverified. The client never interrupts a response for exceeding 1K or 4K reasoning, and the reasoning request does not reduce the existing combined completion allowance.

[GLM's model card](https://huggingface.co/zai-org/GLM-5.3-Flash) documents `low`, `high` and `max`, with other values falling back to `max`, and recommends `clear_thinking=true` for chat. The application never sends a generic `medium` value to GLM. [DeepSeek's model card](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731) documents the same three effort values.

[Super's model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16) documents thinking on/off and a `medium_effort` flag. [Lightning's model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16) documents on/off without graded effort controls. Its thinking stays enabled across all presets; the selected target is the effort guidance. It remains optional in the model lineup.

Explain mode shows the model-specific mapping. Each call saves its thinking preset, target, effective controls, policy version and observed usage. Changing a preference never rewrites an existing call or interrupts one in flight. The change applies to requests that have not started. No provider request is made by changing the selector.

Explicit Answer now recovery retains its existing model-specific completion controls and reuses the saved public context. If the target changes, configuration replaces the exact generated reasoning instruction rather than accumulating conflicting targets. Thinking and compaction preference revisions are separate from logical conversation revisions, so changing them does not invalidate a queued, otherwise unchanged saved-answer recovery authorization.

## Continuing the same conversation

A completed reviewed council can accept another full request, a targeted challenge or an explanation in the same chat. Each full or targeted cycle receives a fresh bounded request window; the lifetime call count does not become a lifetime conversation limit. Explanations retain their one-call route and disclose that no new checks were performed.

The next review cycle receives a frozen checkpoint of the previous cycle's public answer, exact assertions, scopes, assumptions, dependency relationships, concerns and recheck assessments. The checkpoint identifies its source cycle, completeness and stale state, and has a content hash. Historical IDs and assessments are explicitly historical; they cannot substitute for current evidence or current-cycle authority.

New independent openings share that prior public checkpoint and earlier user instructions. They do not see other seats' current-cycle opening replies. Checkpoints do not recursively embed previous checkpoints. The complete original transcript and earlier publications remain saved.

The older ordinary Token Factory discussion path also continues beyond six rounds. Its execution context now retains complete baseline replies, public discussion and all director notes instead of the former 6,000-character excerpts, 16,000-character discussion window and last-two-note selection. The 262,144-token context check, existing-credit checks and lossless context compaction still govern actual requests.

## Pause, failure and restart handling

Active turns are tagged with their durable job ID. When that job fails after a user pause, its active marker is cleared without changing the paused state or enqueueing work. Restart recovery clears interrupted owned markers for paused jobs too. Completed replies remain saved, unknown charges stay counted, and network work is not replayed automatically.

The same-chat workflow still validates authors, claim revisions, mandatory coverage, dependencies and evidence links. Checkpoints do not weaken review admission or grant verification authority. Compaction does not delete required concerns to fit another turn.

## Conversation credit allowance

The aggregate application cap remains $24 of existing credit. A conversation also retains its own explicitly chosen allowance; completed, reserved and unknown amounts count toward it.

The collapsed Conversation allowance control shows the cap and available amount. Expanding it lets the director add a specific amount from existing credit. This is an explicit local allowance amendment, not an account top-up or an immediate charge. It preserves the original frozen brief, historical financial rows and unknown reservations. Repeated submission with the same idempotency key cannot add credit twice. The addition is refused if it exceeds remaining authority or the $24 cap.

An exhausted conversation allowance is now reported as such, even if aggregate credit remains. It can be extended in this conversation without creating a new chat. Increasing it does not automatically resume work or start inference.

## Verification and remaining limits

The offline tests exercise eight full review cycles in one Token Factory chat, repeated explanations and targeted challenges, a discussion continuing through eight rounds, exact preservation of older replies and notes, pause/failure/restart transitions, allowance exhaustion and unknown-charge retention, and preference changes while saved-answer recovery is queued. Model-specific controls are checked across all four configured models. The multi-cycle review is exported and verified offline.

Browser tests cover initial preset selection, updates without clearing the follow-up draft, Explain mappings, explicit allowance increases, mobile layout and the existing context ring. The public-fetch concurrency test now synchronizes two mock workers rather than assuming a 30 ms overlap under arbitrary machine load; it still requires exactly two concurrent fetches and durable results.

No paid live model probe was performed for this feature. Native control effectiveness, hosted latency, rate limits and answer quality still require observation during real use. Unique required context must fit the physical context window, and actual dispatch remains bounded by the conversation and aggregate credit allowances.

See [the validation record](../validation/thinking-and-multiturn.json), `tests/test_thinking_and_multiturn.py` and `apps/web/e2e/thinking-levels.spec.ts`.
