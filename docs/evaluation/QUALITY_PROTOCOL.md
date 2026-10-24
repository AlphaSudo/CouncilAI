# Independent council quality evaluation

The separate [1.02 scoped-review protocol](SCOPED_QUALITY_PROTOCOL.md) compares Reviewed v1 with v2 and adds false-closure, proposal-retention and provenance metrics. Its tasks and tooling do not complete the independent evaluation described below.

The integration cases and eighteen protocol fixtures demonstrate software behavior. They do not establish that Reviewed council gives better answers. Keep that claim pending until qualified human labels exist.

Before collecting outputs, freeze representative unseen tasks, supplied sources, exact selected model IDs, prompt/evidence hashes, eligibility criteria and the scoring rubric. Keep the selected model set the same across each pair. Disclose actual provider participation and failures. Do not tune prompts against held-out labels or exclude failed/partial answers to improve reported results.

Create one Discussion and one Reviewed council per task through the existing UI/API, using identical question/source conditions. Four-member Discussion with two rounds plans thirteen calls; Reviewed council plans twelve. Record the differing allocation, tokens, actual attempts, retries, latency, missing members and monetary-cost visibility. Each conversation retains its own twenty-attempt ceiling and the shared database daily cap; the evaluation does not bypass either. Do not run more pairs than confirmed free capacity can support. No automated evaluation runner silently dispatches these calls.

Export both transcripts and review packs. A qualified reviewer should be blind to mode where practical. Record reviewer expertise, disagreements, task-specific reference answers or sources, and uncertainty. Label material claims, unsupported claims presented as established, relevant citations, valid/invalid objections, useful repairs, goal drift and direct usefulness (1: unusable through 5: directly useful with appropriate uncertainty). A cautious answer that refuses every useful proposal should score poorly on usefulness.

Populate [the manifest template](../../benchmark/review_quality_template.json). Each pair records task ID, exact question/evidence hashes, selected models and two `QualityRun` records; each run records mode, chat ID, completion state, actual calls, latency, cost if actually reported, and optional `QualityLabels`. The strict contracts are in `src/zerowall/quality.py`. Set labels to null while missing; do not substitute zero errors. Source confidence from the same council is not ground truth.

Run `python scripts/summarize_review_quality.py benchmark/review_quality_template.json` to produce a credential-free summary. It keeps denominators, failed/partial runs, missing labels and unknown invoice cost explicit. Synthetic labels are marked synthetic. A human-labelled input is an operator declaration, not authenticated proof of reviewer identity or independence. The summary does not set publication permissions or unlock any provider.

Predeclare sample size and acceptance criteria before labels. Small pilots are descriptive and may be inconclusive; the summarizer makes no significance or universal-superiority claim. Keep Reviewed council opt-in until evidence justifies changing that default. Publish adverse results and reviewer limitations alongside positive observations.
