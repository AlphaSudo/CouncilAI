import json
import uuid

import httpx
import pytest
from test_workflow import experiment, post

from zerowall.contracts import MissionBrief
from zerowall.db import DomainError, canonical, now
from zerowall.fixtures import demo_brief, review, submission
from zerowall.free_provider import BASE_URL, MODEL


def free_brief():
    return {
        **demo_brief(),
        "mode": "live",
        "provider": "openrouter_free",
        "budget_usd": 0,
    }


def mock_free_council(app, monkeypatch):
    research = app.state.research
    research.settings.openrouter_api_key = "unit-test-free-key"
    calls = []
    client_type = httpx.Client

    def handle(request):
        assert str(request.url).startswith(BASE_URL + "/")
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": MODEL, "pricing": {"prompt": "0", "completion": "0"}}
                    ]
                },
            )
        body = json.loads(request.content)
        calls.append(body)
        try:
            payload = json.loads(body["messages"][-1]["content"])
        except ValueError:
            payload = {}
        if payload.get("revealed_submissions"):
            content = review(
                payload["hypotheses"], payload["shared_context"]["concerns"]
            )
        elif payload.get("output_schema"):
            content = submission(
                "hardware",
                [s["id"] for s in payload["shared_context"]["mission"]["sources"]],
            )
        else:
            content = {"observation": "A bounded trial returned JSON"}
        return httpx.Response(
            200,
            json={
                "model": MODEL,
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(content)},
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 100, "cost": 0},
            },
        )

    monkeypatch.setattr(
        "zerowall.free_provider.httpx.Client",
        lambda **kwargs: client_type(**kwargs, transport=httpx.MockTransport(handle)),
    )
    monkeypatch.setattr("zerowall.free_provider.time.sleep", lambda seconds: None)
    return calls


def test_free_app_round_privacy_trial_and_separate_billing(client, app, monkeypatch):
    calls = mock_free_council(app, monkeypatch)
    m = post(client, "/missions", free_brief())
    assert m["brief"]["openrouter_model"] == MODEL
    post(client, f"/missions/{m['id']}/freeze", {"expected_revision": 1})
    view = client.get("/api/missions/" + m["id"]).json()
    sid = view["steps"][0]["id"]
    rnd = post(client, f"/steps/{sid}/rounds", {"expected_revision": 1, "mode": "live"})
    app.state.executor.run_once()
    private = client.get("/api/missions/" + m["id"]).json()
    assert private["rounds"][0]["status"] == "committed"
    assert "submissions" not in private["rounds"][0]
    assert not private["artifacts"]
    assert private["budget"]["attempts"] == 4
    post(client, f"/rounds/{rnd['id']}/reveal", {"expected_revision": 1})
    post(client, f"/rounds/{rnd['id']}/review", {"expected_revision": 1})
    app.state.executor.run_once()
    view = client.get("/api/missions/" + m["id"]).json()
    assert view["rounds"][0]["reviews_complete"]
    assert len(view["rounds"][0]["reviews"]) == 4
    view = experiment(
        client,
        app,
        view,
        "inference.run_trial",
        {
            "prompt": "Return a brief JSON observation",
            "max_output_tokens": 128,
        },
    )
    assert view["evidences"][0]["provider"] == "openrouter_free"
    assert view["evidences"][0]["result"]["provider"] == "openrouter_free"
    assert len(calls) == 9
    assert all(c["model"] == MODEL for c in calls)
    assert view["budget"]["absolute_cap_usd"] == 0
    assert view["budget"]["settled_usd"] == 0
    assert view["budget"]["remaining_calls"] == 3
    bootstrap = client.get("/api/bootstrap").json()
    assert bootstrap["openrouter_free"]["ready"]
    assert not bootstrap["live_ready"]
    assert bootstrap["budget"]["attempts"] == 0
    assert (
        client.patch(
            f"/api/missions/{m['id']}/draft?expected_revision=1",
            json={**free_brief(), "provider": "nebius_token_factory", "budget_usd": 1},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        ).status_code
        == 409
    )
    with app.state.research.store.tx() as c:
        assert not app.state.research.store.setting(c, "live_verification", {})
        with pytest.raises(DomainError):
            app.state.research.provider.choose(c)


@pytest.mark.parametrize(
    "change",
    [
        {"budget_usd": 1},
        {"mode": "fixture"},
        {"openrouter_model": "nvidia/nemotron-3-super-120b-a12b"},
    ],
)
def test_free_mission_cannot_authorize_money_or_paid_models(client, change):
    post(client, "/missions", {**free_brief(), **change}, 422)


def test_benchmark_is_rejected_before_dispatch_for_free_missions(
    client, app, monkeypatch
):
    calls = mock_free_council(app, monkeypatch)
    m = post(client, "/missions", free_brief())
    post(client, f"/missions/{m['id']}/freeze", {"expected_revision": 1})
    with app.state.research.store.tx() as c:
        research = app.state.research
        sid = research.store.list(c, "step", m["id"])[0]["id"]
        from zerowall.contracts import ExperimentInput
        # The usual hypothesis provenance is still required; create it through a round below.
    rnd = post(client, f"/steps/{sid}/rounds", {"expected_revision": 1, "mode": "live"})
    app.state.executor.run_once()
    post(client, f"/rounds/{rnd['id']}/reveal", {"expected_revision": 1})
    post(client, f"/rounds/{rnd['id']}/review", {"expected_revision": 1})
    app.state.executor.run_once()
    with research.store.tx() as c:
        h = research.store.list(c, "hypothesis", m["id"])[0]
        e = research.experiment(
            c,
            sid,
            ExperimentInput(
                expected_revision=1,
                title="A controlled routing benchmark",
                hypothesis_ids=[h["id"]],
                capability="inference.run_benchmark",
                args={"routing_treatment_approved": True},
                control="Fixed first model",
                treatment="Fast first routing",
                prediction="Compare cost under fixed quality controls",
                kill_rule="Reject invalid tasks",
            ),
        )
        with pytest.raises(DomainError) as error:
            research.approve_experiment(c, e["id"], 1)
        assert error.value.code == 412
    assert len(calls) == 8


def test_ledger_and_attempt_caps_do_not_mix_providers(app):
    r = app.state.research
    with r.store.tx() as c:
        c.execute(
            "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
            ("nebius", "paid", "paid-call", 2000, 2000, "settled", canonical({})),
        )
        c.execute(
            "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
            (
                "free",
                "free",
                "free-call",
                0,
                0,
                "settled",
                canonical({"provider": "openrouter_free", "catalog_checked_at": now()}),
            ),
        )
        assert r.budget.summary(c)["settled_usd"] == 0.002
        assert r.budget.summary(c)["attempts"] == 1
        assert r.budget.summary(c, "free", "openrouter_free")["settled_usd"] == 0
        assert r.free_provider.capacity(c, "free")["mission_attempts"] == 1
        from zerowall.free_limits import DAILY_ATTEMPTS

        for i in range(DAILY_ATTEMPTS - 1):
            c.execute(
                "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
                (
                    str(i),
                    "other-free",
                    str(i),
                    0,
                    0,
                    "settled",
                    canonical(
                        {"provider": "openrouter_free", "catalog_checked_at": now()}
                    ),
                ),
            )
        with pytest.raises(DomainError):
            r.free_provider.capacity(c, "new-mission")


def test_legacy_mission_default_keeps_token_factory():
    assert MissionBrief.model_validate(demo_brief()).provider == "nebius_token_factory"
