"""Deterministic analysis shared by execution, exported packs and offline reproduction."""

import math, random, statistics
from collections import defaultdict

CELLS = ("C00", "C10", "C01", "C11")


def compare_trials(args):
    rows = args["observations"]
    identities = [
        (r["task_id"], r["split"], r.get("repeat", 0), r["cell"]) for r in rows
    ]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate task/cell/repeat observations")
    splits = {r["split"] for r in rows}
    if len(splits) != 1:
        raise ValueError("Analyze exploration and confirmation separately")
    grouped = {cell: [r for r in rows if r["cell"] == cell] for cell in CELLS}
    blocks = defaultdict(dict)
    for r in rows:
        blocks[(r["task_id"], r.get("repeat", 0))][r["cell"]] = r
    complete = bool(blocks) and all(set(b) == set(CELLS) for b in blocks.values())
    cells = {}
    for cell, items in grouped.items():
        valid = sum(r["valid"] for r in items)
        total = sum(r["cost_usd"] for r in items)
        cells[cell] = {
            "attempted": len(items),
            "valid": valid,
            "total_cost_usd": total,
            "cost_per_valid_task": total / valid if valid else None,
            "mean_latency_ms": statistics.mean(r["latency_ms"] for r in items)
            if items
            else None,
        }
    baseline = cells["C00"]
    comparisons = {}
    for cell in CELLS[1:]:
        candidate = cells[cell]
        paired = [
            (b["C00"], b[cell]) for b in blocks.values() if "C00" in b and cell in b
        ]
        new_failures = [
            a["task_id"] for a, b in paired if a["valid"] and not b["valid"]
        ]
        base_cost = baseline["cost_per_valid_task"]
        cand_cost = candidate["cost_per_valid_task"]
        saving = (
            1 - cand_cost / base_cost if base_cost and cand_cost is not None else None
        )
        # Cluster on task, never treat chunks or correlated repeats as independent samples.
        task_pairs = defaultdict(list)
        for a, b in paired:
            task_pairs[a["task_id"]].append(b["cost_usd"] - a["cost_usd"])
        deltas = [statistics.mean(v) for v in task_pairs.values()]
        interval = None
        saving_interval = None
        if len(deltas) >= 8:
            rng = random.Random(1701)
            bootstrap = sorted(
                statistics.mean(rng.choices(deltas, k=len(deltas))) for _ in range(2000)
            )
            interval = [bootstrap[49], bootstrap[1949]]
            clusters = defaultdict(list)
            for a, b in paired:
                clusters[a["task_id"]].append((a, b))
            groups = list(clusters.values())
            rng = random.Random(1701)
            savings = []
            for _ in range(2000):
                sample = [
                    pair
                    for group in rng.choices(groups, k=len(groups))
                    for pair in group
                ]
                av = sum(a["valid"] for a, b in sample)
                bv = sum(b["valid"] for a, b in sample)
                ac = sum(a["cost_usd"] for a, b in sample)
                bc = sum(b["cost_usd"] for a, b in sample)
                if av and bv and ac > 0:
                    savings.append(1 - (bc / bv) / (ac / av))
            if len(savings) == 2000:
                savings.sort()
                saving_interval = [savings[49], savings[1949]]
        comparisons[cell] = {
            "saving_fraction": saving,
            "new_required_failures": new_failures,
            "paired_tasks": len(task_pairs),
            "paired_cost_difference_usd": statistics.mean(deltas) if deltas else None,
            "bootstrap_95_cost_difference": interval,
            "bootstrap_95_saving_fraction": saving_interval,
            "cost_confirmation_gate": "unknown"
            if not complete or saving_interval is None
            else "pass"
            if saving_interval[0] >= args["material_saving"]
            else "fail"
            if saving_interval[1] < args["material_saving"]
            else "unknown",
            "quality_gate": "fail"
            if new_failures
            else "pass"
            if complete
            else "unknown",
            "cost_gate": "unknown"
            if saving is None or not complete
            else "pass"
            if saving >= args["material_saving"]
            else "fail",
            "latency_gate": "unknown"
            if candidate["mean_latency_ms"] is None or not complete
            else "pass"
            if all(r["latency_ms"] <= args["latency_limit_ms"] for r in grouped[cell])
            else "fail",
        }
    c = [cells[cell]["cost_per_valid_task"] for cell in CELLS]
    interaction = (
        math.log(c[3]) - math.log(c[1]) - math.log(c[2]) + math.log(c[0])
        if complete and all(x and x > 0 for x in c)
        else None
    )
    pareto = []
    for cell in CELLS:
        x = cells[cell]
        if not x["attempted"] or x["valid"] != x["attempted"]:
            continue
        if not any(
            y["valid"] == y["attempted"]
            and y["attempted"]
            and y["cost_per_valid_task"] <= x["cost_per_valid_task"]
            and y["mean_latency_ms"] <= x["mean_latency_ms"]
            and (
                y["cost_per_valid_task"] < x["cost_per_valid_task"]
                or y["mean_latency_ms"] < x["mean_latency_ms"]
            )
            for other, y in cells.items()
            if other != cell
        ):
            pareto.append(cell)
    return {
        "method": "paired-task-v1",
        "cells": cells,
        "comparisons": comparisons,
        "integrity_gate": "pass" if complete else "invalid",
        "log_cost_interaction": interaction,
        "pareto_candidates": pareto,
        "independent_tasks": len({r["task_id"] for r in rows}),
        "split": next(iter(splits)),
        "claim_scope": "Descriptive task-set results. Human quality review and independent confirmation are required for a confirmed finding.",
        "hardware_observed": False,
    }


