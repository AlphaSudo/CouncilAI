# Reflection Beam council integration

The user requested replacing GLM with `reflection/beam` on October 23, 2026. New Token Factory councils default to Super, Beam and DeepSeek, with Super still leading and Lightning optional. GLM is hidden from the new-model picker but its legacy configuration remains available for reading and testing historical receipts.

## Reasoning and completion space

Beam always reasons and supports named effort levels. Balanced requests `reasoning_effort=low` and the council's 4,000-token reasoning instruction. Quick keeps low effort with a 2K target; Deep requests medium effort with an 8K target; Maximum requests high effort with a 16K target. No undocumented numeric hard-cap field or thinking-off switch is sent. Sampling follows the published model card at temperature 0.7 and top-p 0.99.

The 4K instruction is advisory. Overruns remain observable and do not cause a client cancellation or rejection of a completed public answer. Production openings keep their available 262,144-token context/credit-sized completion room; review and recovery keep their 32,768-token combined ceiling. Reasoning and answer usage are displayed separately, while the provider's total completion limit still includes both.

## Saved chat and public context

The existing `chat_0bd9f187edcc4289` has an audited override for GLM's frozen seat. Its original participants, protocol hash, old messages, model attribution, financial reservations and calls remain intact. Future work assigned to that seat uses Beam and discloses which model it replaces. Replacements are refused during active or queued work, require the user-authorized mapping and verified target pricing, and do not enqueue inference. The original failed extraction remains stopped until explicit continuation.

Reflection's native continuation contract requires original reasoning alongside replayed assistant messages. The council deliberately stores public replies only. Therefore each Beam stage is a fresh self-contained request; saved public drafts and research exchanges are quoted as user-context evidence instead of replayed as incomplete assistant/tool turns. Hidden reasoning is not fabricated, stored or published. Public source IDs and text remain available across research and explicit recovery.

## Verification

The public catalogue and authenticated account catalogue both confirmed `reflection/beam`. Published text rates were $0.25/M uncached input, $0.05/M cached input and $1/M output. Tokenizer metadata is pinned to its model-repository revision and SHA-256; only tokenizer data was downloaded, with no model weights or GPU resource creation.

One explicitly bounded diagnostic used the same physics question with low effort, the 4K target and a 16,384-token combined ceiling. It completed normally in 45.57 seconds: 1,077 input tokens, 1,985 reasoning tokens and 2,429 visible-answer tokens. Conservative recorded cost was $0.004684, under its $0.03 mission limit and the unchanged global $24 cap. There was no retry or fallback. Answer text and receipts are in `docs/validation/reflection-beam-live.json`. This verifies one software-integration request; scientific quality and future latency/target compliance are not certified.

Sources: [Reflection reasoning contract](https://developers.reflection.ai/reasoning), [model card](https://huggingface.co/reflection/Beam-1.0-501B-A23B), [Nebius Beam cookbook](https://dev.nebius.com/cookbook/beam-reflection-token-factory), [live public catalogue](https://tokenfactory.nebius.com/api/public/models_info).
