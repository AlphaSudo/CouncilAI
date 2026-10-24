"""One bounded, synthetic generic integration case; never a quality benchmark."""

from pathlib import Path
import json
from zerowall.settings import Settings
from zerowall.api import create_app
from zerowall.contracts import ChatCreate
from zerowall.db import now
from zerowall.review_exports import export_review, verify_review_pack

settings = Settings(
    Path(__file__).resolve().parents[1] / "data" / "review-live-validation"
)
app = create_app(settings, run_worker=False)
r = app.state.research
with r.store.tx() as c:
    previous = c.execute(
        "SELECT id FROM records WHERE kind='chat' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    if previous:
        cid = previous[0]
    else:
        view = r.chat.create(
            c,
            ChatCreate(
                prompt="Recommend a local backup workflow for a solo developer with $0 paid services. Compare manual folder copies with scripted versioned backups; distinguish version control from backup, state uncertainty and one restore test. Keep each initial answer to at most two material claims and 150 words.",
                provider="direct_council",
                models=list(r.direct_provider.entries()),
                mode="reviewed",
                max_rounds=1,
            ),
        )
        cid = view["chat"]["id"]
print(
    json.dumps({"chat_id": cid, "purpose": "synthetic generic integration case"}),
    flush=True,
)
for _ in range(24):
    with r.store.tx() as c:
        view = r.chat.view(c, cid)
    if view["chat"]["status"] in (
        "completed",
        "failed",
        "unavailable",
        "paused",
        "cancelled",
        "interrupted",
    ):
        break
    print(
        json.dumps(
            {
                "status": view["chat"]["status"],
                "next_phase": (view["next_turn"] or {}).get("phase"),
                "attempts": view["budget"]["attempts"],
                "retry_wait": view["chat"].get("retry_wait"),
            }
        ),
        flush=True,
    )
    if not app.state.executor.run_once():
        break  # Durable retry waits are resumed by a later explicit invocation; no busy wait.
with r.store.tx() as c:
    view = r.chat.view(c, cid)
    calls = r.store.list(c, "call", view["chat"]["mission_id"])
    summary = {
        "checked_at": now(),
        "chat_id": cid,
        "status": view["chat"]["status"],
        "error": view["chat"].get("error"),
        "phases": [m["phase"] for m in view["messages"]],
        "models": [
            {"provider": p.get("provider"), "model": p.get("actual_model")}
            for p in view["chat"]["participants"]
        ],
        "claims": len(view["review"]["claims"]),
        "attempts": len(calls),
        "reported_costs_usd": [x.get("cost_usd") for x in calls],
        "human_quality_review": "pending",
        "source": "genuine direct-provider responses to an authored test prompt",
    }
    if view["chat"]["status"] == "completed":
        pack = settings.data / "review.zip"
        pack.write_bytes(export_review(r, c, view["chat"]))
        summary["offline_reproduction"] = verify_review_pack(pack)
target = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "validation"
    / "reviewed-council-live.json"
)
target.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary), flush=True)
