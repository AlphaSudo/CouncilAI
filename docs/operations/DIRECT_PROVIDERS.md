# Direct council providers

Save the keys in ignored `.env.local` as `ZAI_API_KEY`, `GEMINI_API_KEY`, `NVIDIA_NIM_API_KEY`, and `GROQ_API_KEY`. They stay server-side and are excluded from exports and release packages. Restart after editing credentials or explicit model configuration.

Set `ZEROWALL_DIRECT_FREE_CONFIRMED=true` only after confirming free access without automatic paid charging. This records the director's authority; it cannot change or certify provider account billing. Token Factory retains its separate existing-credit gate and $24 aggregate ceiling. GPU rental remains outside scope.

| Provider | Endpoint | Official reference |
| --- | --- | --- |
| Z.ai | `https://api.z.ai/api/paas/v4/chat/completions` | [Free GLM pricing](https://docs.z.ai/guides/overview/pricing), [chat API](https://docs.z.ai/api-reference/llm/chat-completion) |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent` | [Models API](https://ai.google.dev/api/models), [free-tier pricing](https://ai.google.dev/gemini-api/docs/pricing) |
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1/chat/completions` | [Hosted API catalogue](https://docs.api.nvidia.com/nim/reference/llm-apis) |
| Groq | `https://api.groq.com/openai/v1/chat/completions` | [API reference](https://console.groq.com/docs/api-reference), [account limits](https://console.groq.com/docs/rate-limits) |

Each participant uses its selected upstream and saved key. There is no gateway or key-rotation scheme. A literal `private/` deployment prefix is normalized only when the remaining ID exactly matches the requested model; raw identities remain recorded. A different model is not admitted.

Requests contain no paid search, MCP tools or code execution. The director authorized one named free Groq alternative after two eligible GPT OSS 120B failures: `openai/gpt-oss-20b`. Substitution is audited and visible; it cannot bypass authentication, billing, cost locks or identity validation. There is no general provider-routing fallback. Every dispatched attempt is recorded before the network request, including ambiguous outcomes. Durable transport retries allow two automatic retries per turn and three shared retries per bounded request, honoring rate-limit hints. The single substitution also consumes the request's attempt ceiling. Interrupted dispatch requires explicit continuation.

Direct councils allow twenty attempts per explicit request and one hundred per UTC day per application database. A follow-up creates an audited allowance in the same conversation; prior calls remain counted and unused allowance does not accumulate. Resume alone does not create a new allowance. The old six-cycle ceiling is removed for direct chats. Actual provider quotas are separate; missing headers remain unknown. Development databases have separate audit trails and consume real provider quota too. Changing a key does not erase a database's counters.

Missing monetary usage is stored as `cost_status=not_reported`, `cost_usd=null`. A positive or invalid reported cost locks that provider. Never infer a zero invoice from an omitted cost field. The application does not top up accounts or enable paid charging.

OpenRouter is disabled by default through `ZEROWALL_OPENROUTER_ENABLED=false`. Saved history remains readable. Restoring legacy inference is an explicit configuration change, not an outage fallback.

For an outage, inspect the retained phase/error. Missing opening or author participation is disclosed. A missing mandatory review stage needs retry, explicit reassignment or partial synthesis. Replacement author replies are attributed to the actual responder. No absent model's agreement is invented.
