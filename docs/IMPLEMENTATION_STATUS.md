# Implementation and acceptance status

## Current unified Council - October 19, 2026

The interface now provides a calm **Simple** default and an **Explain** view for process inspection/debugging. These are two presentations of the same engine and saved chat. See [design research and behavior](design/COUNCIL_INTERFACE.md) and [UI acceptance](validation/council-design-status.json). The software counts below describe the preceding Council release; current UI validation is recorded separately.

Application 1.3.0 implements the single Council baseline. Normal creation no longer asks for a mode or review version. It combines independent answers, targeted challenges, public author revisions, scoped checks and Gemini-led synthesis, with same-chat continuation and preserved historical records. See [the release](releases/1.03.md), [the current plan](../plans/10_UNIFIED_COUNCIL_1.03.md) and [acceptance evidence](validation/council-1.03-status.json).

Local validation passed 304 backend tests in a fresh credential-free installation, all 14 browser scenarios, production build, backup/restore and mixed-version replay. Seven protected baseline files and 103 historical records remain unchanged. The checklist is 63/66 complete; its three independent evaluation tasks remain open.

The genuine four-provider development run ended in an explicit partial comparison after 11 attempts because of timeouts, invalid outputs and rate limits. Its generated final was admitted and its export reproduces; reliable full live-review completion and independent answer quality are not established. OpenRouter remains disabled, paid Token Factory access remains gated and GPU spending remains zero. Entries below are historical snapshots of earlier builds.

## Version 1.02 preview - October 19, 2026

Scoped review is implemented as an opt-in method for new Reviewed councils. It adds atomic assertions with exact sources, reversible groups, observation/test audits, scope-sensitive recheck and separate resolution/evidence/risk/decision states. See [the 1.02 release](releases/1.02.md), [requirement evidence](validation/review-1.02-status.json) and [checklist](../plans/08_IMPLEMENTATION_PLAN_1.02.md).

Software acceptance is separate from model quality. The four-provider development run completed through the conservative fallback after two invalid generated finals; another two-member run hit provider limits after an extraction rejection. Reliable live final compliance and independent human semantic quality remain pending. Version 1.01 publications retain their original policy and hashes.

## Version 1.01 update - October 19, 2026

Generic Reviewed council and four direct provider seats are implemented as an opt-in extension. OpenRouter is disabled for new inference by default. See [the release record](releases/1.01.md), [provider operations](operations/DIRECT_PROVIDERS.md), and [current acceptance evidence](validation/review-1.01-status.json). Counts and provider behavior below describe their recorded earlier builds.

The new workflow includes source-unit claims, scrutiny, versioned repairs, recheck, scoped publication labels, human evidence/dispositions, governed role/contract changes, mobile inspection and reproducible exports. Independent semantic quality evaluation remains pending. The application does not certify arbitrary claims or infer zero invoice cost from missing usage data.

Updated October 18, 2026. This is a runnable local development candidate covering the 0.1–1.00 implementation roadmap. It is **not a completed hackathon release**: the director explicitly kept paid inference locked while building, and external publication/submission have not occurred.

## What works

- Council chat is the default home page: a prompt composer, distinct actual model participants, isolated opening answers, a shared baseline, sequential discussion rounds, director interventions and a final synthesis. Saved conversations, pause/resume/stop, early synthesis, human acceptance and Markdown download are available. Research tools remain under `/?workspace=research`. See [the walkthrough](COUNCIL_CHAT.md).
- Frozen missions, typed contracts, an acyclic step graph and transactional revision checks.
- Four role-isolated private commitments, an atomic reveal barrier, cross-review, missing-seat continuation and retained history.
- Director concerns with all-seat acknowledgement, blocking/nonblocking disposition policy, pause/resume/cancel, dissent and transitive dependency reopening.
- Falsifiable hypotheses, expected/observed trade-offs, related-proposal suggestions, editable challenge groups, negative-result lookup and evidence-linked causal records/reframes.
- Typed local calculations, evidence import/identifier validation, human rubric review and bounded Token Factory trial/benchmark execution paths.
- Ordered exact-model routing, disabled optional DeepSeek, durable provider/mission spending reservations, whole-schedule holds, ambiguous-charge retention and rate-limit backoff without hidden retries.
- Optional OpenRouter free execution in the interface, frozen provider/model selection, a $0 allowance, separate ledger, per-mission/day attempt caps and provenance on real API evidence. Free missions cannot invoke Token Factory cost benchmarks.
- Four-cell paired analysis, task-cluster uncertainty, Pareto candidates, hard gates and honest rejected/inconclusive decisions.
- All eight requested vision views plus dependency navigation, raw artifacts, visible evidence classes, local director authentication and durable SSE updates.
- Escaped reports, complete registries, checksummed packs, offline numerical and decision-gate reconstruction, backup/restore, diagnosis, setup and credential-free release packaging.

## Demonstrated evidence

The seeded mission uses synthetic council text and a real deterministic calculation: 2,000,000,000 bytes / 100 decimal GB/s = **0.02 s (20 ms)**. Its evidence changes the interpretation and produces an approved **inconclusive** report. Unknown empirical quality, cost, latency and live confirmation gates remain unknown. No physical hardware was measured.

