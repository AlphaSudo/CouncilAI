import json, uuid
import pytest
from zerowall.fixtures import demo_brief
from zerowall.reports import verify_pack, reproduce


def post(client, path, body, status=200, key=None):
    response = client.post(
        "/api" + path, json=body, headers={"Idempotency-Key": key or str(uuid.uuid4())}
    )
    assert response.status_code == status, response.text
    return response.json()


def mission(client):
    m = post(client, "/missions", demo_brief())
    post(client, f"/missions/{m['id']}/freeze", {"expected_revision": 1})
    return client.get("/api/missions/" + m["id"]).json()


def reviewed(client, app):
    v = mission(client)
    s = v["steps"][0]
    r = post(
        client, f"/steps/{s['id']}/rounds", {"expected_revision": 1, "mode": "fixture"}
    )
    assert app.state.executor.run_once()
    post(client, f"/rounds/{r['id']}/reveal", {"expected_revision": 1})
    post(client, f"/rounds/{r['id']}/review", {"expected_revision": 1})
    assert app.state.executor.run_once()
    return client.get("/api/missions/" + v["mission"]["id"]).json()


def experiment(client, app, v, cap="analysis.calculate_bound", args=None):
    s = v["steps"][0]
    e = post(
        client,
        f"/steps/{s['id']}/experiments",
        {
            "expected_revision": s["revision"],
            "title": "Check the declared analytical bound",
            "hypothesis_ids": [v["hypotheses"][0]["id"]],
            "capability": cap,
            "args": args
            or {
                "bytes_moved": 2e9,
                "bandwidth_gbps": 100,
                "assumptions": ["Supplied bandwidth; no overlap"],
            },
            "control": "Declared input values",
            "treatment": "Fixed analytical formula",
            "prediction": "At least 20 ms under the declared assumptions",
            "kill_rule": "Reject a smaller bandwidth-only bound",
        },
    )
    post(client, f"/experiments/{e['id']}/approve", {"expected_revision": 1})
    app.state.executor.run_once()
    return client.get("/api/missions/" + v["mission"]["id"]).json()


def decision(client, v, verdict="inconclusive"):
    return post(
        client,
        f"/steps/{v['steps'][0]['id']}/decisions",
        {
            "expected_revision": v["steps"][0]["revision"],
            "conclusion": "The arithmetic bound is 20 ms; no provider hardware has been measured.",
            "verdict": verdict,
            "agreement": "majority_with_dissent",
            "alternatives": ["Collect real API evidence"],
            "reasons": ["The calculation addresses arithmetic only"],
            "dissent": ["The API mechanism remains unresolved"],
            "assumptions": ["100 decimal GB/s is supplied"],
            "reopen_triggers": ["Different transfer assumptions"],
            "evidence_ids": [v["evidences"][0]["id"]],
        },
    )


def test_private_commit_reveal_including_raw_artifacts(client, app):
    v = mission(client)
    sid = v["steps"][0]["id"]
    mid = v["mission"]["id"]
    r = post(
        client, f"/steps/{sid}/rounds", {"expected_revision": 1, "mode": "fixture"}
    )
    post(client, f"/rounds/{r['id']}/reveal", {"expected_revision": 1}, 409)
    app.state.executor.run_once()
    public = client.get("/api/missions/" + mid).json()
    assert "submissions" not in public["rounds"][0]
    assert not public["artifacts"] and not public["hypotheses"]
    assert "A bandwidth lower bound constrains" not in json.dumps(public)
    with app.state.research.store.tx() as c:
        private = app.state.research.store.list(c, "artifact", mid)
    assert len(private) == 4
    assert client.get("/api/artifacts/" + private[0]["id"]).status_code == 403
    revealed = post(client, f"/rounds/{r['id']}/reveal", {"expected_revision": 1})
    assert len(revealed["submissions"]) == 4
    assert len({s["context_hash"] for s in revealed["submissions"]}) == 1
    for artifact in private:
        value = client.get("/api/artifacts/" + artifact["id"]).json()
        assert "revealed_submissions" not in value["prompt"]
        assert "submissions" not in value["prompt"]["shared_context"]


def test_full_local_loop_and_portable_pack(client, app, tmp_path):
    v = experiment(client, app, reviewed(client, app))
    assert v["evidences"][0]["result"]["minimum_seconds"] == 0.02
    s = v["steps"][0]
    post(
        client,
        f"/steps/{s['id']}/reframes",
        {
            "expected_revision": 1,
            "reason": "A calculated bound cannot explain provider internals",
            "interpretation": "Separate a physical lower bound from client-observed API workflow latency",
            "prediction_comparison": "The supplied arithmetic bound is reproduced; the API mechanism remains untested",
            "changed_assumptions": [
                "Do not equate an analytical bound with observed provider behavior"
            ],
            "alternative_explanations": [
                "Client queueing or model routing may dominate the complete workflow"
            ],
            "next_action": "Collect a bounded API timing control after billing verification",
            "evidence_ids": [v["evidences"][0]["id"]],
            "hypothesis_states": {v["hypotheses"][0]["id"]: "supported"},
        },
    )
    d = decision(client, v)
    approved = post(client, f"/decisions/{d['id']}/approve", {"expected_revision": 1})
    assert approved["status"] == "approved"
    assert any(g["status"] == "unknown" for g in approved["gates"])
    pack = post(client, f"/missions/{v['mission']['id']}/exports", {})
    response = client.get("/api/exports/" + pack["id"] + "/download")
    path = tmp_path / "pack.zip"
    path.write_bytes(response.content)
    assert verify_pack(path)["valid"]
    result = reproduce(path)
    assert result["all_match"] and len(result["reanalysis"]) == 1
    assert result["network_calls"] == 0
    assert b"test-key-never-network" not in response.content


