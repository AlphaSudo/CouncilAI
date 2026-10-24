# Council baseline and price-cache lifecycle

The default provider is Nebius Token Factory with these three selected seats:

1. `nvidia/Nemotron-3.5-Super-VL` — lead.
2. `reflection/beam`.
3. `deepseek-ai/DeepSeek-V4-Flash-0731`.

Lightning remains optional. Direct providers remain available through an explicit selection; readiness changes must not silently replace an established Token Factory setup.

| Feature | Baseline |
| --- | --- |
| Context window | 262,144 application tokens |
| Thinking | Balanced, approximately 4,000 reasoning tokens by default; selectable presets remain available; native enforcement varies by model |
| Context display | Circle beside thinking/send, truthful unknown state before measurement, compaction inspector and controls |
| Search | On by default, collective parallel research before independent openings, shared saved source library |
| Deliberation | Answer-first review; annotation failures cannot overwrite committed public replies |
| Conversation tools | Compare, expanded reader, original model reply, copy one/all, edit and regenerate, multi-turn continuity |
| Usage | Per-response and accumulated token/cost accounting; unknown charges retained |
| Spending | Existing credit only, $24 aggregate application cap, no additional payment authority |
| UI | Simple and Explain views, dark default |

## Price cache: seven days

An expired local price cache previously set Token Factory's readiness to false. The frontend then selected the historical direct-provider lineup. Thinking presets and the context circle are provider-specific, so this also hid both controls. The underlying generation, compaction and review implementations were still present.

The price cache now lasts **7 days**. A refresh performs two metadata GETs: the official public tariffs and the account's accessible model catalogue. It preserves the existing spending-authority ID, $24 cap, settled charges, unknown reservations, model selections and generation controls. It does not run inference, recreate a spending grant, reset the ledger or claim knowledge of card settings.

Expired prices refresh on opening the council, a setup preview, creation, follow-up/control actions and before provider dispatch. Concurrent refresh requests share one check. A fresh cache needs no network traffic. A failed check uses a short retry backoff and preserves the selected provider and models; reconnect remains available. Requests requiring unverified prices stay unavailable until fresh evidence exists. A token-bound/billing-category lock cannot be cleared by refreshing prices.

Readiness determines whether a request can run. It does not determine which established setup the interface displays. Thinking and context controls remain visible while the selected Token Factory setup reconnects.

At narrow widths, header actions wrap so the Simple/Explain switch remains reachable. The responsive test retains its viewport and control-alignment assertions.

Regression evidence is recorded in `docs/validation/baseline-stability*.json`, backend checks, and the Token Factory, thinking, context, research, copy, edit and Compare browser suites.
