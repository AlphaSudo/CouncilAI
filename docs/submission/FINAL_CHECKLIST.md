# Final release and submission checklist

Updated October 26, 2026. Implementation is frozen. [Demo video — 2:48](https://youtu.be/IOy6m_5ZwuM) · [Hosted app](https://web-mu-weld-26.vercel.app/) · [Testing guide](TESTING.md) · [Release status](RELEASE_READINESS.md).

## Published project

- [x] Publish the current council source at [AlphaSudo/CouncilAI](https://github.com/AlphaSudo/CouncilAI), with an MIT license and developer setup instructions.
- [x] Link the uploaded demo prominently in the README and submission documents; observe its 2:48 duration in the YouTube player.
- [x] Add a public testing guide that clearly states the hosted access code is required and distinguishes it from provider API keys.
- [x] Explain access for hackathon judges, invited testers and other visitors.
- [x] Correct stale statements that cloud deployment and video upload were still pending.
- [x] Record the October 26 release freeze and preserve a named submission snapshot.

## Working access and evidence

- [x] Deploy Vercel/Supabase with durable Postgres/private Storage and one coordinated worker.
- [x] Complete two real same-chat hosted cycles with collective search, originals and Storage checks; complete two further synthetic cycles after the availability changes.
- [x] Preserve saved conversations, originals, exports and the existing paid ledger across replacement deployments.
- [x] Pass 100 targeted local regressions and 27 Linux/Postgres integration checks for the availability release.
- [x] Verify actual Vercel cron HTTP 200 and a successful external GitHub runner check; activate daily and judging-period schedules.
- [x] Preserve the shared $24 cloud cap and $0 additional-payment authority; leave local paid inference disabled.
- [x] Keep provider keys, the actual access code and private runtime evidence out of the public repository.

## Entrant's Devpost handoff

- [ ] Put the actual production access code in the **private Devpost testing instructions**. The website requires it before a judge can proceed; the public README deliberately does not contain the code.
- [ ] Confirm the uploaded YouTube video's **Public** visibility and playback while signed out. Duration observed: **2:48**.
- [ ] Fill source, working-app, video and testing-instruction fields. A separate downloadable build is optional for this hosted submission.
- [ ] Select **Best Apps and Agents** and highlight collective research for **Best Use of Tavily** where applicable.
- [ ] Confirm entrant/team details, eligibility, ownership/permissions and any required development-period disclosure.
- [ ] Submit before **October 30, 2026, 17:00 UTC / 19:00 Cairo** and retain the confirmation.
- [ ] Retain the judged release and free testing access through **December 15, 2026, 20:00 UTC / 22:00 Cairo**.

Unchecked items are submission/account confirmations, not unfinished council implementation. This repository update does not assert that a Devpost entry has been submitted. [Official rules](https://nebiusglobalaihackathon.devpost.com/rules).
