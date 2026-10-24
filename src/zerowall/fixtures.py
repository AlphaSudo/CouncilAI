"""Synthetic development data. Never presented as model-generated or measured."""

SEATS = [
    (
        "hardware",
        "Hardware & Physics",
        "Challenge physical bounds and resource assumptions.",
    ),
    (
        "runtime",
        "Driver & Runtime",
        "Find queueing, framing and application overhead confounders.",
    ),
    (
        "engine",
        "Inference Engine",
        "Test request behavior, latency definitions and missing controls.",
    ),
    (
        "algorithms",
        "Model & Algorithms",
        "Test context packing, routing quality and escalation cost.",
    ),
]


def submission(seat, sources):
    ideas = {
        "hardware": (
            "A bandwidth lower bound constrains a physical explanation, but API timing cannot identify provider bandwidth.",
            "Moving 2 GB at an assumed 100 GB/s requires at least 0.02 seconds.",
            "Calculate a lower bound and separate client timing from physical measurement.",
            "Reject the physical explanation if it requires less time than the stated lower bound.",
        ),
        "runtime": (
            "Smaller source packets can reduce input overhead, while queueing and retries may dominate the complete workflow.",
            "Packing may lower input cost without lowering complete workflow latency.",
            "Pair full and packed packets on the same tasks and retain retry costs.",
            "Reject the optimization if required facts are lost or complete task cost increases.",
        ),
        "engine": (
            "Fast-first routing adds escalation calls; endpoint latency must include both attempts.",
            "An invalid fast answer may consume more money than one strong-model request.",
            "Compare all four context and routing cells under the same validators.",
            "Reject a candidate with any newly failing required case.",
        ),
        "algorithms": (
            "Context packing and routing can interact through evidence visibility and escalation rates.",
            "The combination may save input tokens while increasing unsupported answers.",
            "Freeze a paired four-cell pilot and hold confirmation tasks separate.",
            "Reject a claimed synergy unless the combination beats each single factor with quality preserved.",
        ),
    }
    mechanism, prediction, experiment, kill = ideas[seat]
    return {
        "mechanism": mechanism,
        "prediction": prediction,
        "experiment": experiment,
        "control": "Keep the supplied facts, units, tasks and complete-workflow measurement boundary fixed.",
        "confounders": [
            "Provider internals are unobserved; model identity and retries can change application outcomes."
        ],
        "kill_rule": kill,
        "affected_layers": [seat, "application"],
        "source_ids": sources,
        "uncertainty": "Synthetic fixture for workflow verification. No provider or hardware observation.",
        "recommendation": "Run the smallest discriminating approved test; retain negative results.",
    }


def review(hypotheses, concerns):
    return {
        "challenged_hypothesis_ids": [h["id"] for h in hypotheses],
        "missing_controls": [
            "Keep task facts and complete-workflow timing boundaries fixed."
        ],
        "confounders": [
            "Model identity, response validity, caching and unobserved provider load may change workflow latency."
        ],
        "tradeoffs": [
            "Savings may be offset by escalation and evidence-quality failures."
        ],
        "evidence_needed": [
            "Raw responses, usage, validators and actual request identities."
        ],
        "concern_responses": {
            c[
                "id"
            ]: "Address this in the approved controls and keep its disposition open for director review: "
            + c["text"]
            for c in concerns
        },
        "revised_recommendation": "Run a bounded local calculation first; a fixture cannot establish a live model or quality benefit.",
    }


def demo_brief():
    return {
        "title": "The cost of a valid research answer",
        "goal": "Test whether context packing and bounded model routing reduce hosted research workflow cost while preserving facts, citations and useful next experiments.",
        "deliverable": "An evidence-backed decision with ablation, dissent, operating limits and an offline reproducibility pack.",
        "constraints": [
            "Use existing Token Factory credit only; no additional payment.",
            "Hosted API timing does not measure provider hardware behavior.",
            "Preserve every required source fact and count escalation attempts.",
        ],
        "rubric": [
            "Factual and numerical validity",
            "Source support and units",
            "Falsifiable mechanism and useful next test",
        ],
        "sources": [
            {
                "id": "S01",
                "text": "A hypothetical transfer moves 2,000,000,000 bytes at an assumed sustained bandwidth of 100 decimal GB/s. This is a supplied analytical scenario, not a hardware measurement.",
                "provenance": "ZeroWall authored synthetic analytical scenario, CC0",
            },
            {
                "id": "S02",
                "text": "Workflow latency includes queueing, all model attempts, validation and escalation. Token Factory does not expose physical memory-bandwidth controls to this application.",
                "provenance": "ZeroWall protocol definition",
            },
        ],
        "steps": [
            {"key": "frame", "title": "Test the mechanism", "depends_on": []},
            {
                "key": "confirm",
                "title": "Confirm the operating point",
                "depends_on": ["frame"],
            },
        ],
        "primary_metric": "cost_per_valid_task",
        "budget_usd": 1,
        "latency_limit_ms": 60000,
        "material_saving": 0.1,
        "mode": "fixture",
    }