The browser acceptance test creates a fresh mission through the interface, freezes it, commits/reveals four seats, cross-reviews, creates/edits a challenge group, approves a local calculation, inspects raw evidence, records a scientific reframe, approves an inconclusive decision, downloads a pack and visits all research views. Desktop/mobile screenshots are visually reviewed. A separate backend suite covers concurrency, provider transport doubles, complete controlled schedules, partial-commit recovery, stale concerns, dependency invalidation, artifact/plan tampering, report escaping and backup/restore.

Validation evidence is stored in `docs/validation/`; commands and test sources are in the README and `tests/`. Transport doubles establish software behavior, not genuine NVIDIA runtime use. Clean-distribution setup and pack reanalysis are automated acceptance checks, not an independent human operator's evaluation.

An isolated **real OpenRouter free-model integration test also passed** using `nvidia/nemotron-3-super-120b-a12b:free`: four private schema-valid commitments, atomic reveal, four schema-valid cross-reviews and the deterministic 20 ms calculation. All eight calls reported $0. The four logical seats reused one actual model. This validates the software/model interface; research quality, performance improvement and target Token Factory acceptance remain unverified. The application has zero Token Factory inference calls and no Token Factory live billing authorization. See `docs/validation/openrouter-live-check.md` and `openrouter-smoke.json`. Earlier failed Super VL tests remain recorded.

The same real free-model loop passes through the research UI, including mission creation/freezing, reveal privacy, all four reviews, a numerical experiment, a scientific reframe, an inconclusive draft and pack download. Its eight additional calls reported $0. The draft awaits the actual human director; it does not claim an optimization result. The exported calculation and decision gates reproduce offline.

Council chat has fifteen base backend checks plus 22 resilience cases and a provider keep-alive deadline check. Six entry checks cover automatic local sessions, remote/cross-site refusal and locked billing. The latest full backend run passes 108 tests and the browser run passes six tests. The browser checks start without a session, cover direct prompt entry, quota preflight, the smaller-council option, visible retries and reduced participation, and preserve the research workflow. Retry counts and due times are durable; temporary free failures retry within limits, and persistent member outages can continue with at least two available members. Fewer than two stops honestly unless the director explicitly requests partial synthesis. Readiness claims from models do not shorten the configured discussion schedule. The chat is public-answer discussion, not hidden chain-of-thought collection or scientific verification.

The latest genuine conversation (`chat_304211b1c25846de`) completed after Xing recovered through queued waits and Lightning was declared unavailable during discussion. All three opening answers were retained, the two remaining members completed four debate turns and a labelled partial synthesis, and the human has not accepted it. Its 14 attempts include retained failed/unknown outcomes; successful responses reported $0. The account check afterward reported seven of fifty free requests remaining, with zero monetary usage. The local daily ceiling was then aligned to fifty without resetting counters. A fresh browser verified the smaller two-model/one-round setup can be selected with that allowance, without dispatching inference. Fresh credential-free installation, production build, all 108 backend tests and reproduction pass for the final source. See `validation/resilient-free-chat-live.json`, `final-free-ui-check.json` and [the reliability findings](validation/free-reliability-findings.md). Free hosting still cannot guarantee a complete council on demand.

The real chat `chat_5d5d8378ce454981` used Nemotron Super, Xing 4 and Nemotron Lightning through their distinct free model IDs. It retained three opening answers, six discussion turns, a director correction, the original synthesis and the revised synthesis. Eleven successful responses reported zero cost. One synthesis request returned HTTP 502; one explicit resume completed the missing turn without replaying saved replies, for twelve total attempts. A separate earlier Gemma attempt stopped on upstream shared-pool HTTP 429 and remains saved. The completed answer awaits the human director's review; its scientific recommendations are unverified. See [chat validation](validation/council-chat-check.md), `council-chat-live.json` and the screenshots. The preceding chat build passed fresh credential-free setup, build, its 78 backend tests and pack reproduction; its source hash is retained in `clean-setup.json`. The subsequent direct-entry change passes all 84 backend tests, the production build and all four browser tests, including a fresh browser against the actual local server. No inference was needed for the entry checks. See `direct-prompt-entry.json` and `direct-prompt-entry.png`.

## Requirement traceability

After a real opening hit the old 1,000-token cap twice, free-chat output ceilings were raised to 3,072 tokens per contribution and 4,096 per synthesis, with concise response targets. Paid Token Factory bounds were preserved. The saved OpenRouter credential was replaced and verified through a read-only account request. Explicit recovery produced a complete Nemotron reply (`finish_reason=stop`, 936 completion tokens, reported $0). Xing 4 then returned an upstream shared-pool HTTP 429; the run stopped with the recovered reply retained. No automatic model replacement or paid routing was used. See `validation/chat-output-recovery.json`; generated user prompt/reply text is not exported there.

