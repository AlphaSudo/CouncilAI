"""Plan, or explicitly execute, one ledger-backed Beam integration diagnostic."""

import argparse
import json
from pathlib import Path

from zerowall.artifacts import Artifacts
from zerowall.budget import Budget, cost_micro
from zerowall.contracts import MissionBrief
from zerowall.db import DomainError, Store, now
from zerowall.provider import Provider
from zerowall.service import Research
from zerowall.settings import ROOT, Settings
from zerowall.token_factory_generation import configure, profile
from zerowall.usage import normalize

MODEL = "reflection/beam"
REPORT = ROOT / "docs/validation/reflection-beam-live.json"


def run(execute=False):
    if execute and REPORT.exists():
        raise DomainError("A Beam diagnostic is already recorded; no automatic replay")
    settings = Settings()
    store = Store(settings.data / "zerowall.sqlite3")
    artifacts = Artifacts(settings.artifacts, [settings.api_key, settings.director_token])
    budget = Budget(store, settings)
    provider = Provider(store, settings, budget, artifacts)
    research = Research(store, settings, budget, artifacts, provider)
    generation = profile(settings, {"phase": "opening", "participant": {"model": MODEL}})
    generation["requested_output_tokens"] = 16384  # Diagnostic only, not the production opening policy.
    with store.tx() as c:
        verification = budget.verification(c, MODEL)
        chat = store.get(c, "chat_0bd9f187edcc4289", "chat")
        prompt = next(m["content"] for m in research.chat.messages(c, chat) if m["role"] == "user")
        request = provider.request(prompt, 16384, MODEL)
        configure(request, generation)
        maximum = cost_micro(*provider.bounds(request, verification), verification["prices"][MODEL]) / 1e6
        if maximum > 0.03:
            raise DomainError("Conservative maximum exceeds the $0.03 diagnostic cap")
        report = {"started_at": now(), "model": MODEL, "reasoning_effort": "low",
                  "reasoning_target_tokens": 4000, "hard_thinking_limit_claimed": False,
                  "combined_completion_ceiling": 16384, "maximum_usd": maximum,
                  "mission_cap_usd": 0.03, "automatic_retries": 0,
                  "production_opening_limits_changed_by_probe": False}
        if not execute:
            return {**report, "plan_only": True}
        if c.execute("SELECT COUNT(*) FROM records WHERE kind='call' AND json_extract(body,'$.state')='dispatching'").fetchone()[0]:
            raise DomainError("An inference request is active; diagnostic deferred")
        mission = research.create_mission(c, MissionBrief(
            title="Reflection Beam low-effort 4K advisory diagnostic",
            goal="Verify the real Beam endpoint returns a public answer with measured reasoning usage.",
            deliverable="Recorded request, response timing, usage and conservative cost estimate.",
            constraints=["At most $0.03 existing credit within the aggregate $24 cap", "One request; no automatic retry"],
            rubric=["A completed public answer and measured usage; no latency or hard-cap guarantee"],
            steps=[{"key": "probe", "title": "Run one model integration diagnostic"}],
            mode="live", budget_usd=0.03,
        ))
        report["mission_id"] = mission["id"]
    REPORT.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    error = None
    try:
        provider.call(mission["id"], prompt, 16384, model=MODEL, generation=generation, purpose="diagnostic:beam-low-4k")
    except DomainError as exc:
        error = exc.message
    with store.tx() as c:
        calls = store.list(c, "call", mission["id"])
        report.update(completed_at=now(), physical_attempts=len(calls), error=error,
                      budget=budget.summary(c, mission["id"]))
        if calls:
            call = calls[-1]
            report["call"] = {k: call.get(k) for k in ("id", "state", "http_status", "finish_reason", "usage", "latency_ms", "ttft_ms", "artifact_id", "generation")}
            usage = normalize("nebius_token_factory", call.get("usage"))
            report["tokens"] = usage["categories"]
            if call.get("artifact_id"):
                saved = artifacts.read(store.get(c, call["artifact_id"], "artifact"))
                report["public_answer"] = ((saved.get("response", {}).get("choices") or [{}])[0].get("message", {}).get("content") or "")
            report["complete_public_answer"] = bool(report.get("public_answer", "").strip()) and call.get("finish_reason") == "stop"
            report["scientific_quality_evaluated"] = False
    REPORT.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    return {k: v for k, v in report.items() if k != "public_answer"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    print(json.dumps(run(parser.parse_args().execute), indent=2))
