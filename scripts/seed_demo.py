"""Create a full synthetic council + real numerical tool mission. No model calls."""

import argparse, json
from zerowall.api import create_app
from zerowall.settings import Settings
from zerowall.fixtures import demo_brief
from zerowall.contracts import (
    MissionBrief,
    RoundInput,
    ExperimentInput,
    ReframeInput,
    TradeoffInput,
    DecisionInput,
)
from zerowall.reports import export_pack, reproduce
from zerowall.process_lock import ProcessLock


def seed(data_dir=None):
    settings = Settings(data_dir)
    ownership = ProcessLock(settings.data / "executor.lock")
    ownership.acquire()
    try:
        return seed_owned(settings)
    finally:
        ownership.release()


def seed_owned(settings):
    app = create_app(settings, run_worker=False)
    r = app.state.research
    s = r.store
    x = app.state.executor
    with s.tx() as c:
        m = r.create_mission(c, MissionBrief.model_validate(demo_brief()))
        r.freeze(c, m["id"], 1)
        step = s.list(c, "step", m["id"])[0]
        rnd = r.round(c, step["id"], RoundInput(expected_revision=1, mode="fixture"))
    x.run_once()
    with s.tx() as c:
        r.reveal(c, rnd["id"], 1)
        r.review(c, rnd["id"], 1)
    x.run_once()
    with s.tx() as c:
        hypotheses = s.list(c, "hypothesis", m["id"])
        e = r.experiment(
            c,
            step["id"],
            ExperimentInput(
                expected_revision=1,
                title="Test the declared bandwidth lower bound",
                hypothesis_ids=[hypotheses[0]["id"]],
                capability="analysis.calculate_bound",
                args={
                    "bytes_moved": 2e9,
                    "bandwidth_gbps": 100,
                    "assumptions": [
                        "Hypothetical sustained bandwidth of 100 decimal GB/s",
                        "Serial transfer with no overlap; not a measurement",
                    ],
                },
                control="Fixed supplied transfer size and decimal units",
                treatment="Evaluate bytes divided by the declared bandwidth",
                prediction="The bandwidth-only lower bound is 20 ms",
                kill_rule="Reject any smaller arithmetic bound under these assumptions",
                information_value=4,
                impact=3,
                feasibility=5,
                cost_score=5,
                priority_reason="Discriminate arithmetic feasibility before paying for model requests",
            ),
        )
        r.approve_experiment(c, e["id"], 1)
    x.run_once()
    with s.tx() as c:
        evidence = s.list(c, "evidence", m["id"])[0]
        r.reframe(
            c,
            step["id"],
            ReframeInput(
                expected_revision=1,
                reason="A valid arithmetic bound does not identify provider internals",
                interpretation="Separate the calculated physical lower bound from client-observed workflow cost and latency",
                prediction_comparison="The 20 ms analytical prediction is reproduced; no provider performance prediction was tested",
                changed_assumptions=[
                    "Replace any physical performance interpretation with a supplied-input calculation"
                ],
                alternative_explanations=[
                    "Client framing, queueing, routing or validation may dominate workflow latency"
                ],
                next_action="After billing verification, compare paired source packing and routing treatments using frozen validators",
                evidence_ids=[evidence["id"]],
                hypothesis_states={hypotheses[0]["id"]: "supported"},
            ),
        )
        r.tradeoff(
            c,
            step["id"],
            TradeoffInput(
                expected_revision=1,
                category="conflict",
                title="Cheap analytical discrimination versus missing empirical evidence",
                expected_pros=[
                    "Falsifies impossible arithmetic without an inference request"
                ],
                expected_cons=["Cannot establish the real API bottleneck"],
                observed_pros=["The deterministic tool returns a 20 ms bound"],
                observed_cons=["Provider hardware remains unobserved"],
                hidden_costs=[
                    "A valid bound may not transfer to full workflow performance"
                ],
                mitigations=["Measure the application workflow separately"],
                operating_region="Supplied serial transfer assumptions only",
                complexity="One fixed formula; no model or hardware allocation",
                rejection_rule="Reject hardware-performance claims unsupported by measurements",
                evidence_ids=[evidence["id"]],
            ),
        )
        d = r.decision(
            c,
            step["id"],
            DecisionInput(
                expected_revision=1,
                conclusion="The supplied transfer scenario implies a 20 ms analytical lower bound. The hosted workflow optimization remains inconclusive until real API and quality evidence is collected.",
                verdict="inconclusive",
                agreement="unresolved",
                alternatives=[
                    "Proceed to a paired context and routing pilot",
                    "Revise the physical assumptions if the research scope changes",
                ],
                reasons=[
                    "The calculation is reproducible and has explicit units",
                    "No live inference, quality study or provider hardware measurement was performed",
                ],
                dissent=[
                    "The runtime and algorithm mechanisms remain untested; the bound alone does not prioritize them"
                ],
                assumptions=[
                    "100 decimal GB/s is a supplied hypothetical input",
                    "Synthetic council text demonstrates software behavior only",
                ],
                reopen_triggers=[
                    "New measured workflow evidence",
                    "Changed units, transfer size or overlap assumptions",
                ],
                evidence_ids=[evidence["id"]],
            ),
        )
        r.approve_decision(c, d["id"], 1)
    pack = export_pack(r, m["id"])
    path = r.settings.data / "exports" / pack["filename"]
    result = {
        "mission_id": m["id"],
        "mode": "fixture",
        "actual_tool": "analysis.calculate_bound",
        "minimum_ms": 20,
        "inference_calls": 0,
        "export": str(path),
        "reproduction": reproduce(path),
    }
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir")
    args = p.parse_args()
    print(json.dumps(seed(args.data_dir), indent=2))