def calculate_bound(args):
    return {
        "minimum_seconds": args["bytes_moved"] / (args["bandwidth_gbps"] * 1e9),
        "bytes_moved": args["bytes_moved"],
        "bandwidth_gbps": args["bandwidth_gbps"],
        "bandwidth_unit": "decimal GB/s",
        "method": "bytes / (GB_per_second * 10^9)",
        "assumptions": args["assumptions"],
        "evidence_class": "calculated",
        "scope": "A lower-bound calculation under supplied assumptions; no hardware was measured.",
    }


def evaluate_rubric(args):
    missing = [k for k in args["required"] if k not in args["scores"]]
    failures = [
        k
        for k in args["required"]
        if k in args["scores"] and args["scores"][k] < args["minimum"]
    ]
    return {
        **args,
        "missing": missing,
        "failures": failures,
        "gate": "unknown" if missing else "fail" if failures else "pass",
        "method": "human-rubric-v1",
    }


def decision_gates(evidence, budget, step_revision, integrity="pass"):
    from .spending_limits import TOKEN_FACTORY_CAP_USD
    credit = (
        "pass"
        if budget["global_committed_usd"] <= min(TOKEN_FACTORY_CAP_USD, budget["operational_cap_usd"])
        else "fail"
    )
    current_benchmarks = {
        e["id"]
        for e in evidence
        if e["capability"] == "inference.run_benchmark"
        and e["evidence_class"] == "measured_api"
        and e["step_revision"] == step_revision
    }
    reviews = [
        e["result"]
        for e in evidence
        if e["capability"] == "analysis.evaluate_rubric"
        and current_benchmarks.intersection(
            e["result"].get("reviewed_evidence_ids", [])
        )
    ]
    quality = (
        "fail"
        if any(r["gate"] == "fail" for r in reviews)
        else "pass"
        if reviews and all(r["gate"] == "pass" for r in reviews)
        else "unknown"
    )
    comparisons = [
        e["result"]
        for e in evidence
        if e["capability"] in ("analysis.compare_trials", "inference.run_benchmark")
    ]
    metrics = {"validity": "unknown", "cost": "unknown", "latency": "unknown"}
    if comparisons:
        latest = comparisons[-1]
        if latest.get("integrity_gate") != "pass":
            integrity = "invalid"
        vals = latest.get("comparisons", {}).get("C11", {})
        metrics = {
            "validity": vals.get("quality_gate", "unknown"),
            "cost": vals.get("cost_gate", "unknown"),
            "latency": vals.get("latency_gate", "unknown"),
        }
    confirmations = [
        e
        for e in evidence
        if e["capability"] == "inference.run_benchmark"
        and e["evidence_class"] == "measured_api"
        and e["mode"] == "live"
        and e["step_revision"] == step_revision
        and e["result"].get("split") == "confirmation"
        and e["result"].get("independent_tasks", 0) >= 8
        and e["result"].get("integrity_gate") == "pass"
        and e["result"].get("completed") == e["result"].get("planned")
    ]
    if confirmations:
        vals = confirmations[-1]["result"]["comparisons"]["C11"]
        metrics = {
            "validity": vals["quality_gate"],
            "cost": vals.get("cost_confirmation_gate", "unknown"),
            "latency": vals["latency_gate"],
        }
        confirmation_ids = {e["id"] for e in confirmations}
        reviews = [
            e["result"]
            for e in evidence
            if e["capability"] == "analysis.evaluate_rubric"
            and confirmation_ids.intersection(
                e["result"].get("reviewed_evidence_ids", [])
            )
        ]
        quality = (
            "fail"
            if any(r["gate"] == "fail" for r in reviews)
            else "pass"
            if reviews and all(r["gate"] == "pass" for r in reviews)
            else "unknown"
        )
    return [
        {"id": "G01", "name": "Credit authority", "status": credit},
        {"id": "G02", "name": "Required case validity", "status": metrics["validity"]},
        {"id": "G03", "name": "Human quality rubric", "status": quality},
        {"id": "G04", "name": "Cost objective", "status": metrics["cost"]},
        {"id": "G05", "name": "Workflow latency", "status": metrics["latency"]},
        {"id": "G06", "name": "Artifact and comparison integrity", "status": integrity},
        {
            "id": "confirmation",
            "name": "Independent live confirmation",
            "status": "pass" if confirmations else "unknown",
        },
    ]
