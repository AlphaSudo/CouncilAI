# ZeroWall Core Research and Measurement Protocol

**Scope October 18:** required model inference is served by Token Factory. Experiments use the hosted API and registered local tools. No self-managed GPU, free notebook, AI Cloud resource, local model weights, or inference engine is required.

This protocol replaces the earlier mandatory hardware protocol. The [optional memory-wall protocol](optional/04_MEMORY_WALL_GPU_PROTOCOL.md) remains available for a later genuinely free experiment. Do not apply its hardware metrics to hosted API observations.

## 1. First measurable mission

**Mission:** evaluate the cost, latency, and evidence quality of a hosted research workflow.

**Question:** can a supported combination of context packing and model-routing policy reduce the cost of producing a valid research result while preserving required facts, constraints, citations, and useful scientific reasoning?

The council still reasons across hardware, runtime, inference, and model/algorithm perspectives. The measured intervention in this mission is at the application/context/model-selection layers. Provider hardware, kernels, memory bandwidth, power, and engine scheduling remain unobserved.

The memory wall can be the subject of a task/source packet. A model's proposed memory explanation or a local roofline calculation remains a hypothesis/calculation unless supported by a real appropriately sourced measurement. This preserves the larger research direction without claiming unavailable experiment controls.

## 2. Evidence classes and claim ladder

| Evidence class | Meaning |
| --- | --- |
| Measured API | Actual request/response times, returned output, usage metadata, failures, and attributable cost. |
| Calculated | A registered deterministic calculation from declared inputs, units, formulas, and assumptions. |
| Imported | An external artifact with recorded source, timestamp, provenance, and unchanged raw content. |
| Inferred | A proposed mechanism explaining an observation but not directly established by it. |
| Untested | A hypothesis without a discriminating executed test. |
| Fixture/replay | Synthetic development input or a saved genuine run, explicitly labeled. |

Claims can progress from an observation, to a supported hypothesis, to a bounded finding on the declared tasks, and then to a broader confirmed result only if independent evidence and sample precision support it. Negative and inconclusive findings are valid outcomes.

A small pilot does not prove general research quality or multi-model superiority. A client latency improvement does not prove a provider kernel, scheduler, or hardware improvement.

## 3. Frozen operating envelope

| Field | Freeze requirement |
| --- | --- |
| Provider | Exact Token Factory endpoint and available model IDs; record reported version metadata or explicitly unknown version. |
| Credit controls | Verified existing credit, account overage behavior, $25 aggregate authorization, below-cap operational stop, and reservation rules. |
| Prices | Timestamped per-model price source and every billed token category used to bound requests. |
| Client | Host/runtime, adapter version, clock source, network path, timeout, client concurrency, retry policy. |
| Task/source packet | IDs, hashes, license/provenance, all model-visible instructions, and separate hidden evaluation data. |
| Context treatment | Packing algorithm/version, source-ID preservation, token limits, and fact/constraint coverage checks. |
| Model routing | Fixed strong-model baseline, fast model, escalation rules, maximum attempts, and per-route request bounds. |
| Request settings | Supported sampling/output/format parameters; record unsupported options rather than inventing them. |
| Objective | One primary metric, normally cost per valid task; quality/validity gates and secondary latency metrics. |
| Trial design | Matched tasks, repeat/order schedule, live-call budget, missing/invalid rules, and confirmation set. |
| Approval | Director-approved mission/protocol revision before comparison and candidate confirmation. |

Exact permitted model IDs and priority are recorded in [Model selection](06_MODEL_SELECTION.md). Account access, current billed prices/categories, task counts, and materiality targets still need bounded feasibility verification. Do not buy access, silently use an unlisted model, or enable optional DeepSeek to resolve a blocked experiment.

## 4. Four-cell experiment

### 4.1 Factor A context packaging

Compare a clear full source packet with a deterministic structured representation that removes duplicate boilerplate and preserves every required source fact, constraint, source ID, and output instruction. Packing cannot use hidden answers or selectively omit difficult requirements.

This tests token/context overhead and evidence organization. It does not test model weight quantization or physical memory traffic.

### 4.2 Factor B routing policy

Default execution preserves the director's ordered allowlist. An explicitly approved comparison can contrast one fixed allowed model with a bounded fast-first policy using only the enabled allowed models. The treatment and any departure from default selection priority must be visible in the experiment plan. The policy can escalate under fixed format, citation-presence, uncertainty, or incomplete-output checks that do not see hidden answer keys; optional DeepSeek remains excluded while disabled.

Evaluate fast answers that pass the routing checks with the same hidden final validators as other outputs. A fast response that looks well formed but is factually wrong is a real policy failure, not a trial to discard. Count both calls and all latency/cost when escalation occurs.

