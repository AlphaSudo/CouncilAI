# Provider accounting and search constraints for 1.05

Research date: October 19, 2026. These are public documentation observations, not a check of the user's account balance, billing configuration, entitlement or invoice. No model inference or paid search was invoked for this research.

## Current configured seats

The local source of truth is `config/direct_models.json`: Z.ai `glm-4.7-flash`, Google `gemini-3.5-flash-lite`, NVIDIA hosted `nvidia/nemotron-3-super-120b-a12b`, Groq `openai/gpt-oss-120b`, and the explicitly authorized Groq `openai/gpt-oss-20b` replacement. This plan does not change those selections.

| Endpoint/model | Published standard reference prices, USD per million tokens | Cache interpretation | Planning consequence |
| --- | --- | --- | --- |
| Z.ai GLM-4.7-Flash | Input, cached input and output are listed Free; cached storage is also listed Free. | Chat response can report `usage.prompt_tokens_details.cached_tokens`. Separate write-token billing is not established by that field. | Preserve reported counts. Do not invent a charged write category. [Pricing](https://docs.z.ai/guides/overview/pricing), [API fields](https://docs.z.ai/api-reference/llm/chat-completion). |
| Gemini 3.5 Flash-Lite | Paid Standard reference: input **0.30**, output including thinking **2.50**, cached input **0.03**; cache storage **1.00 per million token-hours**. | The exact model's pricing table marks context caching unavailable on Free. A generic caching guide is insufficient entitlement evidence. | No paid explicit cache creation under the current budget. Reference prices are distinct from free-tier entitlement and provider-reported cost. [Exact model table](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite). |
| NVIDIA hosted Nemotron Super | A verified per-million input/output/cache tariff for this exact hosted endpoint was not established in this review. | Hosted service and self-hosted NIM behavior must be distinguished. Optional usage fields depend on the endpoint. | Rate remains **unknown**, not zero and not borrowed from Nebius or another host. [NIM FAQ](https://docs.api.nvidia.com/nim/docs/product), [API reference](https://docs.api.nvidia.com/nim/reference/llm-apis). |
| Groq GPT OSS 120B | Input **0.15**, output **0.60**; documented cached-input discount gives a **0.075** reference rate. | Implicit prefix caching is documented for this model, without an extra cache-creation fee. Actual hits must come from usage. | Missing cache telemetry remains unknown. No keepalive request is needed. [Models](https://console.groq.com/docs/models), [Caching](https://console.groq.com/docs/prompt-caching). |
| Groq GPT OSS 20B | Input **0.075**, output **0.30**; cached-input reference **0.0375**. | Same documented caching family; actual account and endpoint still govern. | Price the actual replacement model, retaining its relationship to the original seat. Same [model](https://console.groq.com/docs/models) and [cache](https://console.groq.com/docs/prompt-caching) sources. |

Prices must become versioned records with source URL, checked time, effective period, endpoint, exact model, tier, modality, context-size bracket and service class. Revalidate before enabling a billable feature. Never silently reprice a historical request with the latest rate.

## Accounting rules

The APIs do not share one universal token-count convention. Keep raw usage plus the adapter version and field mappings. Google exposes `promptTokenCount`, `cachedContentTokenCount`, `candidatesTokenCount`, `thoughtsTokenCount` and other fields; their billing relationships must be mapped explicitly. Z.ai and Groq expose compatible-looking prompt/cache fields. Similar field names do not prove identical semantics. [Google usage reference](https://ai.google.dev/api/generate-content), [Z.ai usage reference](https://docs.z.ai/api-reference/llm/chat-completion), [NVIDIA vendor field survey](https://docs.nvidia.com/aiperf/reference/vendor-usage-field-reference).

The proposed calculator uses **disjoint billable components**. If prompt tokens include cache reads, subtract those reads once before pricing ordinary input. If reasoning is a subset of output, do not add it a second time. If the provider reports visible output and reasoning separately, form the billed output according to its documented rule. Never equate all cold input with cache writes.

Use `known`, `not_reported`, `not_applicable`, `estimated`, `invalid` and `unknown_outcome` states. A literal provider zero is known zero; an absent field is not. Validate finite nonnegative integers and subset relationships. Preserve conflicting raw data and mark normalization invalid rather than quietly clamping it.

Distinguish three monetary views:

1. **Provider-reported amount:** what this response actually reports, with completeness. It is not automatically a reconciled invoice.
2. **Applicable-tariff estimate:** computed only when the user's tier, charged categories and rates are established; otherwise partial/unknown.
3. **Published list-price equivalent:** a labelled reference comparison, useful for estimating future scale. It must not imply that a free account has been charged that amount.

The conversation total counts each physical API attempt and external tool charge once. It includes rejected outputs, retries, replacements, research steps, optional summary calls, cache lifecycle charges and late responses. Shared research is its own overhead bucket; showing it under every model must not multiply the financial total. Unknown outcomes remain counted and reserved.

## Calculation example

For Groq 120B's published reference tariff, assume a provider response reports 12,000 prompt tokens, of which 9,000 are cached, and 1,000 billed output tokens:

```text
Uncached input: 3,000 × $0.15 / 1,000,000 = $0.000450
Cache read:     9,000 × $0.075 / 1,000,000 = $0.000675
Output:         1,000 × $0.60 / 1,000,000 = $0.000600
Reference total:                              $0.001725
```

The corresponding all-uncached reference is $0.002400. The $0.000675 difference is an arithmetic comparison under those inputs, not a promised saving or an account charge. Cache-write count is not inferred from the 3,000 uncached tokens. Use exact Decimal arithmetic; preserve finer precision than one microdollar for categories and round only at defined boundaries.

## Web search: practical initial choice

**Recommended optional integration: Tavily's free Researcher account, basic Search only, through a shared broker.** Its docs advertise 1,000 monthly credits without a card; Basic Search consumes one credit and Advanced Search consumes two. Paid/pay-as-you-go modes exist. Account setup must stay on the free plan without paid overages. A local reservation cap is required independently of the provider quota. [Credits and pricing](https://docs.tavily.com/documentation/api-credits), [provider pricing FAQ](https://www.tavily.com/pricing).

Start with ordinary bounded HTTP retrieval for result URLs, not paid Extract/Crawl/Research operations. Extraction licensing, request limits and site access still apply. An API key is required for Tavily; none is created or supplied by this plan. If the optional key is unavailable, Council still supports supplied documents, direct public URLs and its local library. It should say search is unavailable rather than pretend to have searched.

| Alternative | Evidence and boundary | Decision |
| --- | --- | --- |
| Z.ai native Web Search | Public pricing lists **$0.01/use**, independent of a free text model. [Pricing](https://docs.z.ai/guides/overview/pricing). | Disabled under the current zero-additional-payment boundary unless separately funded existing credit and all charges are confirmed. |
| Gemini Google Search grounding | The configured Flash-Lite model's table does not offer it in the API Free tier; AI Studio testing is not an API entitlement. [Pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite), [grounding guide](https://ai.google.dev/gemini-api/docs/google-search). | Do not turn it on automatically from a free Gemini key. |
| Groq built-in browser search | Tool availability and pricing are separate capabilities; a model's tool-calling ability does not establish a free search entitlement. [Browser search](https://console.groq.com/docs/tool-use/built-in-tools/browser-search). | Leave native hosted search off until exact model/account/tool charging is verified. Local function calls to our broker are a different mechanism. |
| Local SearXNG | Provides a search API; many public instances disable JSON/CSV output and operators apply limits. [Search API](https://docs.searxng.org/dev/search_api.html), [server settings](https://docs.searxng.org/admin/settings/settings_server.html). | Optional local/operator-controlled adapter later. No assumption that arbitrary public instances provide a reliable free backend. No mandatory cloud/GPU. |
| Credential-free scraping/fan-out | Some agent harnesses include it; fragility, CAPTCHA and provider restrictions vary. | Not the default. No bypassing blocks or multiplying searches across engines to conceal exhausted quotas. |

## Four different caches

| Layer | What is reused | What it does not establish |
| --- | --- | --- |
| HTTP/search result cache | A saved query result or fetched version, subject to freshness. | Provider token-cache hits or current truth. |
| Library/index cache | Extracted chunks and local ranked lookups. | Zero input tokens when those chunks are sent to a model. |
| Context-pack cache | A deterministic set/order of passages, schema and stable instructions. | A shared KV cache across providers or seats. |
| Provider prompt cache | Provider/model-scoped reused prefix computation, when reported. | Guaranteed hits, transferable cache handles, universally free writes or unlimited quota. |

The first three layers work with the existing local machine. Provider caching requires exact capability/tariff handling. Groq documents exact prefix matching and notes that cache deductions happen after processing, so simultaneous large requests can still hit a token limit. [Groq caching](https://console.groq.com/docs/prompt-caching).

For an explicit provider cache, compare expected reuse savings against creation, storage, refresh and extra model-call costs. If those costs are unknown or billable without authorization, do not create it. Never send dummy requests merely to keep a cache warm.

## Credentials and funding impact

- Existing four model keys remain server-side; no new generation provider or model is required.
- Optional new credential: `TAVILY_API_KEY`, with a confirmed free-only account and locally reserved monthly credits. Recheck the provider's reset period; do not assume a UTC month matches an account period.
- No LangSmith subscription, paid vector database, GPU, AI Cloud account, LangGraph service, OpenRouter activation or paid agent subscription is required.
- Token Factory's existing billing-verification gate and at-most-$25 existing-credit boundary stay intact. No additional personal payment is authorized by this plan.
