# Frozen hackathon release — October 26, 2026

The current council implementation is frozen for judging. This final update adds the uploaded demo, tester instructions and an accurate release handoff. No runtime code, provider configuration or spending authority is changed.

## Entry points

- [Hosted ZeroWall council](https://web-mu-weld-26.vercel.app/) — **access code required**.
- [Demo video](https://youtu.be/IOy6m_5ZwuM) — observed duration **2:48**.
- [Public source and MIT license](https://github.com/AlphaSudo/CouncilAI).
- [Instructions for judges and invited testers](TESTING.md).
- [Frozen submission snapshot](https://github.com/AlphaSudo/CouncilAI/tree/hackathon-2026-10-26).

## What is ready

The default Token Factory lineup is NVIDIA Nemotron 3.5 Super VL (lead), Reflection Beam and DeepSeek V4 Flash 0731. Collective Tavily research, pooled sources, independent openings, answer-first review, synthesis and same-chat follow-ups are implemented. Simple/Explain, Compare, original-response inspection, copy/edit, thinking controls, context compaction and usage accounting remain available.

Production runs independently of the developer computer: one Vercel web Service and council-worker Daemon, Supabase Postgres and private Storage. Actual hosted acceptance included two real same-chat cycles with collective research, source/original/export persistence and private Storage round trips. Two further synthetic cycles and replacement-deployment checks passed. See [production acceptance](../operations/PRODUCTION_ACCEPTANCE.md).

The availability release passed **100 targeted local regressions** and **27 Linux/Postgres integration checks at 1 GiB**. The final Vercel cron test returned HTTP 200 and the [GitHub cloud check passed](https://github.com/AlphaSudo/CouncilAI/actions/runs/40242150946). Daily checks and additional hourly checks for November 30–December 15 are active. See [availability and recovery](../operations/JUDGING_AVAILABILITY.md). These checks do not make model or Tavily calls and do not guarantee future provider uptime.

The public repository includes lockfiles, local setup instructions and an MIT license. The hosted application supplies the working-test URL; a separate downloadable build is optional for this route. Raw private histories, credentials and runtime artifacts stay outside Git. Model-quality superiority is not claimed.

## Testing access

Judges and invited testers enter the **Access code**, also called the **director token**, then select **Open council**. The code must be supplied privately with Devpost testing instructions. No provider API key, cloud account or payment details are required from a hosted tester. This is a shared single-director workspace, not isolated accounts per visitor.

The cloud retains its explicitly authorized $24 aggregate existing-credit allowance and $0 additional-payment authority. That allowance is shared; deployment and visitors never reset it. Local paid inference remains disabled. Provider credits, Tavily quotas and free hosting limits are separate; actual availability can still vary.

## Submission handoff

The repository update does not submit a Devpost entry. The entrant still needs to:

1. Put the hosted URL and actual production access code in the **private testing instructions**, alongside the source and video links in their relevant fields.
2. Confirm the YouTube video is **Public** and plays while signed out. Its player reports 2:48; this check does not certify footage, rights or platform visibility settings.
3. Complete entrant/team, eligibility, ownership and development-period declarations, select the track, and submit the entry.

The proposed primary track is **Best Apps and Agents**; collective research is the feature highlighted for **Best Use of Tavily**. These are entry recommendations, not claims of an award.

The [official rules](https://nebiusglobalaihackathon.devpost.com/rules) list the submission deadline as **October 30, 2026, 17:00 UTC / 19:00 Cairo**, and judging through **December 15, 2026, 20:00 UTC / 22:00 Cairo**. Preserve the submitted snapshot and free judge access through that period. No additional project implementation is planned.
