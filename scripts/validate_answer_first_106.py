"""Credential-free, replayable Council demo and measured controller pilot.

Synthetic model replies and injected faults prove software behavior, not intelligence.
Never invokes a provider, Tavily or a GPU. Live evidence is recorded separately.
"""

import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from zerowall.api import create_app
from zerowall.council_review_v3 import UnifiedCouncil
from zerowall.review_exports import export_review, verify_review_pack
from zerowall.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
QUESTION = "How can a model council compare engineering approaches while retaining independent proposals, material disagreement and a useful final answer?"


def run(destination):
    destination.mkdir(parents=True, exist_ok=True)
    settings = Settings(Path(tempfile.mkdtemp(prefix="zerowall-answer-first-demo-")))
    settings.api_key = settings.openrouter_api_key = settings.tavily_api_key = ""
    settings.openrouter_enabled = settings.direct_free_confirmed = False
    settings.direct_keys = {}
    app = create_app(settings, run_worker=False)
    original = UnifiedCouncil.demo
    rows = []
    with TestClient(app) as client:
        client.headers["X-ZeroWall-Director"] = "1"
        client.post(
            "/api/session", json={"token": settings.director_token}
        ).raise_for_status()
        for injected in (False, True):
            faulted = []

            def demo(
                self, c, chat, messages, turn, _injected=injected, _faulted=faulted
            ):
                if _injected and turn["phase"] == "extraction" and not _faulted:
                    _faulted.append(True)
                    return "The proposals remain available, but this deliberately injected annotation has no JSON."
                return original(self, c, chat, messages, turn)

            response = client.post(
                "/api/chats",
                headers={"Idempotency-Key": "demo-" + str(injected)},
                json={
                    "provider": "fixture",
                    "models": ["demo/analyst", "demo/critic", "demo/builder"],
                    "prompt": QUESTION,
                },
            )
            response.raise_for_status()
            cid = response.json()["chat"]["id"]
            started = time.perf_counter()
            first = None
            timings = []
            cycles = []
            with patch.object(UnifiedCouncil, "demo", demo):
                for cycle in range(4):
                    if cycle:
                        text = [
                            "Compare deployment effort under the same constraints.",
                            "Keep novel alternatives conditional and identify the next useful test.",
                            "Explain the strongest remaining disagreement without forcing agreement.",
                        ][cycle - 1]
                        kwargs = {
                            "headers": {
                                "Idempotency-Key": f"demo-{injected}-followup-{cycle}"
                            },
                            "json": {"text": text},
                        }
                        once = client.post(f"/api/chats/{cid}/messages", **kwargs)
                        once.raise_for_status()
                        assert (
                            client.post(f"/api/chats/{cid}/messages", **kwargs).json()
                            == once.json()
                        )
                    count = 0
                    while count < 24:
                        turn_start = time.perf_counter()
                        if not app.state.executor.run_once():
                            break
                        timings.append((time.perf_counter() - turn_start) * 1000)
                        count += 1
                        if first is None:
                            first = (time.perf_counter() - started) * 1000
                    view = client.get(f"/api/chats/{cid}").json()
                    assert view["chat"]["status"] == "completed", view["chat"].get(
                        "error"
                    )
                    cycles.append(
                        {
                            "cycle": cycle + 1,
                            "logical_stage_calls": count,
                            "review_state": view["chat"].get("review_state"),
                        }
                    )
                    with app.state.research.store.tx() as c:
                        pack = export_review(app.state.research, c, view["chat"])
                    target = (
                        destination
                        / f"{'injected' if injected else 'healthy'}-cycle-{cycle + 1}.zip"
                    )
                    target.write_bytes(pack)
                    assert verify_review_pack(target)["reproduced"]
                    app.state.research.store.recover()  # A completed chat stays completed after restart recovery.
            rows.append(
                {
                    "case": "injected" if injected else "healthy",
                    "synthetic": True,
                    "question": QUESTION,
                    "cycles": cycles,
                    "time_to_first_public_ms": first,
                    "complete_four_cycle_ms": (time.perf_counter() - started) * 1000,
                    "controller_turn_ms": {
                        "mean": sum(timings) / len(timings),
                        "max": max(timings),
                    },
                    "provider_latency_ms": None,
                    "review_token_share": None,
                    "provider_attempts": 0,
                    "warning_cycles": sum(
                        c["review_state"] == "incomplete" for c in cycles
                    ),
                    "unexpected_stops": 0,
                    "human_quality_labels": 0,
                    "final_text_sha256": hashlib.sha256(
                        view["messages"][-1]["content"].encode()
                    ).hexdigest(),
                }
            )
    result = {
        "passed": True,
        "evidence_class": "synthetic_workflow_and_measured_local_controller",
        "rows": rows,
        "paid_inference_requests": 0,
        "external_tool_requests": 0,
        "provider_quality_or_latency_claim": False,
    }
    (destination / "demo-and-performance.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "passed": True,
                "cycles": 8,
                "paid_inference_requests": 0,
                "output": str(destination),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/validation/answer-first-1.06/demo"
    )
    run(parser.parse_args().output)
