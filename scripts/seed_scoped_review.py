"""Create and reproduce all review protocols using only labelled scripted fixtures."""

import json
from pathlib import Path

from zerowall.api import create_app
from zerowall.contracts import ChatCreate
from zerowall.review_exports import export_review, verify_review_pack
from zerowall.settings import Settings

settings = Settings(Path(__file__).resolve().parents[1] / "data/review-demo")
app = create_app(settings, run_worker=False)
r = app.state.research
results = []
for protocol in ("reviewed_v1", "reviewed_v2", "reviewed_v3", "reviewed_v4"):
    with r.store.tx() as c:
        view = r.chat.create(
            c,
            ChatCreate(
                prompt="Demonstrate a generic review workflow; scripted outputs are not quality evidence.",
                provider="fixture",
                models=["demo/analyst", "demo/critic"],
                mode="reviewed",
                review_protocol=protocol,
                max_rounds=1,
            ),
        )
        cid = view["chat"]["id"]
    for _ in range(20):
        if not app.state.executor.run_once():
            break
    with r.store.tx() as c:
        view = r.chat.view(c, cid)
        if view["chat"]["status"] != "completed":
            raise ValueError(view["chat"].get("error"))
        target = settings.data / (cid + ".zip")
        target.write_bytes(export_review(r, c, view["chat"]))
        results.append(
            {
                "protocol": protocol,
                "reproduction": verify_review_pack(target),
                "provider_attempts": len(
                    r.store.list(c, "call", view["chat"]["mission_id"])
                ),
            }
        )
print(
    json.dumps(
        {
            "origin": "synthetic protocol fixtures, not human quality evidence",
            "reviews": results,
            "all_reproduced": all(
                x["reproduction"]["reproduced"] and x["provider_attempts"] == 0
                for x in results
            ),
        }
    )
)
