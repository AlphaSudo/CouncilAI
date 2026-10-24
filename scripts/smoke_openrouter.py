"""Run the real council/executor against one pinned free model in a fresh database.

No changes to the app's database, Nebius verification or model policy. Only the
bundled public demo sources are sent. No benchmark or scientific conclusion.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from zerowall.artifacts import Artifacts
from zerowall.budget import Budget
from zerowall.contracts import ExperimentInput, MissionBrief, RoundInput
from zerowall.db import DomainError, Store, uid
from zerowall.executor import Executor
from zerowall.fixtures import demo_brief
from zerowall.free_provider import BASE_URL, FREE_MODELS, MODEL, OpenRouterFreeProvider
from zerowall.process_lock import ProcessLock
from zerowall.service import Research
from zerowall.settings import ROOT, Settings


def run(report_path=None, model=MODEL):
    data_dir = ROOT / "data" / "openrouter-smoke" / uid("run")
    settings = Settings(data_dir)
    # This Settings instance is private to this process, never served as the app.
    settings.base_url = BASE_URL
    store = Store(settings.data / "zerowall.sqlite3")
    artifacts = Artifacts(
        settings.artifacts, [settings.api_key, settings.openrouter_api_key]
    )
    budget = Budget(store, settings)
    provider = OpenRouterFreeProvider(
        store,
        settings,
        artifacts,
        progress=lambda text: print(text, flush=True),
        model=model,
    )
    research = Research(
        store, settings, budget, artifacts, provider, free_provider=provider
    )
    executor = Executor(research)
    lock = ProcessLock(settings.data / "executor.lock")
    lock.acquire()
    mid = None
    summary = {
        "checked_at": datetime.now(UTC).isoformat(),
        "provider": "openrouter_free",
        "model": model,
        "scope": "Software integration only; does not satisfy Nebius runtime or performance gates",
        "data_directory": str(settings.data),
        "passed": False,
        "automatic_retries": 0,
        "fallback_models": [],
    }
    try:
        brief = demo_brief()
        brief.update(
            title="Free OpenRouter integration smoke test",
            mode="live",
            provider="openrouter_free",
            budget_usd=0,
            openrouter_model=model,
        )
        brief["constraints"].append(
            "OpenRouter free test only; no Nebius runtime or performance claim"
        )
        with store.tx() as c:
            mission = research.create_mission(c, MissionBrief.model_validate(brief))
            mid = mission["id"]
            research.freeze(c, mid, 1)
            step = store.list(c, "step", mid)[0]
            rnd = research.round(
                c, step["id"], RoundInput(expected_revision=1, mode="live")
            )
        executor.run_once()
        with store.tx() as c:
            current = store.get(c, rnd["id"], "round")
            if current["status"] == "failed":
                raise DomainError(current["error"])
            private = research.public_round(c, current)
            assert "submissions" not in private
            assert len(store.list(c, "submission", mid)) == 4
            summary["four_private_commits"] = True
            research.reveal(c, rnd["id"], 1)
            assert (
                len(
                    research.public_round(c, store.get(c, rnd["id"], "round"))[
                        "submissions"
                    ]
                )
                == 4
            )
            summary["atomic_reveal"] = True
            research.review(c, rnd["id"], 1)
        executor.run_once()
        with store.tx() as c:
            current = store.get(c, rnd["id"], "round")
            if current["status"] == "failed":
                raise DomainError(current["error"])
            assert current["reviews_complete"]
            assert len(store.list(c, "review", mid)) == 4
            summary["four_valid_cross_reviews"] = True
            hypothesis = store.list(c, "hypothesis", mid)[0]
            experiment = research.experiment(
                c,
                step["id"],
                ExperimentInput(
                    expected_revision=1,
                    title="Check numerical tool after a real model council",
                    hypothesis_ids=[hypothesis["id"]],
                    capability="analysis.calculate_bound",
                    args={
                        "bytes_moved": 2e9,
                        "bandwidth_gbps": 100,
                        "assumptions": [
                            "Hypothetical serial transfer; no overlap or hardware measurement"
                        ],
                    },
                    control="Fixed declared units and transfer size",
                    treatment="Deterministic arithmetic tool",
                    prediction="The declared bandwidth-only lower bound equals 20 ms",
                    kill_rule="Reject if the deterministic tool returns a different numerical bound",
                ),
            )
            research.approve_experiment(c, experiment["id"], 1)
        executor.run_once()
        with store.tx() as c:
            evidence = store.list(c, "evidence", mid)
            assert len(evidence) == 1 and evidence[0]["evidence_class"] == "calculated"
            result = artifacts.read(
                store.get(c, evidence[0]["artifact_id"], "artifact")
            )
            assert result["result"]["minimum_seconds"] * 1000 == 20
            summary["numerical_tool_minimum_ms"] = 20
        summary["passed"] = True
    except Exception as exc:  # noqa: BLE001 - write a credential-safe failure summary
        # Never include raw provider text, request headers or exception bodies.
        summary["error"] = (
            exc.message if isinstance(exc, DomainError) else type(exc).__name__
        )
    finally:
        with store.tx() as c:
            calls = store.list(c, "call", mid) if mid else []
            summary.update(
                mission_id=mid,
                dispatched_calls=len(calls),
                completed_calls=sum(x["state"] == "completed" for x in calls),
                reported_costs_usd=[
                    x.get("usage", {}).get("cost")
                    if isinstance(x.get("usage"), dict)
                    else None
                    for x in calls
                ],
                budget=budget.summary(c, mid, "openrouter_free"),
                nebius_verification_present=bool(
                    store.setting(c, "live_verification", {})
                ),
            )
        summary = artifacts.redact(summary)
        (settings.data / "summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        if report_path:
            Path(report_path).write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
        lock.release()
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", help="Optional path for the sanitized validation summary"
    )
    parser.add_argument("--model", choices=FREE_MODELS, default=MODEL)
    args = parser.parse_args()
    result = run(args.report, args.model)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
