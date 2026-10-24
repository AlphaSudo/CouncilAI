# Council chat walkthrough

## Current Council

The interface opens in **Simple** view. The question and final answer are prominent; **Council discussion** expands the saved model exchanges. **Customize** opens participant and answer settings. **Why this answer?** opens the claim/source inspector.

Use the **Simple / Explain** switch at the top for testing or debugging. Explain shows every phase and model reply, actual model identifiers, the existing **Claims & evidence** inspector, role assignments and a bounded execution snapshot. On smaller screens, **Behind the answer** expands those diagnostics. Both views operate the same Council and preserve the draft and conversation. The switch makes no model call; **Explain this answer** is a separate, explicitly requested model-generated follow-up. The view preference survives reload in this browser.

Open the prompt, choose the participating models if desired, and press **Start council**. The Council combines independent answers, key claims, challenges, author responses/revisions, scoped checks and a final answer. There is one current method and no version or mode selector. **Answer requirements** accepts optional constraints and source context.

Use **Claims & evidence** for the detailed basis, **Challenge this claim** for a targeted same-chat review, or **Explain this answer** for an explanation of a saved result without new review/evidence status. A new free-form question starts a full cycle in the same conversation. A late material issue can receive one bounded focused exchange; otherwise it stays visible as unresolved. Partial results are labelled **Partial answer**.

The current implementation and its live/provider/quality limitations are in [the release record](releases/1.03.md). Historical sections below describe their recorded earlier builds and do not add choices to the current composer.

## Historical entry point: 1.02

New conversations default to **Reviewed council -> Scoped review 1.02**. The actual method is labelled above the transcript. On a completed older conversation, the next message starts a full 1.02 review in the same chat unless **Keep current method** is selected. Previous messages and their original method remain saved; no inference runs merely from opening an older chat. See [the activation correction](releases/1.02.2.md).

## Continuity and presentation: 1.02.1

The council opens in dark mode. Titles use normal letter spacing and up to two lines. Saved JSON replies display as sections and lists with the original response expandable; equations render locally. Source text and exports stay unchanged.

Gemini leads Discussion synthesis when selected and available. A direct-provider follow-up starts a fresh bounded request in this same chat, retaining previous answers and total attempt counts. Each request has up to twenty attempts; the database-wide daily cap stays one hundred. Exhausting the daily allowance means waiting and returning to this chat. No new chat is required to reset a request allowance. One explicitly allowlisted Groq free-model replacement is permitted after two eligible primary failures, with actual model attribution. See [the patch record](releases/1.02.1.md).

## Scoped review preview: version 1.02

The default **Reviewed council -> Scoped review 1.02** uses the same selected provider seats and call schedule. The initial profile reviews up to two atomic claims per model; omitted material stays disclosed. Existing messages retain their original protocol; an explicit new review cycle records any forward transition.

Scoped review separates whether an objection was answered, what evidence supports the current claim, and remaining ordinary risk. Expand **Claims & evidence** to compare original passages with normalized assertions, inspect per-author revisions and claim groups, examine candidate tests, and see source-provenance warnings. Model closure is not external verification. When attaching a source, explicitly assess the supported scope and whether it covers the whole current claim or only part.

The final response leads with a direct answer when its basis permits one. Conditional recommendations preserve assumptions and evidence limits; material unresolved issues can leave the decision open. Quality evaluation remains pending; see [the pilot protocol](evaluation/SCOPED_QUALITY_PROTOCOL.md).

## Shared review controls, introduced in 1.01

Open `http://127.0.0.1:8000/` directly. Choose **Direct models · 4 providers** for Z.ai, Gemini, NVIDIA NIM and Groq, or Synthetic demo for scripted local testing. Keys stay server-side. OpenRouter is disabled and hidden for new work by default. Older conversations remain readable.

Select **Discussion** for the original round-based conversation, or **Reviewed council** for independent answers, source-linked claim extraction, scrutiny, one original-author reply per member, recheck and a constrained final answer. Four reviewed models plan twelve calls plus three shared retry attempts. Two and three models plan eight and ten calls. The setup preview and dispatch share the server's schedule calculation; expand **Review role assignments** to inspect role reuse before starting.

