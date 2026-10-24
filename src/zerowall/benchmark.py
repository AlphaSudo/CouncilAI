"""Authored research tasks with separate visible packets and hidden deterministic keys."""

from pathlib import Path
import json, random, time
from .db import digest, DomainError
from .analysis import compare_trials
from .provider import parse_json

ROOT = Path(__file__).resolve().parents[2]


def tasks(split):
    return json.loads(
        (ROOT / f"benchmark/tasks/{split}.json").read_text(encoding="utf-8")
    )


def pack_sources(sources):
    # Only exact duplicate facts within each source are removed; no semantic answer-aware compression.
    return [{"id": s["id"], "facts": list(dict.fromkeys(s["facts"]))} for s in sources]


def prompt(task, packed):
    sources = pack_sources(task["sources"]) if packed else task["sources"]
    contract = {
        "answer": "number",
        "unit": "string",
        "source_ids": ["source IDs"],
        "finding": "concise evidence-backed statement",
        "next_test": "a discriminating next test",
        "hardware_measured": "boolean",
    }
    return json.dumps(
        {
            "question": task["question"],
            "sources": sources,
            "constraints": task["constraints"],
            "required_output": contract,
        },
        ensure_ascii=False,
    )


def route_valid(value, source_ids):
    return (
        isinstance(value, dict)
        and isinstance(value.get("answer"), (int, float))
        and not isinstance(value.get("answer"), bool)
        and isinstance(value.get("source_ids"), list)
        and bool(value["source_ids"])
        and set(value["source_ids"]) <= set(source_ids)
        and isinstance(value.get("finding"), str)
        and isinstance(value.get("next_test"), str)
        and isinstance(value.get("hardware_measured"), bool)
        and isinstance(value.get("unit"), str)
    )


def validate(task, value, key):
    schema = route_valid(value, [s["id"] for s in task["sources"]])
    if not schema:
        return {"valid": False, "checks": {"schema": False}, "method": "task-key-v1"}
    checks = {
        "schema": True,
        "numeric": abs(value["answer"] - key["answer"]) <= key["tolerance"],
        "unit": value["unit"].strip().lower() in key["units"],
        "citation_support": set(key["required_sources"]) <= set(value["source_ids"]),
        "hardware_scope": value["hardware_measured"] is False,
        "required_facts": all(
            word.lower() in value["finding"].lower() for word in key["finding_terms"]
        ),
        "next_test": len(value["next_test"]) >= 15,
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "method": "task-key-v1",
        "scope": "Checks this authored task only; citation ID coverage and frozen fact terms are not a universal semantic entailment judge.",
    }


def run_benchmark(executor, e, cancelled):
    args = e["args"]
    split = args["split"]
    packet = tasks(split)
    keys = json.loads(
        (ROOT / "benchmark/evaluators/hidden.json").read_text(encoding="utf-8")
    )
    blocks = [
        (task, index, repeat)
        for index, task in enumerate(packet)
        for repeat in range(args["repeats"])
    ]
    random.Random(1701).shuffle(blocks)
    cells = ("C00", "C10", "C01", "C11")
    schedule = []
    for task, index, repeat in blocks:
        rotation = (index + repeat) % 4
        schedule.extend(
            (task, repeat, cell) for cell in cells[rotation:] + cells[:rotation]
        )
    if e["mode"] == "fixture":
        raise DomainError(
            "The controlled API benchmark requires a live mission; fixtures cannot generate measured comparisons",
            412,
        )
    provider = executor.research.provider
    with executor.store.tx() as c:
        mission = executor.store.get(c, e["mission_id"], "mission")
        if mission["brief"].get("provider") == "openrouter_free":
            raise DomainError(
                "Free missions cannot run the Token Factory cost benchmark", 412
            )
        v = executor.store.setting(c, "live_verification", {})
        strong = provider.choose(c)
        allowed = [
            m
            for m in executor.settings.models
            if m in v.get("catalog_model_ids", []) and m in v.get("prices", {})
        ]
        if len(allowed) < 2:
            raise DomainError(
                "Routing comparison needs two verified enabled models", 412
            )
        fast = allowed[-1]
        prior_schedules = executor.store.list(c, "schedule", e["mission_id"])
        if any(x.get("split") == "confirmation" for x in prior_schedules):
            raise DomainError(
                "The held-out confirmation schedule was already consumed. Preserve its result; do not tune or rerun this mission until favorable.",
                412,
            )
        strategy = {
            "strong": strong,
            "fast": fast,
            "packing": "exact-duplicate-facts-v1",
            "route": "visible-schema-source-presence-v1",
            "output_limit": 768,
            "repeats": args["repeats"],
        }
        if split == "confirmation":
            prior = [
                x
                for x in executor.store.list(c, "schedule", e["mission_id"])
                if x.get("split") == "exploration"
                and x.get("strategy_hash") == digest(strategy)
            ]
            if not prior:
                raise DomainError(
                    "Freeze and run the same exploratory strategy before confirmation",
                    412,
                )
        executor.store.put(
            c,
            "schedule",
            {
                "id": e["id"] + "_schedule",
                "mission_id": e["mission_id"],
                "experiment_id": e["id"],
                "split": split,
                "strategy_hash": digest(strategy),
                "strategy": strategy,
                "seed": 1701,
                "order_method": "Shuffled task blocks; counterbalanced Latin rotations within each task",
                "task_hash": digest(packet),
                "key_hash": digest(keys),
                "plan_hash": e["plan_hash"],
                "schedule": [
                    {"task_id": t["id"], "repeat": r, "cell": cell}
                    for t, r, cell in schedule
                ],
                "strong_model": strong,
                "fast_model": fast,
                "routing_rule": "Fast-first; one escalation on visible schema/citation-presence failure only. Hidden keys never inform routing.",
            },
        )
        planned = [
            (model, prompt(task, cell in ("C10", "C11")), 768)
            for task, repeat, cell in schedule
            for model in ([strong] if cell in ("C00", "C10") else [fast, strong])
        ]
        hold_id = provider.schedule_hold(
            c, e["mission_id"], planned, e["id"] + "_schedule_hold"
        )
    try:
        return run_schedule(
            executor, e, cancelled, schedule, keys, packet, strong, fast, hold_id
        )
    finally:
        with executor.store.tx() as c:
            executor.research.budget.release_hold(c, hold_id)


