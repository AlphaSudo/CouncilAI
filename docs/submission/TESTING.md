# Test ZeroWall

For hackathon judges and invited testers. Release frozen October 26, 2026.

| Link | Purpose |
| --- | --- |
| [Hosted council](https://web-mu-weld-26.vercel.app/) | Run the working application in your browser |
| [Demo video — 2:48](https://youtu.be/IOy6m_5ZwuM) | Watch the product demonstration |
| [Public source](https://github.com/AlphaSudo/CouncilAI) | Inspect the implementation and MIT license |

## Access code required

**You need the hosted council access code before you can proceed.** The login screen calls it **Access code**; deployment documentation also calls it the **director token**.

- **Judges:** the project owner must supply this code in the private Devpost testing instructions. Use that supplied code. If it is missing, contact the submitter.
- **Invited testers:** request the code from the project owner, [AlphaSudo](https://github.com/AlphaSudo).
- **Other visitors:** the video and source are public; the hosted council does not offer open self-registration.

Open the hosted link, enter the code and select **Open council**. No provider API key, cloud account, installation, credit card or purchase is required from a hosted tester. The code is a login credential, separate from model API keys and the token counts shown in usage cards.

This is a shared, single-director judging workspace. People with its code can see and control the same cloud conversations. Use sample questions and public documents when evaluating it.

## Suggested walkthrough

1. Select **New council** if a previous conversation is open. Keep the default three models and **Search On**.
2. Ask: **"Compare SQLite and PostgreSQL for a three-person note-taking app. Use web sources, explain the trade-offs, and recommend a practical starting design."** Select **Start council**.
3. Inspect **Shared research** and **Sources**: the models contribute search directions, Tavily searches run in parallel, and the retrieved material is pooled in one saved library.
4. Read the independent answers, challenges, author responses and final synthesis. Research and multi-model review take time; progress appears as the council runs.
5. Open **Compare** to read the three perspectives beside each other. Use **Inspect** to open a complete reply. **Conversation** returns to the chat.
6. Send a follow-up in the same chat: **"Now assume all three people edit notes concurrently from separate computers. What changes?"** Earlier replies and sources remain available.
7. Switch **Simple / Explain** to inspect execution details, source provenance and per-response/conversation usage. The thinking selector and context circle sit beside the send control.

The default models are NVIDIA Nemotron 3.5 Super VL (lead), Reflection Beam and DeepSeek V4 Flash 0731 through Nebius Token Factory. Real requests use the project's existing credit; testers are not asked to pay. Synthetic demo mode is explicitly labelled and is separate from live model execution.

## If something takes longer or fails

Keep the same conversation and read the saved progress/error message. Refreshing the page reconnects to saved state; it does not require starting a new chat. Public replies are saved before optional review annotations. Provider outages, quota limits and uncertain request outcomes can still affect a run; no paid request with an unknown outcome is automatically replayed.

The cloud schedules operate without the developer computer: daily availability checks, with additional hourly checks for November 30 and December 1–15. See the [availability runbook](../operations/JUDGING_AVAILABILITY.md) and [check results](https://github.com/AlphaSudo/CouncilAI/actions/workflows/judging-availability.yml). Free hosting has no uninterrupted-uptime guarantee.

## For the submitter

Copy the hosted URL, video URL, source URL and **actual production access code** into the Devpost testing instructions before submitting. The production code is the existing `ZEROWALL_DIRECTOR_TOKEN` in Vercel's Production settings and the private `.env.cloud` file. Do not publish that value in GitHub, the video or the public project description. The rules require credentials for a private website and free testing access through the end of judging. [Official testing requirements](https://nebiusglobalaihackathon.devpost.com/rules)
