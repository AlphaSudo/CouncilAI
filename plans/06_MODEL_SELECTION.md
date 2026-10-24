# ZeroWall Model Selection

**October 19, 1.01:** direct council chat now uses the director-provided Z.ai, Gemini, NVIDIA NIM and Groq keys with the exact seats in [direct model configuration](../config/direct_models.json). OpenRouter is disabled by default. The Token Factory order below retains its separate scope and billing gate. See [provider operations](../docs/operations/DIRECT_PROVIDERS.md).

**Updated:** October 18, 2026.  
**Authority:** the director's explicit model order.  
**Policy file:** [model policy](../config/model_policy.json).  
**Published references:** [model manifest](../benchmark/model_manifest.json).

## 1. Ordered allowlist

| Priority | Exact requested ID | Status |
| --- | --- | --- |
| 1 | `nvidia/Nemotron-3.5-Super-VL` | Primary preference; documented exact ID; account access and runtime behavior untested. |
| 2 | `zai-org/GLM-5.3-Flash` | Second preference; documented exact ID; account access and runtime behavior untested. |
| 3 | `nvidia/Nemotron-3_5-Lightning` | Third preference; documented exact ID; account access and runtime behavior untested. |
| 4 | `deepseek-ai/DeepSeek-V4.1-Flash` | Optional and disabled; exact ID, prices, and account access still require verification. |

Preserve this order and spelling. Do not substitute an old Super endpoint, Ultra, a differently named DeepSeek variant, or an unlisted model automatically. Do not enable DeepSeek without explicit director opt-in.

The list expresses selection priority. It is not an instruction to call every listed model for each prompt or every retry. Four logical seats remain part of the product; their actual model assignment is not yet implemented and must be shown explicitly. Multiple seats may reuse a model. Paid fallbacks still require separate reservations, and ambiguous prior charges remain reserved.

Default routing follows the director's priority rather than sorting by price. A comparison experiment that intentionally selects another allowed model must show that treatment explicitly in its approved plan. The optional model cannot enter those experiments while disabled.

## 2. Published price references

Prices below are references checked on October 18, not account-verified runtime billing:

| Model | Input per 1M tokens | Output per 1M tokens | Reference |
| --- | --- | --- | --- |
| Nemotron 3.5 Super VL | $0.30 | $0.90 | [Official launch article](https://nebius.com/blog/posts/three-new-open-weight-models-from-us-companies-give-builders-more-choice) |
| GLM 5.3 Flash | $0.15 | $0.50 | [Official model page](https://nebius.com/services/token-factory/models/glm-models-inference) |
| Nemotron 3.5 Lightning | $0.06 | $0.24 | [Official model page](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference) |
| DeepSeek V4.1 Flash | Unknown | Unknown | [Release notes name the model family](https://nebius.com/release-notes/posts/q3-2026) |

Priority is therefore not a claim that the first model is cheapest. Maximum input/output, billed reasoning or other categories, retry/escalation limits, aggregate reservations, and verified account controls determine whether a call is affordable.

No published reference permits assuming the API key has access. Capability and account-catalog checks remain feasibility work. Requests start as text only; vision, image, audio, or video costs are not bounded by this text-price table.

## 3. Readiness and execution limits

The local environment file now contains a nonempty Token Factory key entry; only its presence was checked, and no secret was displayed. This does not establish key validity, model access, account billing, or inference success.

`live_inference_enabled` is false in the saved policy. The application/router and durable budget guard are not implemented yet. No inference requests were made while recording this policy. Verify credit/overage behavior, current prices and token categories, model access, request bounds, and durable reservations before enabling live dispatch.

The maximum authorization remains $25 of existing Token Factory credit and $0 additional personal payments. Configuration records the policy; it does not guarantee provider-wide account billing behavior.
