"""Explicit, ledger-backed Token Factory capability probe; no automatic retry.

Plan by default. --execute sends exactly one request. All probes in a report
share a $0.03 diagnostic mission within the existing global $24 cap.
"""

import argparse
import json
from copy import deepcopy
from pathlib import Path

from zerowall.artifacts import Artifacts
from zerowall.budget import Budget, cost_micro, micro
from zerowall.contracts import MissionBrief
from zerowall.db import DomainError, Store, digest, now
from zerowall.provider import Provider
from zerowall.service import Research
from zerowall.settings import ROOT, Settings
from zerowall.token_factory_generation import configure, profile
from zerowall.usage import normalize

MODEL = "zai-org/GLM-5.3-Flash"
CAP = 0.03
SOURCE_CHAT = "chat_36e90c8e3aa44c92"


def evaluate(call, text, requested):
    measured = normalize("nebius_token_factory", call.get("usage"))
    reasoning = measured["categories"]["output_reasoning"]
    if call.get("http_status") != 200:
        return "request_failed"
    if reasoning is None or measured["status"] == "invalid":
        return "usage_inconclusive"
    # Allow boundary-token accounting differences, never arbitrary overshoot.
    if reasoning > requested + 8:
        return "budget_not_enforced"
    if not text.strip() or call.get("finish_reason") != "stop":
        return "no_complete_public_answer"
    if reasoning < max(1, requested - 8):
        return "within_budget_but_enforcement_unproven"
    return "boundary_observed_with_complete_answer"


def run(args):
    settings = Settings()
    store = Store(settings.data / "zerowall.sqlite3")
    artifacts = Artifacts(settings.artifacts, [settings.api_key, settings.director_token])
    budget = Budget(store, settings)
    provider = Provider(store, settings, budget, artifacts)
    research = Research(store, settings, budget, artifacts, provider)
    report_path = Path(args.report)
    report = json.loads(report_path.read_text("utf-8")) if report_path.exists() else {
        "started_at": now(), "model": MODEL, "maximum_total_usd": CAP,
        "automatic_retries": 0, "results": [], "production_policy_changed": False,
    }
    if len(report["results"]) >= 5:
        raise DomainError("Five diagnostic requests already recorded; stop")
    label = f"{args.placement}:{args.budget}:{args.max_output}"
    if any(x["label"] == label for x in report["results"]):
        raise DomainError("This exact probe was already attempted; no replay")
    generation = deepcopy(profile(settings, {"phase": "opening", "participant": {"model": MODEL}}))
    generation.update(profile="capability_diagnostic", requested_output_tokens=args.max_output)
    native = {"thinking_token_budget": args.budget}
    if args.placement == "nested":
        generation["controls"]["extra_body"] = native
    else:
        generation["controls"].update(native)
    generation["diagnostic"] = {"native_budget": args.budget, "placement": args.placement}
    with store.tx() as c:
        if c.execute("SELECT COUNT(*) FROM records WHERE kind='call' AND json_extract(body,'$.state')='dispatching'").fetchone()[0]:
            raise DomainError("Another inference is active; defer diagnostics")
        verification = budget.verification(c, MODEL)
        source = store.get(c, SOURCE_CHAT, "chat")
        source_hash = digest(source)
        prompt = next(x["content"] for x in research.chat.messages(c, source) if x["role"] == "user")
        request = provider.request(prompt, args.max_output, MODEL)
        configure(request, generation)
        bounds = provider.bounds(request, verification)
        maximum = cost_micro(*bounds, verification["prices"][MODEL])
        if maximum > micro(CAP):
            raise DomainError("Individual probe exceeds diagnostic allowance")
        if not args.execute:
            return {"plan_only": True, "label": label, "maximum_usd": maximum / 1e6,
                    "global_remaining_usd": budget.summary(c)["remaining_usd"],
                    "native_fields": native, "prompt_hash": digest(prompt),
                    "prompt_characters": len(prompt), "reasoning_effort": "low"}
        if "mission_id" not in report:
            brief = MissionBrief(
                title="GLM native thinking-budget compatibility diagnostic",
                goal="Verify whether the hosted endpoint enforces reasoning boundaries and returns a public answer.",
                deliverable="Measured compatibility evidence, timings, public answers and retained receipts.",
                constraints=["At most $0.03 existing credit; aggregate $24 cap remains", "No automatic retry or model fallback"],
                rubric=["Report native control overshoot honestly; HTTP acceptance alone is insufficient"],
                steps=[{"key": "probe", "title": "Measure native reasoning-budget support"}],
                mode="live", budget_usd=CAP,
            )
            report["mission_id"] = research.create_mission(c, brief)["id"]
        mid = report["mission_id"]
        before = {x["id"] for x in store.list(c, "call", mid)}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    # Persist before dispatch: an interrupted script must never silently replay.
    result = {"label": label, "requested_reasoning_tokens": args.budget,
              "placement": args.placement, "maximum_usd": maximum / 1e6,
              "max_completion_tokens": args.max_output, "started_at": now(), "state": "planned_dispatch"}
    report["results"].append(result)
    report_path.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    error = None
    try:
        provider.call(mid, prompt, args.max_output, model=MODEL, plain_text=True,
                      purpose="diagnostic:" + label, generation=generation)
    except DomainError as exc:
        error = exc.message
    with store.tx() as c:
        calls = [x for x in store.list(c, "call", mid) if x["id"] not in before]
        result.update(error=error, completed_at=now(), physical_attempts=len(calls))
        if len(calls) != 1:
            result["state"] = "not_dispatched" if not calls else "unexpected_attempt_count"
        else:
            call = calls[0]
            saved = artifacts.read(store.get(c, call["artifact_id"], "artifact"))
            raw = saved.get("response", {})
            text = (raw.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            reservation = c.execute("SELECT * FROM reservations WHERE id=?", (call["reservation_id"],)).fetchone()
            result.update({k: call.get(k) for k in ("id", "state", "http_status", "usage", "finish_reason", "latency_ms", "ttft_ms", "stream_progress", "artifact_id")})
            result.update(verdict=evaluate(call, text, args.budget), public_answer=text,
                          provider_error=raw.get("error"), reservation_state=reservation["state"],
                          recorded_cost_usd=(reservation["actual_microusd"] or 0) / 1e6 if reservation["state"] == "settled" else None)
        report["source_chat_unchanged"] = digest(store.get(c, SOURCE_CHAT, "chat")) == source_hash
        report["budget"] = budget.summary(c, mid)
    report_path.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    return {k: v for k, v in result.items() if k not in ("public_answer", "stream_progress")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--placement", choices=("top_level", "nested"), default="top_level")
    parser.add_argument("--budget", type=int, choices=(64, 256, 4000), default=64)
    parser.add_argument("--max-output", type=int, choices=(4096, 16384), default=4096)
    parser.add_argument("--report", default=str(ROOT / "docs/validation/glm-native-thinking-budget-live.json"))
    print(json.dumps(run(parser.parse_args()), indent=2))