Review requirements are optional: enter a deliverable, hard constraints, preferences, baseline, success criteria and evidence requirement. Unspecified items remain unspecified. Source extraction chooses numbered passages; the server supplies exact original text and offsets. Coverage remains a fallible model assessment.

Click **Claims & evidence** to inspect source passages, scope, assumptions, dependencies, revisions, objections, author replies, model rechecks, evidence and computed labels. The inspector supports mobile and keyboard use. Escape closes it. A model's confidence or agreement cannot grant external verification; human and tool assessments retain their actual origin and scope.

Attach a source excerpt with attribution or existing approved tool evidence from the same chat/research step. A URL alone is insufficient. An explicit human relevance assessment records what you checked; merely attaching a source does not establish support. Finding dispositions preserve unresolved objections, rebuttals, evidence-backed defects or accepted bounded risks. Accepted risk does not change evidence strength.

Evidence or disposition changes make a published answer visibly stale. **Update final answer** requests one new synthesis; stale answers cannot be newly accepted as current. A malformed final falls back to a local ledger summary without another inference call. Other malformed model outputs retain raw artifacts and require an explicit retry. There is no hidden format-repair inference.

Notes steer subsequent turns. In-flight replies keep their captured context. Required objections and constraints come from durable records; if they cannot fit the input envelope, execution holds rather than dropping them. **Pause**, **Resume**, **Stop** and **Synthesize now** preserve their dispatch controls. An early final is labelled partial.

Temporary provider failures use durable waits, honoring retry hints, at most two automatic retries per turn and three shared retries per bounded request. Groq can additionally use its single authorized model substitution within the same attempt ceiling. Every dispatched attempt remains counted. Restart during a request requires explicit recovery. A missing mandatory reviewer does not count as completed review: retry, explicitly reassign the next phase to a selected available member, or request a partial final. Replacement author replies are attributed to their actual responder.

Changing a question or hard constraint creates a new contract revision/cycle after pausing and waiting for the in-flight request. Old cycles remain in history. A completed direct-provider follow-up starts a full reviewed cycle after preflighting a new bounded request and the remaining daily allowance.

Direct-provider limits are twenty attempts per bounded request and one hundred per UTC day per application database. The conversation retains its cumulative usage across requests. Actual provider quotas are separate. Changing keys does not reset counters. The director confirmed free access; missing monetary usage is recorded as not reported, not certified zero. Nonzero or invalid reported cost locks that provider. No paid routing fallback, account top-up or GPU allocation is performed. [Provider operations](operations/DIRECT_PROVIDERS.md) explains the authority and limits.

**Download transcript** saves Markdown messages. **Download review pack** adds structured records, frozen publication snapshots, source artifacts and hashes. Reconstruct labels without a provider key using `python scripts/verify_review_pack.py path/to/review.zip`. A successful workflow or reconstructed label is software evidence; independent human answer-quality evaluation remains pending. See [the release record](releases/1.01.md).

## Historical walkthrough for the earlier Discussion build

The material below describes recorded pre-1.01 behavior. Its OpenRouter setup and historical request counts do not enable that provider in the current build.

Open `http://127.0.0.1:8000/` to go directly to the prompt composer. Local browser sessions open automatically without entering a director token. If a temporary connection failure interrupts entry, click **Go to prompt** to retry. Use **New council** to start another conversation. The earlier mission, experiment, evidence and decision screens are available through **Research workspace** at `/?workspace=research`.

## Start a discussion

1. Choose the provider above the message box. **OpenRouter — free only** uses the saved server-side key. **Synthetic demo** uses clearly labelled scripted participants. Token Factory remains locked until its billing prerequisites have been verified.
2. Open **3 models** to select at least two distinct models. Each participant uses its own actual model ID, displayed beside its messages. The free defaults are Nemotron Super, Xing 4 and Nemotron Lightning; Gemma 4 is also selectable. Free availability can change between requests.
3. Choose the number of discussion rounds. The default three-model, two-round discussion needs ten successful requests: three openings, six discussion turns and one synthesis. Transient retries consume additional allowance. Model readiness claims do not skip your selected rounds. You can end the discussion early with **Synthesize now**.
4. Type the question and press **Start council**. Enter sends; Shift+Enter inserts a new line.

