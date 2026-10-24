# Optional Memory Wall Experiment Protocol

**Optional extension X1, October 18:** this hardware experiment is outside the core 0.1-1.00 release gates. Consider it after the Token Factory council works, using a verified free Kaggle/Colab notebook or another explicitly free compatible resource. No paid GPU, paid cloud project, deposit, or personal payment is authorized. Missing access does not block ZeroWall's core release. See [Budget and access constraints](../05_BUDGET_AND_ACCESS.md).

This protocol defines how the first ZeroWall mission becomes a falsifiable engineering investigation. The thresholds and workload values below are **proposed starting defaults**. The optional experiment must calibrate and freeze them with director approval before candidate confirmation. None is a claim about an experiment already performed.

## 1. Mission and scope of claims

**Mission:** Breaking the Memory Wall in LLM Inference.

**Research question:** can a controlled combination of reduced weight traffic and engine/runtime scheduling improve end-to-end inference performance without unacceptable quality, correctness, memory, tail-latency, or energy regressions?

The investigation considers four routes: recovering unused effective bandwidth, reducing bytes moved per token, increasing useful work per pass, and eliminating unnecessary movement. The first release implements a small supported subset. It records untestable routes as blocked hypotheses rather than inventing evidence.

The numbers 273 GB/s and 230 GB/s in the source notes explain a question about limits. They are not the selected GPU's specification or baseline. The actual mission starts with a fresh device inventory and method-specific measurements.

The scientific claim ladder is:

1. **Observation:** a measured difference exists in the recorded trials.
2. **Supported hypothesis:** a predicted signature survives a discriminating experiment within the stated envelope.
3. **Validated configuration finding:** a candidate passes the preregistered end-to-end and guardrail checks on independent confirmation data.
4. **Breakthrough candidate:** a validated finding has a useful cross-layer mechanism and a defensible improvement over strong measured alternatives.
5. **Broader novelty or generality:** requires additional literature, hardware/workload replication, and independent evidence beyond this MVP.

ZeroWall must be able to finish at levels 1 or 2, or with a negative/inconclusive result. It does not promise a globally novel discovery within the hackathon.

## 2. Operating envelope to freeze

| Field | Initial plan | Freeze requirement |
| --- | --- | --- |
| Compute | One verified free notebook GPU or another explicitly free compatible resource. | Actual GPU identity, VRAM, session limits, sharing/isolation limitations, and provenance. |
| Software | Linux, pinned CUDA/driver-compatible vLLM container. | OS, driver, CUDA, engine release, image digest, and launch arguments. |
| Model | One open dense decoder family around 3B-8B parameters, sized to the available GPU. | Full-precision and quantized checkpoint revisions, shared provenance, tokenizer, and licenses. |
| Parallelism | One device, tensor parallel size 1. | No hidden change in replicas, offload, partitioning, or parallelism. |
| Primary workload | Decode-heavy fixed-length generation with continuous fixed concurrency. | Prompt/request trace, tokenizer-derived lengths, arrival policy, output policy, and hashes. |
| Starting performance settings | Concurrency 4, 512 input tokens, 256 generated tokens, at least 128 requests per trial. | Calibrate duration and fixed request count during the optional preflight; keep the same settings across cells. |
| Sampling | Greedy or an explicitly fixed supported decoding policy. | Same sampling settings, seed handling, EOS policy, and maximum output length. |
| Quality workload | Independent natural-language evaluation windows and deterministic functional cases. | Dataset provenance, split hashes, sample size, evaluator version, and uncertainty method. |
| Memory | A fixed physical and allocator measurement policy. | GPU memory budget, reservation treatment, and startup/steady-state windows. |
| Latency | Request latency and token-level or honestly named chunk-level latency. | Timestamp source, granularity, quantile estimator, and unit. |
| Energy | GPU power telemetry when reliably available. | Sampling rate, coverage, scope, idle treatment, and whether it is a hard gate. |
| Cost | GPU resource cost must be $0; Token Factory usage remains inside the existing $25 aggregate cap. | Verify free access without paid upgrades; preserve provider-call accounting. |

Execute this extension interactively through the notebook's supported interface; do not turn a free notebook into an SSH server, distributed worker, or app-hosting service. Export raw artifacts for import into ZeroWall. Run the performance client in the notebook or a fixed permitted nearby host. Record the network path and timer source. Keep engine startup/model download out of steady-state throughput, while reporting their separate wall time and cost.

Do not change concurrency between candidates to manufacture speedup. A concurrency sweep is a separate experiment with separate envelopes. Keep prefix reuse, caching policy, context length, scheduler limits other than the declared factor, and warm-up consistent.