| IDs | Implementation evidence | Remaining acceptance dependency |
| --- | --- | --- |
| Z01, Z08 | `contracts.py`, `db.py`, `service.py`; workflow/recovery tests | Live mission envelope and final human approval when ready |
| Z02–Z04 | Private council/exact-model adapter; pre-reveal artifact tests; successful read-only account catalog check | Four real submissions, current model billing/capability verification |
| Z05–Z07 | Typed cross-review, concerns, dispositions, dissent and hard-gate tests | Inspect real research usefulness; fixtures are not scientific evidence |
| Z09–Z13 | Hypothesis/negative memory, trade-offs, ranking, causal records, reframe contracts and memory tests | Genuine measured mechanisms/outcomes if claimed |
| Z14–Z16 | Authored 4/8 task split, hidden validators, counterbalanced schedule, comparisons and simulated complete benchmark tests | Affordable live pilot/confirmation; narrow any resulting claim |
| Z17-Z18 | Real local calculation; imported/measured/calculated provenance; raw artifacts; free-model council execution and trial transport tests | Target Token Factory execution remains locked |
| Z19–Z20 | Browser walkthrough, all views, portable pack verification/reanalysis | Additional user feedback and independent operator review |
| Z21 | Full local software loop plus a real free-model UI mission with a draft decision | Director review; disclosed-budget single-model comparison if feasible |
| Z22, O01–O03 | Integer reservations, schedule holds, process lock, privacy/integrity/recovery tests, backup/restore | Verify provider account-wide card/credit controls before live use |
| O04, H03–H04 | Runnable local distribution, license, setup/access instructions | Publish and verify free repository/test-build access through Dec 15 |
| H01 | Key/catalog access verified, genuine call path implemented | One real NVIDIA runtime trace, after billing verification |
| H02, H05, H10 | Actual local tools/evidence-driven reframe; English README/UI/reports | Demonstrate the same with real model research for final entry |
| H06–H09 | Demo script, description, actual-use feedback draft and disclosure/checklist | Human eligibility/disclosure review, public video and submission confirmation |

## Implementation choices and limits

- Each adapter dispatches once per call. Token Factory and controlled research execution retain explicit continuation without automatic retries. Free chat orchestration can queue at most two retries per turn and three per conversation, with every attempt separately recorded. Waiting jobs survive restart; in-flight work interrupted by a crash still requires explicit recovery. No JSON-repair loop or paid model fallback was enabled.
- Related-proposal suggestions use a local domain-concept/lexical cosine method, not learned embedding inference. The method and limits are exposed; suggestions never suppress work or authorize a result.
- Streaming and structured-output provider options are not assumed. JSON is validated locally, and non-streaming TTFT remains unknown. Capability probing remains a live acceptance action.
- The scientific benchmark timing boundary is per-task preparation through terminal validation, including escalation. Experiment queue wait is separately recorded in each run manifest.
- Rubric annotations must name actual reviewed evidence. Confirmation requires a complete current-revision live confirmation schedule plus all other hard gates. Small samples still support only bounded claims.
- Confirmation cost acceptance uses the lower task-cluster bootstrap saving bound against the frozen materiality threshold. A point estimate alone cannot confirm savings. Human quality review must cover the actual confirmation evidence, and a consumed held-out schedule cannot be rerun until it looks favorable.
- Fresh council contexts include prior revealed hypotheses, recorded reframes/trade-offs and decision memory. Current-round private submissions remain excluded.
- Reopening/concern changes preserve prior artifacts. Stale or cancelled private rounds can be included as metadata in a public pack, but their hidden answers/raw private artifacts remain excluded.
- Restoring a backup clears live authorization. Unresolved financial reservations survive. No generic 'forgive charge' control bypasses the ledger.
- There is no public multi-tenant deployment, learned semantic embedding service, streaming performance measurement, general causal-discovery engine, or executed optional hardware experiment in this candidate.

## Release gates

| Version | Local implementation | Release gate |
| --- | --- | --- |
| 0.1 | Scope/model policy, probe contract, task packets and protocol implemented | Pending billing verification and genuine NVIDIA probe |
| 0.2 | Persistence, authority, budget, queue, provider and UI implemented/tested | Pending real-call trace |
| 0.3 | Commit/reveal/privacy/partial recovery implemented/tested; real OpenRouter free round passes | Target Token Factory round and research-use evaluation remain |
| 0.4 | Governance, concerns, dissent/reopen implemented/tested | Local protocol passes; real-use validation remains |
| 0.5 | Memory, typed plans, trade-offs/ranking/maps implemented | Local capability-valid test passes |
| 0.6 | Local tools and guarded API execution implemented | Local tool passes; real API experiment pending |
| 0.7 | Metrics/gates/reframe/decision implemented/tested | Local loop passes; live research finding pending |
| 0.8 | Interface/reports/pack/reanalysis implemented/tested | Local browser/export gate passes |
| 0.9 | Recovery/integrity, setup, backup and local distribution implemented | Independent human and genuine live validation remain |
| 1.00 | Release package and submission materials prepared | Public links, video, human review and submission remain |

The detailed checkboxes in `plans/02_IMPLEMENTATION_PLAN.md` distinguish implemented/tested local work from live/external gates. A checked implementation item does not upgrade a pending version release gate. Optional X1 remains unstarted and creates no spending authority.
