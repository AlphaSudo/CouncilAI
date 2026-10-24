# Token Factory context window

The current application window is **262,144 tokens shared by input, reasoning and visible output**. `config/token_factory_generation.json` declares the window independently of each model's larger published capacity. All four allowed Token Factory models use it, including optional Lightning. The 4,000-token reasoning instruction and model effort controls remain unchanged; reasoning adherence is still provider behavior, not a hard isolated token ceiling.

The old 90,000-byte review, 94,000/100,000-byte source pack, 48,000-byte tool-history and 120,000-byte wire limits no longer gate Token Factory requests. Other providers retain their existing limits; this change does not assert that their free endpoints support 262K. Mandatory source units, warnings and objections are preserved. New Token Factory review contracts describe the token window; saved review contracts/hashes are never rewritten on read.

## Local token admission

`scripts/setup_tokenizers.py` downloads only public `tokenizer.json` data from the model authors' pinned Hugging Face revisions. `config/token_factory_tokenizers.json` records their URLs, revisions, sizes and SHA-256 hashes. Files live in ignored `data/tokenizers`; no model weights, GPU, API key or model inference is used. Setup verifies hashes. The runtime checks the local hash on first load, disables tokenizer truncation/padding, and never downloads anything during a conversation. Missing or invalid data blocks before dispatch with a setup instruction.

Admission tokenizes the complete decoded message contents, including the system/reasoning instruction, mandatory stage data, source prefix, tools, completed tool exchanges and recovery instructions. It adds an explicit **4,096-token framing allowance plus 32 tokens per message**. This is a local estimate using the published vocabulary, not an exact reproduction of Nebius's hosted chat template. Provider-reported usage remains authoritative. Native context capacity is also recorded separately and exceeds this application window for the configured models.

The requested output allowance is fitted into the remaining shared window. Independent openings request the largest output allowance fitting both that window and the remaining monetary authority. Review stages request up to 32,768 combined output tokens, reduced only when the remaining window is smaller. An input leaving no output space stops before dispatch or reservation, gives the token count and window, and preserves all saved work. No mandatory input is clipped. Source retrieval still has a separate bounded passage budget; library reads remain available for other ranges.

## Spending and resource accounting

Context counts do **not** replace financial bounds. Before every request, the ledger still reserves `(complete serialized UTF-8 request bytes + 4096) × verified input multiplier` at full uncached input prices, plus the requested combined output at its verified price. Current testing uses multiplier 2. This mathematical bound scales with the actual request size; a larger context does not receive an old 120KB reservation. No expected cache discount creates spending authority. Monetary insufficiency remains an explicit budget error, separate from a context error.

Local input/output resource pools cover twenty 262,144-token attempts. Input resources use the local context count rather than the intentionally inflated financial byte bound. The conversation allowance, attempt admission, **$24 aggregate cap**, authorization expiry and unknown-charge reservations remain enforced. This revision neither renews billing authorization nor retries or resumes a conversation.

## Validation

Offline tests exercise all four models' window profiles, shared-window boundaries, rejection before HTTP/reservation, a request exceeding one megabyte with more than 230,000 counted input tokens, large review/source packs with all 810 source units, and complete source/tool/history counting. Synthetic HTTP transports replace inference. The affected saved conversation is also compiled on a disposable SQLite copy before the server is reloaded; historical answers, charges and unknown reservations remain intact.

Primary tokenizer sources and pinned revisions are in the [manifest](../../config/token_factory_tokenizers.json). The local loading/counting API is documented in the [Hugging Face Tokenizers quick tour](https://huggingface.co/docs/tokenizers/python/latest/quicktour.html).