## 3. Four-cell cross-layer experiment

### 3.1 Proposed factors

**Factor A: model/algorithm precision.** Compare the selected full-precision checkpoint with a provenance-matched supported weight-quantized checkpoint, initially targeting W4A16/INT4 where the hardware and engine support it. This tests reduced weight-storage/traffic against dequantization and quality costs.

**Factor B: engine/runtime scheduler token budget.** Compare the selected engine's normal competitive scheduling settings with one preregistered alternative token budget for chunked prefill. The candidate values are chosen in feasibility work, not guessed from unrelated hardware. Preserve normal supported baseline optimizations.

The vLLM optimization guide documents `max_num_batched_tokens` as affecting the prefill/decode trade-off. The quantization guide shows that formats/backends depend on hardware. Both factors therefore require a pinned-release smoke test before freeze. [vLLM optimization](https://docs.vllm.ai/en/latest/configuration/optimization/), [vLLM quantization](https://docs.vllm.ai/en/latest/features/quantization/)

| Configuration | Factor A | Factor B | Question |
| --- | --- | --- | --- |
| C00 baseline | Full precision | Normal competitive engine setting | How does the unmodified system perform? |
| C10 A only | Quantized weights | Same normal engine setting | Does reduced precision help or introduce quality/verification costs? |
| C01 B only | Full precision | Alternative scheduler budget | Does the scheduler improve the relevant user metric or shift latency? |
| C11 A+B | Quantized weights | Alternative scheduler budget | Does precision change the best scheduling region or expose a hidden cost? |

All non-factor settings are equal or explicitly declared dependent consequences of the factor. For example, reduced model weight size is a consequence of A; swapping to an unrelated instruction-tuned checkpoint is a confounder.

The four-cell matrix is a minimal discriminating design, not a guarantee that these settings interact. If preflight proves a factor is unsupported or uninformative, choose a documented substitute before confirmation, such as a supported kernel backend paired with a memory/runtime setting. Preserve two distinct affected layers and a valid four-cell ablation.

### 3.2 Optional fifth and sixth configurations

Use at most two slots for a refinement motivated by measured evidence: an intermediate scheduler budget, a supported precision/backend choice, or a bounded adaptive-policy prototype. Each slot needs its own hypothesis and trade-off card.

Do not start with quantization, speculative decoding, custom kernels, driver patches, and scheduler redesign simultaneously. A large bundle would be difficult to reproduce or attribute. Speculation is a later hypothesis unless compatible draft/target models and telemetry are already available within the approved schedule.

## 4. Hypothesis and trade-off templates

Every hypothesis must include:

```yaml
id: HYP-001
title: Precision changes the useful scheduler region
affected_layers: [model, engine, runtime]
mechanism: >-
  Reduced weight work may expose scheduler or verification overhead
  that was hidden by the baseline resource bottleneck.
prediction:
  observation: The relative effect of B differs between C00 and C10.
  required_evidence: [four_cell_timings, gate_results, selected_profile]
experiment_id: EXP-001
controls: [same_requests, same_gpu, same_tokenizer, same_sampling]
kill_rule: >-
  Reject the claimed interaction if uncertainty includes the
  preregistered no-material-interaction region.
unknowns: [exact_resource_mechanism_without_profiler]
```

The mechanism above is a testable proposal, not an established explanation. If profiling is unavailable, the council can identify a configuration interaction without claiming a proven DRAM or kernel mechanism.

A trade-off card records both expectations and observations:

| Field | Before execution | After execution |
| --- | --- | --- |
| Pros | Expected benefit and why it should occur. | Confirmed or unconfirmed benefit with evidence IDs. |
| Cons | Quality, memory, verification, latency, energy, and complexity risks. | Remaining, reduced, or newly discovered costs. |
| Hidden costs | Likely conversion, allocation, synchronization, cache, or scheduling overhead. | Measured costs or explicitly untested possibilities. |
| Envelope | Conditions under which the mechanism should operate. | Conditions actually tested and any boundary failure. |
| Falsification | Prediction and threshold that would reject it. | Supported, falsified, blocked, or inconclusive. |
| Net effect | Primary improvement sought within hard gates. | Feasible operating point or rejection reason. |

## 5. Metric definitions

Use a single implementation and version it. Client tools can define similarly named metrics differently; the report must state its exact denominators. NVIDIA's benchmarking guide distinguishes request latency, TTFT, ITL, and aggregate/user throughput and explains why concurrency and sequence lengths matter. [NVIDIA benchmarking concepts](https://developer.nvidia.com/blog/llm-benchmarking-fundamental-concepts/)

### 5.1 Primary end-to-end metric

```text
system_output_tps = total_valid_output_tokens
                    / (last_request_completion - first_request_send)
```

Include queuing, prefill, and generation in the timed interval; exclude model loading and declared warm-up. Keep request count and traffic policy fixed. If any required request fails, the trial's completeness/correctness gate fails; do not improve throughput by dropping slow or failed requests.

Report decode-only throughput separately if instrumented. A faster kernel, higher utilization, or faster decode stage alone cannot satisfy the primary end-to-end gate.

### 5.2 Latency

```text
TTFT(request) = first_nonempty_output_time - request_send_time
request_latency = final_output_time - request_send_time
mean_ITL(request) = (final_output_time - first_output_time)
                    / (output_token_count - 1)
```

Mean ITL is undefined for fewer than two output tokens. A per-request mean is not P99 token latency. To report P99 ITL, collect token-level intervals or documented engine-side equivalents. If streamed events bundle tokens, inter-chunk intervals must be named as such unless a supported instrumentation path gives real token timings.

Compute the declared P99 statistic per trial and preserve request/sequence identity. Use trial/block-level uncertainty; pooling thousands of correlated token intervals does not create thousands of independent experiments.

### 5.3 Memory and traffic

- **Physical GPU memory:** sampled device usage, with process/isolation scope and sampling limitations.
- **Allocator peak:** engine/framework allocated and reserved memory, when exposed.
- **Weight size:** artifact/accounted model bytes; an estimate of traffic only under stated assumptions.
- **DRAM bytes/token:** measured read/write counters divided by useful output tokens, only when compatible counters exist.
- **Effective bandwidth:** bytes transferred divided by duration for a declared memory path and traffic convention.

Do not call reserved memory reduction an observed reduction in DRAM traffic. Do not compare CPU-GPU link throughput, device-device copy throughput, and on-device DRAM peak bandwidth as the same quantity. NVbandwidth's test names and paths must be recorded when it is used. [NVIDIA NVbandwidth](https://github.com/NVIDIA/nvbandwidth)

The source ceiling can motivate a bounded model such as `time >= bytes / achievable_bandwidth`, but its bytes, path, and overlap assumptions must be explicit. Useful tokens per transferred byte can improve without exceeding the physical rate of the memory interface.

### 5.4 Quality and correctness

Use a fixed held-out quality dataset, initially around 512 independent text windows where free capacity permits, and a separate set of at least 64 deterministic functional cases. Freeze evaluator rules before confirmation.

For a language-model quality proxy:

```text
delta_NLL = candidate_mean_NLL - baseline_mean_NLL
perplexity_ratio = exp(delta_NLL)
```

Compute the paired effect over matching windows and resample at the window/source-document level. Preserve tokenization and window provenance. This measures the declared language-model proxy, not universal reasoning or application quality.

Functional correctness records newly failing cases, malformed output, empty/invalid completions, NaNs, and unexpected execution errors. Quantization does not require byte-for-byte equality with full-precision text, but it does require passing the declared approximation and task checks.

The performance trace can use fixed generation lengths with EOS ignored for fair timing. Quality evaluation must use its own appropriate EOS/scoring policy. Do not evaluate meaningful answer quality from forced extra generation after EOS.

### 5.5 Energy and cost

```text
GPU_joules = integral_of_sampled_GPU_power_over_timed_window
GPU_joules_per_output_token = GPU_joules / total_valid_output_tokens
GPU_compute_cost_per_million_tokens = hourly_rate
    * timed_seconds / 3600 * 1_000_000 / total_valid_output_tokens
```

Record telemetry cadence, gaps, sensor scope, and whether idle power is subtracted. GPU energy is not total system or datacenter energy. Compute cost excludes council inference, startup, idle reservation, storage, and network unless those are explicitly added. Report total mission spend separately.

## 6. Trial design and comparability

### 6.1 Calibration

1. Capture environment and run the baseline correctly with normal engine optimizations.
2. Define a deterministic warm-up procedure that reaches steady operation; include graph compilation/capture outside timing for every cell.
3. Execute at least six balanced baseline-versus-baseline paired blocks to estimate short-run drift. Treat the small-sample noise estimate as approximate.
4. Set the materiality threshold and final trial count before confirmatory data are examined.
5. Record whether available samples can resolve the proposed quality and tail-latency limits. Tight gates with insufficient precision produce an inconclusive finding.

Proposed noise statistic:

```text
noise_floor = percentile_95(abs(B2_tps / B1_tps - 1))
material_gain_target = max(0.05, 2 * noise_floor)
```

These are planning defaults, not universal thresholds. If the noise is too high, stabilize the environment before increasing model activity or claiming a small gain.

### 6.2 Exploration and confirmation

- Exploration: approximately four complete randomized blocks across C00/C10/C01/C11, sufficient for diagnosis and candidate selection, not final confirmation.
- Confirmation: at least ten preregistered complete blocks on reserved requests/seeds, with the selected candidate and required ablation cells frozen beforehand.
- Each block uses matching request data, seeds/policy, and the same environment. Balance or randomize configuration order to reduce drift.
- If calibration justifies more blocks, freeze that number before confirmation and within the approved budget.
- Do not repeatedly inspect confidence intervals and stop at the first favorable result.
- If the budget interrupts the planned schedule, retain all data and label the confirmatory result incomplete/inconclusive.

Model/engine restart and warm-up can make each block expensive. Report active engineering time, GPU reserved hours, startup time, measured trial time, and analysis time separately.

### 6.3 Invalid trials and failures

Predeclare exclusions such as environment mismatch, missing required events, external GPU contention, collector failure, or documented thermal/clock departure from the frozen policy. Preserve the evidence and exclusion reason.

Candidate OOM, invalid output, or an excessive latency outcome is normally a candidate failure, not a disposable invalid trial. A telemetry collector crash is a measurement failure. Distinguish these so adverse results cannot be excluded as inconvenient noise.

Do not kill unrelated processes or change driver/power settings to stabilize a shared host. Use an approved isolated environment and documented supported controls.

## 7. Hard gates and verdicts

The following defaults are proposals to freeze after calibration:

| Gate | Proposed acceptance rule | Missing evidence |
| --- | --- | --- |
| G01 End-to-end benefit | Lower confidence bound of confirmed relative primary gain exceeds the frozen material gain target. | Inconclusive; no confirmed improvement claim. |
| G02 Quality proxy | Upper confidence bound of paired perplexity ratio is at most 1.02 on the frozen evaluator. | Unknown; no claim of preserved evaluated quality. |
| G03 Functional correctness | No newly failing required correctness cases and no malformed/invalid outputs outside the frozen approximation policy. | Unknown or fail depending on collection versus actual output error. |
| G04 Memory | Peak usage stays within the device budget and the frozen allowable regression from baseline. Initial allowance: 2% plus a declared sampling tolerance. | Unknown; do not assume a model-size estimate proves peak usage. |
| G05 Tail latency | Upper bound of P99 ITL ratio is at most 1.05 and the absolute mission SLO also passes. | Unknown if granularity or sample precision is insufficient. |
| G06 TTFT | Upper bound of declared TTFT ratio is at most 1.10 and the absolute mission SLO passes. | Unknown; distinguish request events from engine-only timing. |
| G07 Energy | When frozen as required, upper bound of GPU joules/token ratio is at most 1.05. | Unknown blocks a confirmed energy-preserving claim. |
| G08 Integrity/completeness | Matching environment, complete planned trials, valid manifests, and confirmed cleanup. | Invalid comparison or incomplete finding. |

Absolute latency and memory limits depend on the chosen GPU/workload and must be selected during the optional preflight. The source examples of 24 GB, 120 ms, and 0.5% quality loss do not automatically become requirements for this device.

If energy telemetry is not reliable, the director may prospectively define energy as unavailable/secondary before confirmation. The report must then say energy preservation was not established. The same transparency applies to any unavailable secondary measurement.

Gate states:

- **Pass:** valid comparable evidence satisfies the frozen criterion.
- **Fail:** valid evidence establishes a criterion violation.
- **Unknown:** required data/precision are insufficient.
- **Invalid:** the comparison or artifact integrity cannot support the calculation.

A candidate is **confirmed within the envelope** only when the primary benefit and every required guardrail pass. Failure rejects the applicable claim; unknown gives an inconclusive verdict; invalid requires a corrected comparison. Director approval accepts the report's bounded finding and cannot override these labels.

## 8. Effects, interactions, and Pareto analysis

### 8.1 Relative effects

For each block and comparison, calculate throughput ratio and relative gain. Aggregate using the frozen estimator, initially the geometric mean of paired throughput ratios, and bootstrap complete blocks with a fixed analysis seed. Report both the point estimate and interval, plus sample count and all invalid/excluded blocks.

Small block counts give approximate intervals. Avoid presenting a confidence percentage as the probability that the hypothesis is true.

### 8.2 Interaction

Use a preregistered log-throughput scale:

```text
interaction = log(T11) - log(T10) - log(T01) + log(T00)
```

Positive interaction indicates more combined throughput than the multiplicative no-interaction expectation; negative indicates antagonism on this scale. The source notes' additive gain examples are intuition, not an interchangeable statistical definition.

To claim synergy, require a positive material interaction interval and show that the feasible combination outperforms the relevant single techniques. A combination can beat baseline without showing synergy. To claim conflict, distinguish a negative interaction from the stronger statement that A+B is worse than the better single technique.

The primary selected-candidate-versus-baseline confirmation is one preregistered contrast. If reporting confirmatory claims for the interaction and both best-single comparisons, predeclare a multiple-comparison method, such as adjusted intervals across those three contrasts. Otherwise label the additional contrasts exploratory.

### 8.3 Feasible Pareto set

1. Exclude invalid comparisons and candidates failing required gates from the feasible set.
2. Compare primary/secondary metrics with explicit directions and uncertainty.
3. Mark a candidate dominated only under the declared comparison rule; uncertain differences can remain non-dominated.
4. Show the baseline and singles, residual cons, and implementation complexity.
5. If a weighted preference score is used to rank feasible candidates, show the weights and sensitivity. A score cannot compensate for a failed hard gate.

The result is a Pareto comparison among tested configurations in one operating envelope. It is not proof of the global hardware/software frontier.

## 9. Reframe and stopping policy

After every experiment, the council must answer:

1. Which predicted signature appeared, failed, or remained unmeasured?
2. Did the local benefit improve the primary end-to-end metric?
3. Which quality, memory, latency, energy, or complexity cost changed?
4. Which alternative mechanism could explain the same observation?
5. Did the bottleneck move, and how strong is that inference?
6. Which next experiment most efficiently distinguishes the remaining explanations?

Trigger an explicit Reframe when a local gain does not transfer, the causal model conflicts with observations, consecutive proposals repeat a tested mechanism, or the director requests it.

A reframe can ask whether the bytes need moving, whether work can be reused or moved to idle compute, whether a different useful-work unit changes the bound, or whether the workload/metric assumption is wrong. It must produce an updated hypothesis or scope decision, not a motivational summary.

Proposed bounded search: four exploration configurations, at most two refinement configurations, two structured cross-review passes per research round, and no more than three full council rounds before director review. Freeze dollar and GPU-hour caps separately. A legitimate unresolved finding is preferable to an unbounded debate.

## 10. Measuring the council's contribution

The product claim is inspectable research coordination and better evidence handling. Test that claim separately from the benchmark speedup.

Use the same mission and evidence packet for:

- A strong single model with a structured research prompt.
- The ZeroWall four-seat protocol.
- An optional naive multi-answer/vote baseline if time permits.

Disclose model identities, token/call/spend budgets, tools available, and whether effort was matched. Judge proposal quality using preregistered criteria: falsifiability, control validity, coverage of trade-offs, evidence citation, unsupported claims, and useful next experiments. Use actual executed/validated outcomes where possible, with a human rubric for remaining qualitative differences.

One mission cannot establish general superiority. Report a case study, coordination effort, actual tool/evidence usage, and any failure where the single model was equally effective or cheaper. Do not tune evaluation criteria to favor the council after observing its outputs.

## 11. Reproducibility and report policy

The pack must include the approved mission/protocol revision, exact model and tokenizer provenance, container digest, hardware inventory, configuration matrix, workload/seed manifests, raw request and telemetry events, profiles if used, analysis version, gate results, all trial exclusions, director decisions, dissent, and cleanup receipts.

Support two reproduction levels:

1. **Offline analysis reproduction:** verify hashes and regenerate metrics/gates from the supplied raw artifacts without a GPU or provider key.
2. **Experimental reproduction:** start the documented compatible GPU environment, download the declared assets, rerun the frozen schedule, and compare results within stated variability. This requires approved compute and is not expected to produce identical wall-clock numbers.

A final report states: what changed; where it was tested; what improved or failed; how uncertain the result is; which gates passed/failed/are unknown; what evidence supports the mechanism; which trade-offs remain; and what should reopen the decision.

## 12. Demo integrity

The video can compress time and use genuine saved results for long experiments. Label the mode and timestamp. Show a short live approved action where feasible. A saved result must still link to its raw evidence and reproducibility pack.

Use the measured story:

- If a feasible combination wins, show baseline, singles, combination, and confirmation.
- If a local winner fails the complete system, show the failed gate and the reframe.
- If no result is conclusive, show what was learned, what remains unknown, and the next discriminating experiment.

Never preassign a minority researcher to be correct, manufacture a consensus reversal, or present illustrative figures as cloud measurements. The value of ZeroWall is that the evidence controls the conclusion.

