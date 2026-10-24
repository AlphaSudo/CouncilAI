# Hosted production acceptance — October 24, 2026

Production: [ZeroWall council](https://web-mu-weld-26.vercel.app/).

The operator activated a **fresh $24 cloud cap**, explicitly requested by the user instead of importing local spending. This is a new authorized spending scope, not an automatic reset caused by deployment. Local Token Factory authorization is disabled. Previous charges, uncertain outcomes and private conversations remain in the local database and its verified backup; they were not imported or deleted. Additional-payment authorization remains $0. The previously reported provider balance is historical, not a fresh balance or card-settings verification.

## Observed hosted checks

| Check | Result |
| --- | --- |
| Actual root Docker build on Vercel Hobby | Passed: one web Service and one council-worker Daemon in iad1 |
| HTTPS API health/readiness | HTTP 200 |
| Hosted access code, refresh and logout | Passed; Secure, HttpOnly cookie; local auto-entry disabled |
| Supabase session pooler and worker ownership | Passed; TLS, port 5432 and an exclusive worker lock |
| Synthetic council with same-chat follow-up | Both review cycles completed, including final synthesis |
| Actual private Storage | Upload/mirror/download hash checks passed; all 85 stored files mirrored when checked |
| Source import, all saved originals, review ZIP download | Passed |
| Live events through Vercel | Received text/event-stream and an event record |
| Current real models | Nemotron Super VL, Reflection Beam and DeepSeek V4 Flash 0731 |
| Real collective web research | Passed; sources and page content saved to the shared library |
| Real council with same-chat follow-up | Both completed, with 6 independent answers, claims, scrutiny, 5 applicable author revisions, 2 rechecks and 2 final syntheses |
| Prior-turn preservation | Earlier message payloads remained identical after the follow-up; all 19 public replies remained readable through the original-response endpoint |
| Current context and thinking controls | 262,144 tokens; Quick, Balanced, Deep and Maximum available |
| App spending guard | Above-cap reservation refused before any model request |
| Live request outcomes | 27 attempts with reported token usage; no unknown outcomes |

## Test usage

The two real cycles reported 388,687 input tokens and 56,190 output tokens, including 36,496 reasoning tokens. Cache-read input was 1,600 tokens. Provider cache-write usage was not reported. These observations do not imply an output/reasoning cap was changed for the test.

The tariff-based UI estimate was $0.13503314. The conservative integer-microdollar ledger counted **$0.13533**, leaving **$23.86467** under the fresh $24 cloud cap. These are application accounting amounts, not a provider invoice. There were no reserved/unknown amounts or active jobs when checked. Research recorded 19 tool invocations and 21 external-credit reservations, without unknown tool outcomes.

Tavily's `/usage` quota-check endpoint returned HTTP 429 during some later requests. Five search invocations were blocked before dispatch; models continued using the shared saved sources and both cycles completed. This is an observed provider-limit degradation, not a claim that every per-reply search succeeded.

Optional review annotations produced warnings without interrupting public model answering. They are not certified scientific findings. No forced timeout, provider failure or paid-request replay was introduced into the live test; uncertain-outcome recovery remains covered by the separate integration tests.

## Replacement deployment check

The operator records immutable message hashes and an export hash before replacing the deployment, then checks the same original replies, export, remote spending totals and worker ownership afterward. The private local acceptance report holds those hashes and the result; it is excluded from Git along with screenshots, credentials and raw runtime records. This check makes no further model requests.

## Remaining release work

Judge-access instructions and funded access through judging, free-plan quota monitoring, video/demo selection and final submission remain release tasks. A basic hosted acceptance check does not certify unlimited traffic or guarantee future provider availability. Redeployments must keep the current database and allowance; no fresh initialization may run on startup.
