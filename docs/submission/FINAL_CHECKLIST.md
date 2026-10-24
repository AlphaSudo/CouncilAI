# External release and submission checklist

Updated October 24, 2026. See the [release/hosting assessment](RELEASE_READINESS.md) and [2:50 video script](DEMO_SCRIPT.md). Checked boxes describe the stated software/publication evidence, not a submitted hackathon entry.

## Local baseline

- [x] Current default lineup is Nemotron Super VL (lead), Reflection Beam and DeepSeek V4 Flash 0731 on Token Factory.
- [x] Search On, collective Tavily research, shared sources, Simple/Explain, Compare, thinking selection and context display are implemented.
- [x] Public-answer preservation and recoverable annotation handling are implemented.
- [x] Root MIT license and third-party notices exist.
- [x] Local records include completed Token Factory calls for the current three models, including NVIDIA Nemotron. No new inference was dispatched for this assessment.
- [x] Recent regression register records 96 backend and 28 browser cases; the subsequent navigation cleanup passed its focused browser case and build.
- [x] Submission description and video draft now describe the current council rather than the legacy experiment workspace.

## Release candidate and repository

- [ ] Choose one complete genuine council and one same-chat follow-up; inspect every shown answer, source and synthesis.
- [ ] Select scrubbed Token Factory receipts and actual Tavily query/extraction evidence for that run.
- [x] Audit the Git publication set for configured secrets, credential patterns and private/generated files; exclude local data, internal screenshots and runtime traces. Third-party notices are included. Raw demo receipts/footage still need their own audit before publication.
- [ ] Replace credentials previously exposed in chat before external deployment; keep replacements only in local/server secrets.
- [ ] Refresh the source/test-build archive and checksums; inspect its contents before publication.
- [ ] Verify setup, demo mode, assets, tokenizers and instructions from a fresh extraction without existing data.
- [x] Publish the first reviewed Git commit and configured remote under [AlphaSudo/CouncilAI](https://github.com/AlphaSudo/CouncilAI), on `main`, initial commit `e5b3d98`.
- [x] Check the repository and setup instructions signed out (HTTP 200) and confirm GitHub reports MIT.

## Working access and budget

- [ ] Choose a downloadable test build or appropriately persistent hosted application. A static-only page is not the current live backend.
- [ ] Provide setup/login/testing instructions permitting free judging access through December 15, 2026.
- [ ] Confirm usable credit and expiry extend through judging, or arrange funded access without additional personal payment. Historical trial screenshots do not prove December availability.
- [ ] Preserve the $24 aggregate cap and $0 additional-payment rule; do not reset the allowance for a deployment or visitor.
- [ ] If hosting: configure public hosts/origins, HTTPS cookies and explicit remote authentication. Ensure a loopback proxy cannot grant visitors a local director session or expose private conversations/paid controls.
- [ ] If hosting the current backend: persist SQLite/financial state, artifacts, sources and tokenizer assets; retain one executor per data directory and test restart/recovery.
- [ ] Test final access outside the developer browser session. Label any saved replay; do not imply it supplies fresh inference.

## Entry and video

- [ ] Select **Best Apps and Agents**; highlight collective research for **Best Use of Tavily** where the form permits.
- [ ] Finalize the description with a real example, architecture, platform use, limits and observed feedback.
- [ ] Record and upload the English video as **Public** on YouTube below three minutes; verify duration and signed-out playback.
- [ ] Entrant confirms eligibility, representation, ownership/permissions and development-period disclosure.
- [ ] Fill required fields with the public source, working access, video and testing instructions.
- [ ] Submit before **October 30, 2026, 17:00 UTC / 19:00 Cairo**; preserve confirmation. Aim for October 29 to allow final checks.
- [ ] Retain the judged release and free testing access until **December 15, 2026, 12:00 Pacific Time**.

Dates and requirements were checked against the [official rules](https://nebiusglobalaihackathon.devpost.com/rules). Runtime calls to Token Factory satisfy the platform-use definition; a separate Nebius GPU deployment is not required.
