# Agent repository research for Council 1.05

Research date: October 19, 2026. Read-only inspection; no upstream installer, build, hook or agent was executed. Repositories are pinned to commits. A root licence does not automatically cover every optional dependency or hosted service.

## Survey

| Repository | Commit | Root licence | Decision for Council |
| --- | --- | --- | --- |
| [anomalyco/opencode](https://github.com/anomalyco/opencode) | `6bac3b9ad8a3` | [MIT](https://github.com/anomalyco/opencode/blob/6bac3b9ad8a3bed5ac01b8f6a3c30850a4d04685/LICENSE) | Adapt typed usage, provider-aware prompt layout and separate search/fetch adapters. Keep unknown values explicit. |
| [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) | `687f282e8625` | [MIT](https://github.com/deepseek-ai/deepseek-harness/blob/687f282e8625c6b8d11ff58211a90524be2e4317/LICENSE) | Adapt bounded retained-tool projections and recoverable compaction records; do not adopt its full plugin runtime. |
| [zai-org/ZCode](https://github.com/zai-org/ZCode) | `0a1fc56d279f` | [Apache-2.0](https://github.com/zai-org/ZCode/blob/0a1fc56d279fd1001f78387bd81aec1c26767411/LICENSE) | Adapt usage attribution and bounded fetch cache/egress separation; keep Council's local persistence. |
| [xai-org/grok-build](https://github.com/xai-org/grok-build) | `2bdd1d6a6369` | [Apache-2.0](https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/LICENSE) | Adapt per-prompt/session completeness and late-cost accounting; no Rust/TUI runtime dependency. |
| [MiniMax-AI/Mini-Agent](https://github.com/MiniMax-AI/Mini-Agent) | `d76a4f638968` | [MIT](https://github.com/MiniMax-AI/Mini-Agent/blob/d76a4f6389688cabda39c224a6cdfa274215d47c/LICENSE) | Adapt small typed tools and persistent notes. Reject universal tokenizer assumptions and unmetered summarization. |
| [earendil-works/pi](https://github.com/earendil-works/pi) | `0ed1b0431444` | [MIT](https://github.com/earendil-works/pi/blob/0ed1b0431444f1e9321c5cf3a9e0acd04da11f89/LICENSE) | Adapt explicit usage semantics, append-only session entries and steering-aware tool boundaries. |
| [can1357/oh-my-pi](https://github.com/can1357/oh-my-pi) | `53a0377db684` | [MIT](https://github.com/can1357/oh-my-pi/blob/53a0377db6845e0dae606146130766ec92d407fd/LICENSE) | Adapt bounded reads and search-provider normalization. Do not copy its large tool catalogue or public-engine fan-out. |
| [google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli) | `76e4d7c046c7` | [Apache-2.0](https://github.com/google-gemini/gemini-cli/blob/76e4d7c046c7dab5727787da378b9c06bf0948cf/LICENSE) | Inspect source attribution and caching boundaries. CLI login benefits do not establish entitlement for our API key. |
| [QwenLM/qwen-code](https://github.com/QwenLM/qwen-code) | `5dcf7c7cb162` | [Apache-2.0](https://github.com/QwenLM/qwen-code/blob/5dcf7c7cb162e825d95d531081f67ee60da3c0e1/LICENSE) | Adapt retained-result manifests and range reads. Replace soft concurrent-budget behavior with strict reservations. |
| [langchain-ai/deepagents](https://github.com/langchain-ai/deepagents) | `12f70f27cc2e` | [MIT](https://github.com/langchain-ai/deepagents/blob/12f70f27cc2e96ac715f4563e05b205be7adc275/LICENSE) | Adapt filesystem/backend and offload boundaries. Do not add a second LangGraph runtime or require LangSmith. |
| [aaif-goose/goose](https://github.com/aaif-goose/goose) | `fb9e3c89b2b4` | [Apache-2.0](https://github.com/aaif-goose/goose/blob/fb9e3c89b2b4670a0eded99e7567e578ac6e502c/LICENSE) | Adapt frozen tool-catalogue leases and usage event attribution; no general extension marketplace. |
| [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) | `8d39305538c1` | [MIT](https://github.com/OpenHands/OpenHands/blob/8d39305538c1d17a30cbe477e57a0e18fcee7d95/LICENSE) | Landscape/UI/backend-boundary reference. This checkout is Agent Canvas; do not attribute SDK runtime features to its frontend. |
| [Aider-AI/aider](https://github.com/Aider-AI/aider) | `5dc9490bb35f` | [Apache-2.0](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/LICENSE.txt) | Adapt a budgeted context index. Disable cache keepalive traffic and omit coding-only AST/edit machinery. |

Pi's older `badlogic/pi-mono` URL redirects to `earendil-works/pi`; `block/goose` redirects to `aaif-goose/goose`. These identities were resolved rather than treated as separate independent projects. All 13 metadata responses were unarchived at inspection.

## Feature-to-source evidence

Each link points to the exact inspected revision. The plan specifies Council adaptations separately; it does not claim every proposed behavior already exists upstream. F13 is a Council-specific requirement, grounded in its existing independent-opening exposure boundary.

### F01
- [anomalyco/opencode / packages/core/src/session/usage.ts](https://github.com/anomalyco/opencode/blob/6bac3b9ad8a3bed5ac01b8f6a3c30850a4d04685/packages/core/src/session/usage.ts)
- [earendil-works/pi / packages/ai/src/types.ts](https://github.com/earendil-works/pi/blob/0ed1b0431444f1e9321c5cf3a9e0acd04da11f89/packages/ai/src/types.ts)

### F02
- [anomalyco/opencode / packages/core/src/session/usage.ts](https://github.com/anomalyco/opencode/blob/6bac3b9ad8a3bed5ac01b8f6a3c30850a4d04685/packages/core/src/session/usage.ts)

### F03
- [xai-org/grok-build / crates/codegen/xai-chat-state/src/usage.rs](https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-chat-state/src/usage.rs)
- [zai-org/ZCode / apps/zcode-cli/packages/core/src/runtime/methods/usage-observability.ts](https://github.com/zai-org/ZCode/blob/0a1fc56d279fd1001f78387bd81aec1c26767411/apps/zcode-cli/packages/core/src/runtime/methods/usage-observability.ts)

### F04
- [QwenLM/qwen-code / packages/core/src/agents/runtime/workflow-budget.ts](https://github.com/QwenLM/qwen-code/blob/5dcf7c7cb162e825d95d531081f67ee60da3c0e1/packages/core/src/agents/runtime/workflow-budget.ts)

### F05
- [anomalyco/opencode / packages/ai/src/cache-policy.ts](https://github.com/anomalyco/opencode/blob/6bac3b9ad8a3bed5ac01b8f6a3c30850a4d04685/packages/ai/src/cache-policy.ts)

### F06
- [Aider-AI/aider / aider/website/docs/usage/caching.md](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/website/docs/usage/caching.md)
- [earendil-works/pi / packages/coding-agent/docs/compaction.md](https://github.com/earendil-works/pi/blob/0ed1b0431444f1e9321c5cf3a9e0acd04da11f89/packages/coding-agent/docs/compaction.md)

### F07
- [langchain-ai/deepagents / libs/deepagents/deepagents/backends/protocol.py](https://github.com/langchain-ai/deepagents/blob/12f70f27cc2e96ac715f4563e05b205be7adc275/libs/deepagents/deepagents/backends/protocol.py)
- [MiniMax-AI/Mini-Agent / mini_agent/tools/note_tool.py](https://github.com/MiniMax-AI/Mini-Agent/blob/d76a4f6389688cabda39c224a6cdfa274215d47c/mini_agent/tools/note_tool.py)

### F08
- [langchain-ai/deepagents / libs/deepagents/deepagents/middleware/filesystem.py](https://github.com/langchain-ai/deepagents/blob/12f70f27cc2e96ac715f4563e05b205be7adc275/libs/deepagents/deepagents/middleware/filesystem.py)
- [can1357/oh-my-pi / packages/coding-agent/src/tools/read.ts](https://github.com/can1357/oh-my-pi/blob/53a0377db6845e0dae606146130766ec92d407fd/packages/coding-agent/src/tools/read.ts)

### F09
- [anomalyco/opencode / packages/core/src/tool/plugin/websearch.ts](https://github.com/anomalyco/opencode/blob/6bac3b9ad8a3bed5ac01b8f6a3c30850a4d04685/packages/core/src/tool/plugin/websearch.ts)
- [can1357/oh-my-pi / docs/tools/web_search.md](https://github.com/can1357/oh-my-pi/blob/53a0377db6845e0dae606146130766ec92d407fd/docs/tools/web_search.md)

### F10
- [zai-org/ZCode / apps/zcode-cli/packages/core/src/tool/handlers/webfetch-egress-guard.ts](https://github.com/zai-org/ZCode/blob/0a1fc56d279fd1001f78387bd81aec1c26767411/apps/zcode-cli/packages/core/src/tool/handlers/webfetch-egress-guard.ts)
- [deepseek-ai/deepseek-harness / packages/web/web-fetch-http/src/policy.ts](https://github.com/deepseek-ai/deepseek-harness/blob/687f282e8625c6b8d11ff58211a90524be2e4317/packages/web/web-fetch-http/src/policy.ts)
- [can1357/oh-my-pi / packages/coding-agent/src/web/response-body.ts](https://github.com/can1357/oh-my-pi/blob/53a0377db6845e0dae606146130766ec92d407fd/packages/coding-agent/src/web/response-body.ts)

### F11
- [zai-org/ZCode / apps/zcode-cli/packages/core/src/tool/handlers/webfetch-cache.ts](https://github.com/zai-org/ZCode/blob/0a1fc56d279fd1001f78387bd81aec1c26767411/apps/zcode-cli/packages/core/src/tool/handlers/webfetch-cache.ts)

### F12
- [google-gemini/gemini-cli / packages/core/src/tools/web-search.ts](https://github.com/google-gemini/gemini-cli/blob/76e4d7c046c7dab5727787da378b9c06bf0948cf/packages/core/src/tools/web-search.ts)

### F13
Council source: `src/zerowall/council_review_v3.py`, especially `prompt()` and `exposure_boundary`. Shared-source barriers are our adaptation.

### F14
- [QwenLM/qwen-code / packages/core/src/managed-runtime/local-managed-tool-result-store.ts](https://github.com/QwenLM/qwen-code/blob/5dcf7c7cb162e825d95d531081f67ee60da3c0e1/packages/core/src/managed-runtime/local-managed-tool-result-store.ts)
- [QwenLM/qwen-code / packages/core/src/tools/tool-result-retention.ts](https://github.com/QwenLM/qwen-code/blob/5dcf7c7cb162e825d95d531081f67ee60da3c0e1/packages/core/src/tools/tool-result-retention.ts)
- [deepseek-ai/deepseek-harness / packages/compaction/compaction-tool-result-pruner/src/index.ts](https://github.com/deepseek-ai/deepseek-harness/blob/687f282e8625c6b8d11ff58211a90524be2e4317/packages/compaction/compaction-tool-result-pruner/src/index.ts)

### F15
- [Aider-AI/aider / aider/repomap.py](https://github.com/Aider-AI/aider/blob/5dc9490bb35f9729ef2c95d00a19ccd30c26339c/aider/repomap.py)

### F16
- [earendil-works/pi / packages/coding-agent/docs/compaction.md](https://github.com/earendil-works/pi/blob/0ed1b0431444f1e9321c5cf3a9e0acd04da11f89/packages/coding-agent/docs/compaction.md)
- [MiniMax-AI/Mini-Agent / mini_agent/agent.py](https://github.com/MiniMax-AI/Mini-Agent/blob/d76a4f6389688cabda39c224a6cdfa274215d47c/mini_agent/agent.py)

### F17
- [earendil-works/pi / packages/agent/src/agent-loop.ts](https://github.com/earendil-works/pi/blob/0ed1b0431444f1e9321c5cf3a9e0acd04da11f89/packages/agent/src/agent-loop.ts)
- [MiniMax-AI/Mini-Agent / mini_agent/tools/base.py](https://github.com/MiniMax-AI/Mini-Agent/blob/d76a4f6389688cabda39c224a6cdfa274215d47c/mini_agent/tools/base.py)

### F18
- [aaif-goose/goose / crates/goose/src/agents/extension_manager/lease.rs](https://github.com/aaif-goose/goose/blob/fb9e3c89b2b4670a0eded99e7567e578ac6e502c/crates/goose/src/agents/extension_manager/lease.rs)
- [QwenLM/qwen-code / packages/core/src/agents/runtime/workflow-budget.ts](https://github.com/QwenLM/qwen-code/blob/5dcf7c7cb162e825d95d531081f67ee60da3c0e1/packages/core/src/agents/runtime/workflow-budget.ts)

### F19
- [earendil-works/pi / packages/coding-agent/src/core/session-manager.ts](https://github.com/earendil-works/pi/blob/0ed1b0431444f1e9321c5cf3a9e0acd04da11f89/packages/coding-agent/src/core/session-manager.ts)
- [xai-org/grok-build / crates/codegen/xai-chat-state/src/usage.rs](https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-chat-state/src/usage.rs)

### F20
- [zai-org/ZCode / apps/zcode-cli/packages/core/src/runtime/methods/usage-observability.ts](https://github.com/zai-org/ZCode/blob/0a1fc56d279fd1001f78387bd81aec1c26767411/apps/zcode-cli/packages/core/src/runtime/methods/usage-observability.ts)
- [aaif-goose/goose / crates/goose/src/agents/state_machine/usage.rs](https://github.com/aaif-goose/goose/blob/fb9e3c89b2b4670a0eded99e7567e578ac6e502c/crates/goose/src/agents/state_machine/usage.rs)

## Reuse conditions

1. Prefer stable libraries for document extraction and SQLite indexing, then small audited adapters. Preserve the existing Council scheduler, durable attempt ledger and review policies.
2. TypeScript/Rust code is a design reference unless a clearly bounded, licensed port is justified. A Python application should not gain multiple sidecar runtimes simply to reuse a helper.
3. Preserve MIT notices and Apache licence/NOTICE requirements for any copied code; inspect transitive licences and pin actual imported versions before implementation. Do not infer that source availability grants free hosted search or model use.
4. No repository was adopted wholesale. Framework swaps, unrestricted shells, multi-agent fan-out and tool marketplaces are outside this plan.
5. The raw read-only research copies are under ignored `data/research-1.05`; the committed research manifest records 71 downloaded files, hashes, reviewed feature evidence and scope. No upstream code is shipped as application code by this planning task.

## Deliberately rejected patterns

- Missing usage or a missing price becoming zero: preserve typed unknowns and partial totals.
- One tokenizer being described as exact for unrelated providers: distinguish bounds/estimates from returned usage.
- Background cache-warming pings: they consume quota and can create charges.
- Automatic LLM compaction outside the request allowance: reserve and attribute any such call.
- Soft fan-out limits: concurrent in-flight requests can overshoot; Council needs atomic reservations.
- Aggressive tool-result pruning without recoverable originals: retain immutable source versions and range reads.
- Installing thirteen complete harnesses or replacing the current Council engine: reuse focused mechanisms and existing local infrastructure.