def run_schedule(executor, e, cancelled, schedule, keys, packet, strong, fast, hold_id):
    provider = executor.research.provider
    split = e["args"]["split"]
    observations = []
    details = []
    for task, repeat, cell in schedule:
        if cancelled():
            break
        started = time.perf_counter()
        calls = []
        value = {}
        failure = None
        models = [strong] if cell in ("C00", "C10") else [fast, strong]
        try:
            for model in models:
                raw, call = provider.call(
                    e["mission_id"],
                    prompt(task, cell in ("C10", "C11")),
                    768,
                    model,
                    purpose=f"benchmark:{e['id']}:{task['id']}:{repeat}:{cell}",
                    cancelled=cancelled,
                    hold_id=hold_id,
                )
                calls.append(call)
                try:
                    value = parse_json(raw)
                except ValueError:
                    value = {}
                if route_valid(value, [s["id"] for s in task["sources"]]):
                    break
        except DomainError as exc:
            failure = exc.message
        validation = validate(task, value, keys[task["id"]])
        with executor.store.tx() as c:
            # Includes every failed/ambiguous attempt for this task, not only calls returning text.
            all_calls = [
                r
                for r in executor.store.list(c, "call", e["mission_id"])
                if r["purpose"] == f"benchmark:{e['id']}:{task['id']}:{repeat}:{cell}"
            ]
            cost = 0
            unknown = False
            for call in all_calls:
                row = c.execute(
                    "SELECT * FROM reservations WHERE id=?", (call["reservation_id"],)
                ).fetchone()
                cost += (
                    row["actual_microusd"]
                    if row["state"] == "settled"
                    else row["maximum_microusd"]
                ) / 1e6
                unknown |= row["state"] != "settled"
            detail = {
                "task_id": task["id"],
                "cell": cell,
                "repeat": repeat,
                "split": split,
                "cost_usd": cost,
                "latency_ms": (time.perf_counter() - started) * 1000,
                "valid": validation["valid"] and not failure and not unknown,
                "validator": validation,
                "failure": failure,
                "unknown_cost": unknown,
                "call_ids": [r["id"] for r in all_calls],
                "task_hash": digest(task),
                "output": value,
            }
            executor.store.put(
                c,
                "trial",
                {
                    "id": e["id"] + f"_{task['id']}_{repeat}_{cell}",
                    "mission_id": e["mission_id"],
                    "experiment_id": e["id"],
                    **detail,
                },
            )
        observations.append(
            {
                k: detail[k]
                for k in (
                    "task_id",
                    "cell",
                    "repeat",
                    "split",
                    "cost_usd",
                    "latency_ms",
                    "valid",
                )
            }
        )
        details.append(detail)
        if failure:
            break
    if not observations:
        raise DomainError("No benchmark block was executed")
    with executor.store.tx() as c:
        m = executor.store.get(c, e["mission_id"], "mission")
        attempt_records = [
            x
            for x in executor.store.list(c, "call", e["mission_id"])
            if x["purpose"].startswith(f"benchmark:{e['id']}:")
        ]
    usage_complete = all(
        isinstance(x.get("usage"), dict)
        and all(
            isinstance(x["usage"].get(k), int)
            for k in ("prompt_tokens", "completion_tokens")
        )
        for x in attempt_records
    )
    result = compare_trials(
        {
            "observations": observations,
            "material_saving": m["brief"]["material_saving"],
            "latency_limit_ms": m["brief"]["latency_limit_ms"],
        }
    )
    if len(observations) != len(schedule) or any(
        d["unknown_cost"] or d["failure"] for d in details
    ):
        result["integrity_gate"] = "invalid"
    return {
        **result,
        "observations": observations,
        "trials": details,
        "planned": len(schedule),
        "completed": len(observations),
        "request_count": len(attempt_records),
        "prompt_tokens": sum(x["usage"]["prompt_tokens"] for x in attempt_records)
        if usage_complete
        else None,
        "completion_tokens": sum(
            x["usage"]["completion_tokens"] for x in attempt_records
        )
        if usage_complete
        else None,
        "usage_complete": usage_complete,
        "escalation_count": sum(max(0, len(t["call_ids"]) - 1) for t in details),
        "automatic_repairs": 0,
        "strong_model": strong,
        "fast_model": fast,
        "evidence_class": "measured_api",
        "task_manifest_hash": digest(packet),
        "hidden_key_hash": digest(keys),
        "timing_boundary": "Task-loop entry before prompt preparation through terminal validation, including both route attempts. Experiment queue wait is separately recorded in the run manifest.",
    }
