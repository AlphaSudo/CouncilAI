"""Explicitly start or inspect ONE main-database current Council integration run; never a quality pilot."""

import argparse
import json
import sqlite3
import uuid
from pathlib import Path

import httpx

from zerowall.db import now
from zerowall.review_exports import verify_review_pack

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data/unified-smoke.json"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--start",
    action="store_true",
    help="Explicitly authorize one preflighted council through the running local app",
)
args = parser.parse_args()
with httpx.Client(
    base_url="http://127.0.0.1:8000", headers={"X-ZeroWall-Director": "1"}, timeout=20
) as client:
    client.post("/api/session/local", json={}).raise_for_status()
    if args.start:
        if STATE.exists():
            raise ValueError(
                "A smoke conversation already exists; inspect it without --start"
            )
        boot = client.get("/api/chats/bootstrap").json()
        models = [m["id"] for m in boot["providers"]["direct_council"]["models"]]
        preview = client.get(
            "/api/chats/preview",
            params={
                "provider": "direct_council",
                "models": ",".join(models),
                "max_rounds": 1,
            },
        ).json()
        if preview["blocked"]:
            raise ValueError(preview["reason"])
        response = client.post(
            "/api/chats",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={
                "prompt": "Give the best two scheduling approaches for a single-user desktop editor: bounded FIFO versus a priority queue when interactive edits and background indexing coexist. Hard requirements: offline operation, $0 additional services, saved jobs must survive restart. No performance or reliability experiment has been run. Distinguish queue ordering from durable persistence, give one necessary operating condition, and propose one discriminating test. Keep each independent opening to two material assertions and 120 words; no invented measurements.",
                "provider": "direct_council",
                "models": models,
                "max_rounds": 1,
            },
        )
        response.raise_for_status()
        STATE.write_text(
            json.dumps(
                {
                    "chat_id": response.json()["chat"]["id"],
                    "preview": preview,
                    "created_at": now(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    state = json.loads(STATE.read_text())
    response = client.get("/api/chats/" + state["chat_id"])
    response.raise_for_status()
    view = response.json()
    review = view["review"]
    connection = sqlite3.connect(
        "file:" + (ROOT / "data/zerowall.sqlite3").as_posix() + "?mode=ro", uri=True
    )
    calls = [
        json.loads(row[0])
        for row in connection.execute(
            "SELECT body FROM records WHERE kind='call' AND mission_id=?",
            (view["chat"]["mission_id"],),
        )
    ]
    connection.close()
    summary = {
        "checked_at": now(),
        "chat_id": state["chat_id"],
        "url": "http://127.0.0.1:8000/?chat=" + state["chat_id"],
        "protocol": view["chat"]["protocol"]["version"],
        "status": view["chat"]["status"],
        "error": view["chat"].get("error"),
        "next_phase": (view.get("next_turn") or {}).get("phase"),
        "phases": [m["phase"] for m in view["messages"]],
        "claims": len(review["claims"]),
        "groups": len(review["groups"]),
        "families": len(review.get("families", [])),
        "audit_results": [{k: a.get(k) for k in ("state", "scope", "reason")} for a in review.get("audit_results", [])],
        "execution_plan": review.get("execution_plan"),
        "inventory_status": review.get("inventory_status"),
        "observations": len(review["observations"]),
        "attempts": len(calls),
        "reported_costs_usd": [c.get("cost_usd") for c in calls],
        "attempt_details": [
            {
                k: call.get(k)
                for k in (
                    "id",
                    "provider",
                    "model",
                    "state",
                    "purpose",
                    "usage",
                    "cost_status",
                )
            }
            for call in calls
        ],
        "models": [
            {"provider": p.get("provider"), "model": p.get("actual_model")}
            for p in view["chat"]["participants"]
        ],
        "synthesis_fallback": review.get("synthesis_fallback"),
        "answer_disposition": review.get("answer_disposition"),
        "human_quality_review": "pending",
        "test_kind": "genuine compatibility run, authored development prompt; not independent semantic evaluation",
    }
    if summary["status"] == "completed":
        item = client.post(
            f"/api/chats/{state['chat_id']}/review/exports",
            json={},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        item.raise_for_status()
        pack = client.get(item.json()["download"])
        pack.raise_for_status()
        target = ROOT / "data/unified-smoke-review.zip"
        target.write_bytes(pack.content)
        summary["reproduction"] = verify_review_pack(target)
    (ROOT / "docs/validation/council-1.03-live.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
