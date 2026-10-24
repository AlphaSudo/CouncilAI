import hashlib, json, sqlite3, zipfile
import pytest
from test_workflow import reviewed, experiment, post, decision, mission
from zerowall.reports import verify_pack


def test_report_escapes_html_and_pack_detects_tampering(client, app, tmp_path):
    v = experiment(
        client,
        app,
        reviewed(client, app),
        cap="evidence.import",
        args={
            "content": '<script>alert("bad")</script>',
            "source": "Authored test input",
            "collected_at": "2026-10-18T00:00:00Z",
            "method": "Literal source-preserving test import",
        },
    )
    pack = post(client, f"/missions/{v['mission']['id']}/exports", {})
    raw = client.get("/api/exports/" + pack["id"] + "/download").content
    path = tmp_path / "pack.zip"
    path.write_bytes(raw)
    with zipfile.ZipFile(path) as z:
        html = z.read("report.html").decode()
        assert "<script>" not in html and "&lt;script&gt;" in html
        content = {name: z.read(name) for name in z.namelist()}
    content["report.md"] += b" altered"
    with zipfile.ZipFile(path, "w") as z:
        for name, value in content.items():
            z.writestr(name, value)
    with pytest.raises(ValueError, match="Checksum mismatch"):
        verify_pack(path)


def test_artifact_tampering_blocks_decision_confirmation(client, app):
    v = experiment(client, app, reviewed(client, app))
    e = v["evidences"][0]
    with app.state.research.store.tx() as c:
        a = app.state.research.store.get(c, e["artifact_id"], "artifact")
    (app.state.research.settings.artifacts / a["path"]).write_text("{}")
    assert client.get("/api/artifacts/" + a["id"]).status_code == 422
    post(
        client,
        f"/steps/{v['steps'][0]['id']}/decisions",
        {
            "expected_revision": 1,
            "conclusion": "Attempt to approve altered evidence should fail",
            "verdict": "inconclusive",
            "agreement": "unresolved",
            "alternatives": ["Keep original artifact"],
            "reasons": ["Inspect integrity"],
            "dissent": [],
            "assumptions": ["Source hash is preserved"],
            "reopen_triggers": ["A changed artifact"],
            "evidence_ids": [e["id"]],
        },
        422,
    )


def test_stale_unrevealed_round_does_not_leak_into_export(client, app):
    v = mission(client)
    sid = v["steps"][0]["id"]
    mid = v["mission"]["id"]
    rnd = post(
        client, f"/steps/{sid}/rounds", {"expected_revision": 1, "mode": "fixture"}
    )
    app.state.executor.run_once()
    post(
        client,
        f"/steps/{sid}/concerns",
        {
            "expected_revision": 1,
            "text": "The physical-mechanism assumption needs another control.",
        },
    )
    pack = post(client, f"/missions/{mid}/exports", {})
    assert pack["files"] > 10
    with zipfile.ZipFile(
        app.state.research.settings.data / "exports" / pack["filename"]
    ) as z:
        assert not any(n.startswith("artifacts/") for n in z.namelist())
        public = json.loads(z.read("research.json"))
        assert public["rounds"][0]["status"] == "stale"
        assert "submissions" not in public["rounds"][0]


def test_backup_restore_excludes_credentials_and_locks_live(client, app, tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "backup", app.state.research.settings.root / "scripts/backup.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    v = experiment(client, app, reviewed(client, app))
    archive = tmp_path / "backup.zip"
    r = app.state.research
    with r.store.tx() as c:
        r.store.set_setting(
            c, "live_verification", {"test": "not carried into restored authorization"}
        )
    result = module.backup(archive, r.settings)
    assert result["credential_files_included"] is False
    with zipfile.ZipFile(archive) as z:
        assert "director-token" not in z.namelist() and ".env.local" not in z.namelist()
    restored = tmp_path / "restored"
    module.restore(archive, restored)
    with sqlite3.connect(restored / "zerowall.sqlite3") as c:
        assert (
            c.execute("SELECT COUNT(*) FROM records WHERE kind='evidence'").fetchone()[
                0
            ]
            == 1
        )
        assert (
            c.execute(
                "SELECT COUNT(*) FROM settings WHERE key='live_verification'"
            ).fetchone()[0]
            == 0
        )
    assert not (restored / "director-token").exists()


def test_altered_plan_is_refused_before_execution(client, app):
    v = reviewed(client, app)
    sid = v["steps"][0]["id"]
    e = post(
        client,
        f"/steps/{sid}/experiments",
        {
            "expected_revision": 1,
            "title": "An immutable bound plan",
            "hypothesis_ids": [v["hypotheses"][0]["id"]],
            "capability": "analysis.calculate_bound",
            "args": {
                "bytes_moved": 100,
                "bandwidth_gbps": 1,
                "assumptions": ["hypothetical"],
            },
            "control": "Fixed values",
            "treatment": "Calculate bound",
            "prediction": "A finite analytical lower bound",
            "kill_rule": "Reject impossible arithmetic",
        },
    )
    with app.state.research.store.tx() as c:
        stored = app.state.research.store.get(c, e["id"], "experiment")
        stored["args"]["bytes_moved"] = 500
        app.state.research.store.put(c, "experiment", stored)
    post(client, f"/experiments/{e['id']}/approve", {"expected_revision": 1}, 422)
