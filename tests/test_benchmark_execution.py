"""The complete API path with a deterministic transport double; no real inference."""

import json
import httpx
from zerowall.fixtures import demo_brief, SEATS, submission, review
from zerowall.benchmark import ROOT
from test_budget import configured
from test_provider import fake, FakeClient
from test_workflow import post


def live_double(client, app, monkeypatch, fast_mode="valid"):
    r, unused, first = configured(app, 1)
    with r.store.tx() as c:
        v = r.store.setting(c, "live_verification")
        v["catalog_model_ids"] = r.settings.models
        v["prices"] = {m: {"input": 1, "output": 1} for m in r.settings.models}
        r.store.set_setting(c, "live_verification", v)
    keys = json.loads((ROOT / "benchmark/evaluators/hidden.json").read_text())
    fast = r.settings.models[-1]

    def handler(url, kwargs):
        request = kwargs["json"]
        payload = json.loads(request["messages"][-1]["content"])
        model = request["model"]
        if "shared_context" in payload:
            seat = next(s[0] for s in SEATS if s[2] == payload["role"])
            value = (
                review(payload["hypotheses"], payload["shared_context"]["concerns"])
                if "revealed_submissions" in payload
                else submission(
                    seat,
                    [s["id"] for s in payload["shared_context"]["mission"]["sources"]],
                )
            )
        else:
            sid = payload["sources"][0]["id"]
            key = keys["T" + sid[3:]]
            value = {
                "answer": key["answer"],
                "unit": key["unit"],
                "source_ids": key["required_sources"],
                "finding": " ".join(key["finding_terms"]),
                "next_test": "Run a discriminating independent control with frozen facts.",
                "hardware_measured": False,
            }
            if model == fast and fast_mode == "wrong":
                value["answer"] = 999999
            if model == fast and fast_mode == "invalid":
                value = {"malformed": "forces one escalation"}
        return httpx.Response(
            200,
            json={
                "model": model,
                "choices": [{"message": {"content": json.dumps(value)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )

    fake(monkeypatch, handler)
    brief = demo_brief()
    brief["mode"] = "live"
    m = post(client, "/missions", brief)
    post(client, f"/missions/{m['id']}/freeze", {"expected_revision": 1})
    view = client.get("/api/missions/" + m["id"]).json()
    sid = view["steps"][0]["id"]
    rnd = post(client, f"/steps/{sid}/rounds", {"expected_revision": 1, "mode": "live"})
    app.state.executor.run_once()
    post(client, f"/rounds/{rnd['id']}/reveal", {"expected_revision": 1})
    post(client, f"/rounds/{rnd['id']}/review", {"expected_revision": 1})
    app.state.executor.run_once()
    return client.get("/api/missions/" + m["id"]).json()


def benchmark(client, app, v, split="exploration"):
    sid = v["steps"][0]["id"]
    e = post(
        client,
        f"/steps/{sid}/experiments",
        {
            "expected_revision": 1,
            "title": "A controlled four-cell research pilot",
            "hypothesis_ids": [v["hypotheses"][0]["id"]],
            "capability": "inference.run_benchmark",
            "args": {"split": split, "repeats": 1, "routing_treatment_approved": True},
            "control": "Full sources and fixed strong model",
            "treatment": "Packed sources and explicitly approved fast-first routing",
            "prediction": "Complete workflow cost may fall without new required failures",
            "kill_rule": "Reject a required-case regression or incomplete comparison",
        },
    )
    post(client, f"/experiments/{e['id']}/approve", {"expected_revision": 1})
    app.state.executor.run_once()
    return client.get("/api/missions/" + v["mission"]["id"]).json()


def test_valid_controlled_schedule_uses_exact_models_and_separate_confirmation(
    client, app, monkeypatch
):
    v = live_double(client, app, monkeypatch)
    v = benchmark(client, app, v)
    result = v["evidences"][0]["result"]
    assert (
        result["planned"] == result["completed"] == 16
        and result["integrity_gate"] == "pass"
    )
    assert len(FakeClient.calls) == 24  # 4 commits + 4 cross-reviews + 16 trials
    assert result["cells"]["C11"]["valid"] == 4
    assert v["budget"]["reserved_usd"] == 0 and v["budget"]["unknown_usd"] == 0
    for _, request in FakeClient.calls:
        assert request["json"]["model"] in app.state.research.settings.models
        assert "finding_terms" not in request["json"]["messages"][-1]["content"]
    confirmed = benchmark(client, app, v, "confirmation")
    confirmation = confirmed["evidences"][-1]["result"]
    assert confirmation["independent_tasks"] == 8 and confirmation["completed"] == 32
    assert confirmation["split"] == "confirmation"
    count = len(FakeClient.calls)
    retried = benchmark(client, app, confirmed, "confirmation")
    assert len(FakeClient.calls) == count
    assert retried["experiments"][-1]["status"] == "failed"


def test_well_formed_wrong_fast_answers_remain_policy_failures(
    client, app, monkeypatch
):
    v = live_double(client, app, monkeypatch, "wrong")
    v = benchmark(client, app, v)
    result = v["evidences"][0]["result"]
    assert result["cells"]["C11"]["valid"] == 0
    assert result["comparisons"]["C11"]["quality_gate"] == "fail"
    assert len(FakeClient.calls) == 24  # Hidden keys never caused escalation.
    assert v["steps"][0]["needs_reframe"]


def test_escalation_counts_both_requests_and_full_cost(client, app, monkeypatch):
    v = live_double(client, app, monkeypatch, "invalid")
    v = benchmark(client, app, v)
    result = v["evidences"][0]["result"]
    assert result["cells"]["C11"]["valid"] == 4
    assert (
        result["cells"]["C11"]["total_cost_usd"]
        == 2 * result["cells"]["C00"]["total_cost_usd"]
    )
    assert len(FakeClient.calls) == 32
    assert v["budget"]["reserved_usd"] == 0