## What appears in the conversation

- **Independent opening answers:** each model gets the original question without its peers' answers. Answers appear in the interface as they finish, but other models cannot use them during this phase.
- **Shared reference baseline:** once every opening is saved, those actual answers become the common reference. Expand the baseline panel to jump back to each answer. It is a collection of proposals, not a claim that they are correct.
- **Discussion rounds:** models take turns in order. Each sees the baseline, recent discussion and the latest director notes. The instructions ask for specific challenges, revisions and remaining disagreements. Visible message numbers support references between replies.
- **Final synthesis:** the first available model combines the discussion into a proposed answer, retaining unresolved disagreements and uncertainty. The interface identifies the model writing it. A synthesis is not a vote or independent verification.

Responses appear as complete messages after each API request; this build does not stream individual tokens. Debate context is bounded: opening answers and recent discussion may be excerpted, and older turns may fall outside the window. The complete saved transcript remains visible to you.

Free-model contributions have a 3,072-token output ceiling and syntheses have 4,096, with concise response targets to avoid unfinished long replies. A provider-reported truncated response is retained in its raw artifact and stops execution; it is never silently treated as a complete answer. Response reading checks total elapsed time so whitespace keep-alives cannot keep an unavailable model busy indefinitely. Token Factory's existing paid output bounds remain unchanged.

## Direct the council

Type a concern in the same message box to guide the next turn. Notes entered while openings are being written are held for the discussion phase so the openings stay independent. A request already in flight uses its previously captured context.

**Pause** prevents the following dispatch; an in-flight answer is still saved if it arrives successfully. **Resume** continues from the first missing turn. Temporary free-provider 429/5xx errors and connection losses now schedule a visible automatic retry, with a countdown. The wait survives restart and can be paused or stopped. Retry hints are honored; otherwise waits increase from 20 to 40 seconds. There are at most two retries per turn and three per conversation. A request with an ambiguous outcome remains counted. A process restart during an in-flight request still requires explicit recovery.

If a free member remains unavailable, the council can continue with at least two available participants. Missing members are named in the header and transcript, their previous answers stay saved, and synthesis input explicitly records their absence. No model is silently substituted. If fewer than two remain available, the conversation explains that free hosting cannot currently complete the council. **Synthesize now** explicitly requests a partial answer from saved replies; partial syntheses are labelled. **Stop** ends further turns.

After the final answer, **Accept answer** records your acceptance, and **Download transcript** exports Markdown. A follow-up starts an additional discussion round and a new synthesis when sufficient request allowance remains. Previous final answers stay in the conversation. Free chat allows 20 total attempts per conversation and 50 per UTC day across the workspace. These are separate from the provider quota, displayed above the composer. Every retry consumes allowance. Changing the API key does not erase prior attempts. **Refresh allowance** checks the account without generating model output. Insufficient known allowance blocks a new council before inference. When at least five requests remain, **Use 2 models / 1 round** switches the visible setup to a five-reply council; extra requests can absorb retries but cannot guarantee provider availability.

## What was built before this screen

The research workspace supports frozen mission requirements, four role-based private commitments, cross-review, typed experiments, evidence, decision gates and reproducible reports. Those tools support deeper research work. They did not provide the straightforward group conversation requested here; council chat now supplies that entry point.

Free routing verifies the selected model's published prices before each request and sends zero price ceilings with provider fallbacks disabled. Account authentication, exhausted quota, access refusals and cost/identity anomalies get distinct explanations and are not blindly retried. Nonzero reported cost locks future free calls even when the HTTP request failed. No paid model, rented GPU, account top-up or Token Factory billing unlock is part of the free chat path. Free quota can cover a session while a shared provider is unavailable, so free hosting cannot guarantee even one complete council on demand.