def test_unknown_hard_gates_block_confirmation(client, app):
    v = experiment(client, app, reviewed(client, app))
    d = decision(client, v, "confirmed")
    post(client, f"/decisions/{d['id']}/approve", {"expected_revision": 1}, 409)


def test_concern_requires_fresh_four_seat_response_and_disposition(client, app):
    v = experiment(client, app, reviewed(client, app))
    s = v["steps"][0]
    d = decision(client, v)
    concern = post(
        client,
        f"/steps/{s['id']}/concerns",
        {
            "expected_revision": 1,
            "text": "Could escalation costs erase the claimed cost improvement?",
        },
    )
    post(client, f"/decisions/{d['id']}/approve", {"expected_revision": 1}, 409)
    post(
        client,
        f"/concerns/{concern['id']}/resolve",
        {
            "expected_revision": 1,
            "disposition": "Keep escalation costs in the workflow metric",
        },
        409,
    )
    old = v["rounds"][0]
    post(client, f"/rounds/{old['id']}/review", {"expected_revision": 2}, 409)
    r = post(
        client, f"/steps/{s['id']}/rounds", {"expected_revision": 2, "mode": "fixture"}
    )
    app.state.executor.run_once()
    post(client, f"/rounds/{r['id']}/reveal", {"expected_revision": 2})
    post(client, f"/rounds/{r['id']}/review", {"expected_revision": 2})
    app.state.executor.run_once()
    current = client.get("/api/missions/" + v["mission"]["id"]).json()
    assert len(current["concerns"][0]["acknowledged_by"]) == 4
    resolved = post(
        client,
        f"/concerns/{concern['id']}/resolve",
        {
            "expected_revision": 1,
            "disposition": "Retain every escalation charge and reject incomplete comparisons.",
        },
    )
    assert resolved["status"] == "resolved"


def test_reopen_invalidates_transitive_dependencies(client, app):
    v = experiment(client, app, reviewed(client, app))
    d = decision(client, v)
    post(client, f"/decisions/{d['id']}/approve", {"expected_revision": 1})
    post(
        client, f"/steps/{v['steps'][0]['id']}/control/reopen", {"expected_revision": 1}
    )
    current = client.get("/api/missions/" + v["mission"]["id"]).json()
    assert current["steps"][1]["stale"]
    assert current["decisions"][0]["status"] == "stale"
    post(
        client,
        f"/steps/{v['steps'][1]['id']}/control/reopen",
        {"expected_revision": 2},
        409,
    )


def test_auth_csrf_idempotency_and_cycle_validation(client, app):
    key = str(uuid.uuid4())
    one = post(client, "/missions", demo_brief(), key=key)
    two = post(client, "/missions", demo_brief(), key=key)
    assert one["id"] == two["id"]
    changed = demo_brief()
    changed["title"] = "Changed mission"
    post(client, "/missions", changed, 409, key)
    bad = demo_brief()
    bad["steps"][0]["depends_on"] = ["confirm"]
    post(client, "/missions", bad, 422)
    assert (
        client.post(
            "/api/missions",
            json=demo_brief(),
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    client.cookies.clear()
    assert client.get("/api/bootstrap").status_code == 401


def test_pause_prevents_queued_dispatch(client, app):
    v = mission(client)
    s = v["steps"][0]
    post(
        client, f"/steps/{s['id']}/rounds", {"expected_revision": 1, "mode": "fixture"}
    )
    post(client, f"/steps/{s['id']}/control/pause", {"expected_revision": 1})
    assert not app.state.executor.run_once()
    post(client, f"/steps/{s['id']}/control/resume", {"expected_revision": 1})
    assert app.state.executor.run_once()


def test_arbitrary_execution_capability_is_rejected(client, app):
    v = reviewed(client, app)
    post(
        client,
        f"/steps/{v['steps'][0]['id']}/experiments",
        {
            "expected_revision": 1,
            "title": "Execute untrusted text",
            "hypothesis_ids": [v["hypotheses"][0]["id"]],
            "capability": "shell.run",
            "args": {"cmd": "whoami"},
            "control": "none",
            "treatment": "arbitrary command",
            "prediction": "Should never execute",
            "kill_rule": "Any shell dispatch violates the contract",
        },
        422,
    )
