# ZeroWall Budget and Access Constraints

**Updated:** October 18, 2026.  
**Authority:** the director confirmed a $25 maximum from existing Token Factory credit, $0 additional personal payments, and Token Factory inference as sufficient for the core. Free hardware experiments may be considered later if needed.

This replaces the earlier pending-GPU prerequisite. No self-managed GPU, AI Cloud account, GPU rental, SSH key, cloud IAM credential, free notebook, or local inference stack is required to begin or finish the core releases.

## 1. Confirmed financial authority

| Item | Authorized maximum | Rule |
| --- | --- | --- |
| Existing Token Factory credit | $25 aggregate | Count probes, all researcher calls, retries, repairs, experiments, and demonstrations. |
| Additional personal payments | $0 | No top-ups, deposits, subscriptions, overage, or paid upgrades. |
| Paid cloud resources | $0 | No compute, database, storage, or networking purchase. |
| $1 trial entry | No increase to the $25 cap | Verify its source/expiry separately; do not assume a $26 authorization. |
| Partner credits | Optional and service-specific | No LangSmith/Tavily/Toloka integration or payment is a prerequisite. |
| Optional later hardware experiment | $0 resource charge | Only genuinely free compatible access; absence does not block the core. |

The earlier '25%' wording was clarified as **$25 maximum**, not $6.25. Budget against verified remaining credit and existing usage, not just a planned number of calls.

## 2. Current readiness

| Item | Status |
| --- | --- |
| Devpost | Joined, as reported by the director. |
| Token Factory | Ready; $1 trial and $25 balance reported. Credit source, expiry, and overage behavior still need verification. |
| Project | Keep `default-project`, ID `aiproject-e00ptxgc6a0vsj3zdn`. A new project is optional. |
| API key | Nonempty local entry confirmed without displaying it; validity and runtime access remain untested. |
| GitHub | Username `AlphaSudo`; local authentication/repository setup remain implementation tasks. |
| Local application | Runs on the existing workstation; implementation has not started. |
| AI Cloud, SSH, GPU quota | Not required for the core and not a readiness blocker. |

These entries are user-reported, not a live account audit. No account login, inference call, resource provisioning, or credit redemption occurred while recording the plan.

## 3. Prerequisites for live Token Factory calls

The billing guide describes automatic card charging when a negative balance is settled or a billing threshold is reached. A positive displayed balance is not a provider-enforced no-overage guarantee. Promo-code credit can be checked in Transactions. [Token Factory billing](https://docs.tokenfactory.nebius.com/other-capabilities/billing-new)

- [ ] Verify that the $25 entry is existing promotional/authorized credit and record its expiry and remaining amount.
- [ ] Check account paid-usage/overage controls; do not treat an alert or billing threshold as a hard stop.
- [ ] Establish a credit-only/no-overage configuration if supported, or obtain provider clarification if account-wide protection is unclear.
- [ ] Preserve the existing local API key without exposing or committing it; verify validity only through the bounded feasibility flow.
- [ ] Verify model prices, all billed token categories, and bounded input/output settings before request dispatch.
- [ ] Build durable aggregate cost reservations and a below-$25 operational stop before routine calls.
- [ ] Count concurrent requests and every retry/repair/escalation attempt before dispatch.
- [ ] Keep full reservations for ambiguous/time-out charges until reconciled; do not assume no response means no charge.
- [ ] Reconcile usage from other keys and manual Playground activity drawing on the same credit.
- [ ] Refuse new live calls if maximum possible cost or remaining authority cannot be established.

Application controls reduce overage risk but do not establish provider-wide billing behavior. Do not promise zero new account charges based solely on an application counter. Until the billing prerequisites are clear, use offline fixtures for development.

## 4. Local application and core experiment path

Run the Python API, research database, local executor, deterministic tools, React interface, and evidence storage on the existing workstation. Token Factory hosts the NVIDIA models. No model download or rented machine is needed.

All required model requests pass through the same budget-controlled router. Registered local tools perform calculations, source/evidence checks, artifact analysis, and experiment comparisons. Core tests measure request strategy, evidence validity, actual output, API/workflow latency, token usage, and attributable cost.

The [model selection policy](06_MODEL_SELECTION.md) fixes the director's order and disables optional DeepSeek. Public price references are recorded, but model order alone does not enforce the $25 cap.

Calling an NVIDIA open model through Token Factory meets the event's platform requirement without also hosting the app on AI Cloud. [Official hackathon FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs)

The scope does not claim control of the provider's hardware, scheduler, kernels, precision, power, or memory behavior. A remote model's answer about those mechanisms is a research hypothesis, not a new measurement.

## 5. Optional extension X1 free hardware experiments

Once the core works, consider free Kaggle/Colab or borrowed compatible hardware only if it would strengthen the research case and time permits. Verify actual access, hardware, quota, packages, permitted use, and session limits. Availability is not guaranteed. [Kaggle documentation](https://www.kaggle.com/docs/notebooks), [Colab FAQ](https://research.google.com/colaboratory/faq.html)

Use the provider's supported interactive notebook workflow, export checksummed measurements, and import them into ZeroWall with provenance. Colab's free tier restricts remote-control/distributed-worker usage; do not convert it into an SSH server or always-on backend. [Colab restrictions](https://research.google.com/colaboratory/faq.html)

The separate [optional memory-wall protocol](optional/04_MEMORY_WALL_GPU_PROTOCOL.md) applies only if this work is selected. Missing telemetry stays unknown. No paid upgrade, card deposit, allocation, or mandatory signup is authorized. If unavailable, leave X1 unstarted and release the core normally.

## 6. Budget allocation and release consequences

Before the first live run, allocate the existing credit across development probes, council iterations, core experiment/confirmation calls, and demonstrations. Preserve a reconciliation reserve and stop below the absolute $25 cap. Exact allocations depend on verified model prices and remaining balance; the plan does not promise a specific number of sessions for $25.

Fixtures and saved genuine runs support development/replay. They are labeled and do not satisfy a real runtime-call or executed-experiment gate.

Core version 0.1 now checks Token Factory and local/API experiment feasibility. The former mandatory cloud-GPU requirement Z17 is explicitly replaced by local/API execution provenance. No core gate remains pending free GPU access.

Public judging access or functioning test-build distribution remains a release task. Choose and verify a free approach before submission, preserve the tested release, and document the access limits. Do not silently assume paid hosting through the judging period.

## 7. Immediate next actions

1. Keep the existing Token Factory project.
2. Verify the credit source/expiry and account overage controls.
3. Preserve the saved local key and apply the director's ordered model policy.
4. Implement the budget guard and local council foundation.
5. Complete the core before deciding whether optional hardware measurements add enough value.