| Configuration | A | B | Scientific question |
| --- | --- | --- | --- |
| C00 baseline | Full clear source packet | Fixed strong model | What is the valid-task cost and latency of the normal supported workflow? |
| C10 A only | Structured packed packet | Same fixed strong model | Does packing preserve evidence quality while reducing billed context? |
| C01 B only | Same full packet | Fast-first bounded escalation | Does routing save cost or introduce quality/extra-call overhead? |
| C11 A+B | Same structured packet | Same fast-first policy | Does packing alter the routing trade-off or escalation rate? |

Keep non-treatment settings fixed. Model identity changes are part of B and must be disclosed. Do not turn the baseline into an intentionally confusing prompt or remove normal supported functionality to create a weak comparison.

Up to two refinements can follow exploration if they have a falsifiable hypothesis and fit the remaining authorized credit. A larger search space is not required.

## 5. Task and sample design

Start with a small pre-budgeted pilot, for example four exploration tasks and up to eight separate confirmation tasks if the verified request costs permit. Each task includes inspectable sources and a question requiring evidence-backed reasoning or a declared calculation. Freeze task counts and repeat counts before dispatch.

Useful task categories include testing a claimed limit against its assumptions, identifying a confounder in an experiment, calculating a bound with units, detecting contradictory supplied measurements, and choosing a discriminating next test. These are research tasks, not a return to the rejected AgentProof product.

For each task store:

- Model-visible source packet and IDs, required constraints, and output schema.
- Hidden expected facts/calculations/citation mapping and a director-approved scoring rubric.
- A mapping proving the packed packet preserves required information without exposing the answers.
- Exploration/confirmation split and hash before candidate tuning.

Use paired tasks and a balanced/randomized configuration order. Keep client concurrency low and fixed initially to bound cost and reduce load confounding. Account for day/time, network variability, caching where observable, rate limits, and unavailable provider revisions.

Run repeated trials only when the full maximum cost is reserved. If the credit budget cannot support adequate confirmation, report a descriptive pilot with its limitations rather than claiming statistical proof.

## 6. Hypothesis and trade-off contracts

Every hypothesis states mechanism, affected layers, predicted signature, baseline/control, experiment, rejection rule, and unknowns.

```yaml
id: HYP-001
question: Does context packing change the fast-first routing trade-off?
affected_layers: [application_context, model_selection, orchestration]
prediction: Packing reduces billed input without new required-fact failures.
experiment: EXP-001
controls: [same_task, same_sources, same_output_contract, same_route_rules]
required_evidence: [raw_responses, usage, routing_events, validator_results]
kill_rule: Reject if required evidence quality regresses or savings vanish.
unknowns: [provider_internal_mechanism]
```

A trade-off card compares expected and observed benefits, hidden costs, residual disadvantages, mitigations, implementation complexity, and operating limits. Useful discoveries include a failed cost-saving policy, extra escalation overhead, a context/route interaction, and a better feasible operating point. Do not force the experiment to produce synergy.

## 7. Metrics

### 7.1 Primary cost per valid task

```text
attributable_call_cost = billed_input_cost + billed_output_cost
                        + other_verified_billed_categories
workflow_cost = sum(all_attempt_costs_including_repairs_and_escalations)
cost_per_valid_task = total_workflow_cost / number_of_valid_completed_tasks
```

If no task is valid, the ratio is undefined/unusable, not a zero-cost success. Report total spend and valid/attempted counts next to the ratio so selective success cannot hide failures.

Use returned usage where available. If exact billing is unknown, preserve the maximum reservation and report estimated/unknown cost distinctly. Account for all retries, cancelled requests, escalation calls, and potentially billed timeouts. Do not treat missing usage as free.

### 7.2 Workflow latency

```text
workflow_latency = terminal_result_time - task_start_time
request_TTFT = first_nonempty_output_time - request_send_time
request_latency = final_output_time - request_send_time
```

Workflow time includes client preparation, queueing, retries, and escalations under the frozen boundary. Store per-request times separately. If streaming chunks contain multiple tokens, report inter-chunk timing rather than claiming true per-token P99 latency. Non-streaming endpoints cannot provide measured TTFT from a final-response timestamp alone.

Keep timeout and rate-limit outcomes in the task result. Do not compare the latency of only successful fast tasks against all baseline tasks without disclosing the censoring policy.

### 7.3 Evidence validity and quality

Deterministic checks cover schema, source IDs, citation support where the task has a known mapping, required constraints, correct units, expected numerical results, and prohibited unsupported conclusions.

Human rubric review can score useful mechanism, falsifiability, confounder coverage, and the proposed next experiment. Freeze the rubric, keep model identity hidden from the reviewer where practical, and store actual annotations. LLM judging can be supplementary but consumes the same budget and does not override factual validators.

Track newly failing required cases relative to baseline, not just average prose scores. A quality finding is limited to the declared task/rubric set.

### 7.4 Secondary metrics

Request count, billed input/output, escalation rate, repair rate, valid-task rate, total human review effort, client-observed latency, and complexity. Provider hardware memory, energy, bandwidth, kernel time, and engine scheduling are outside this core measurement surface.

## 8. Gates and verdicts

The following are proposed defaults to freeze after the initial probe:

| Gate | Acceptance rule | Insufficient evidence |
| --- | --- | --- |
| G01 Credit authority | Settled plus reserved/unknown maximum charge stays within the operational allowance and absolute $25 authorization. | Block dispatch. |
| G02 Validity | No new failure of required facts, constraints, units, or citation checks on declared baseline-passing cases. | Unknown or fail according to missing collection versus actual invalid output. |
| G03 Quality | Meet the frozen rubric and non-regression rule on the declared task set. | Inconclusive; no broad preserved-quality claim. |
| G04 Cost objective | Achieve the frozen material saving in cost per valid task, initially considering 10% if price/pilot precision supports it. | Descriptive pilot or inconclusive result. |
| G05 Latency guard | Stay within a director-frozen complete-workflow latency/SLO rule; include escalation/retry costs. | Inconclusive if precision or timing coverage is inadequate. |
| G06 Integrity | Matching task/treatment/protocol versions, raw artifacts, all attempts, and complete planned blocks. | Invalid comparison or incomplete finding. |

Pass/fail/unknown/invalid are separate states. Required failures reject a confirmed candidate. Unknown required gates block confirmation. The director may approve an honest report without turning an unknown or rejected result into a passing optimization.

For a small pilot, use a bounded statement such as 'met the observed checks on these tasks' and disclose sample size. A statistically stronger benefit requires independent confirmation with adequate intervals and predeclared contrasts; do not relabel an underpowered pilot to satisfy a release gate.

## 9. Comparisons and interactions

For each paired task/block, calculate actual cost and latency differences/ratios with valid-result indicators. Keep task/attempt identity. Resample at the independent task/block level if the sample supports uncertainty analysis; correlated events inside one response are not independent observations.

Predeclare the interaction scale. For positive comparable cost values, one option is:

```text
cost_interaction = log(C11) - log(C10) - log(C01) + log(C00)
```

Negative cost interaction indicates a combined cost below the multiplicative no-interaction expectation, subject to valid-task quality gates. Latency interaction needs its own declared scale. Do not mix additive and multiplicative definitions after seeing the results.

A combination beating baseline alone is not proof of synergy or superiority over each single factor. Disclose uncertainty, multiple comparisons, and the limited search space. With insufficient samples, describe an apparent interaction as exploratory.

Construct a Pareto comparison only among valid comparable candidates, retaining quality/cost/latency uncertainty and residual cons. A weighted preference score may rank feasible choices but cannot compensate for a failed gate.

## 10. Local numerical and imported-evidence experiments

Use registered calculations and validators with typed inputs, fixed formulas, units, limits, and no unrestricted code execution from model text. Examples include comparing candidate evidence tables, recomputing paired effects, and calculating a stated resource bound from supplied values.

For imported measurements, preserve original artifacts, provenance, extraction method, and source scope. Record transformations and checksums. Do not make a live-execution claim merely by importing someone else's result.

A calculation may falsify an arithmetic or assumption claim; it does not establish new physical performance. The source's 273/230 GB/s illustration is explanatory, not a new measurement in this project.

## 11. Reframe and stopping

After each experiment ask:

1. Which predicted signature appeared, failed, or remained unknown?
2. Did a local benefit improve the complete task outcome?
3. Which quality, cost, latency, or complexity trade-off changed?
4. What alternate mechanism still fits the evidence?
5. Which next experiment best distinguishes the remaining explanations?

Reframe on failed transfer, surprising costs, repeated low-information proposals, changed constraints, or director instruction. Store a changed hypothesis/causal map/next action, not merely a summary.

Proposed limits are two structured review passes per round, no more than three full rounds before director review, a small fixed trial schedule, and no new work beyond the reserved budget. The budget constraint is binding even if the scientific question remains unresolved.

## 12. Council usefulness and reproducibility

Assess the council separately from the request-strategy optimization. Compare against a strong single-model research prompt under disclosed task, evidence, tool, call, and dollar budgets when feasible. Score actual falsifiability, control validity, trade-off coverage, unsupported claims, and useful next tests. One mission is a case study, not general superiority evidence.

The pack contains mission/protocol/task hashes, model/endpoint/price metadata, raw calls/tool results, timing/usage/routing records, reservations/settlements, validators, human annotations, gates, all exclusions, decisions, dissent, and limitations.

Support offline hash verification and complete numerical reanalysis without a provider key. A fresh live rerun is optional, consumes credit, requires local credentials and budget checks, and may differ because hosted service behavior is not pinned by the application.

## 13. Optional later hardware work

After the core works, a genuinely free Kaggle/Colab or borrowed compatible GPU can support the separate [memory-wall protocol](optional/04_MEMORY_WALL_GPU_PROTOCOL.md). Verify access, package support, allowed usage, and measurement limits first. Run through its supported interactive workflow, import real evidence, and preserve unknown telemetry.

This extension is not a dependency of the council, API mission, local tools, reports, or release 1.00. Without it, hardware-level proposals remain hypotheses and the project reports the actual API/local findings.
