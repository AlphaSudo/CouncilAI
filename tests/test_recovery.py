import pytest
from zerowall.db import DomainError
from zerowall.process_lock import ProcessLock
from test_workflow import mission, post, reviewed, experiment


def test_partial_commit_continues_without_regenerating_valid_seats(
    client, app, monkeypatch
):
    v = mission(client)
    s = v["steps"][0]
    rnd = post(
        client, f"/steps/{s['id']}/rounds", {"expected_revision": 1, "mode": "fixture"}
    )
    from zerowall import executor as module

    original = module.submission

    def fail_last(seat, sources):
        if seat == "algorithms":
            raise ValueError("Injected failure after three durable commits")
        return original(seat, sources)

    monkeypatch.setattr(module, "submission", fail_last)
    app.state.executor.run_once()
    with app.state.research.store.tx() as c:
        before = app.state.research.store.list(c, "submission", v["mission"]["id"])
        assert len(before) == 3
    monkeypatch.setattr(module, "submission", original)
    post(client, f"/rounds/{rnd['id']}/continue", {"expected_revision": 1})
    app.state.executor.run_once()
    result = post(client, f"/rounds/{rnd['id']}/reveal", {"expected_revision": 1})
    assert len(result["submissions"]) == 4
    assert {s["id"] for s in before} <= {s["id"] for s in result["submissions"]}


def test_executor_ownership_is_exclusive(tmp_path):
    a = ProcessLock(tmp_path / "lock")
    b = ProcessLock(tmp_path / "lock")
    a.acquire()
    try:
        with pytest.raises(DomainError):
            b.acquire()
    finally:
        a.release()
    b.acquire()
    b.release()


def test_seed_refuses_an_active_executor(app, tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "seed_demo", app.state.research.settings.root / "scripts/seed_demo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lock = ProcessLock(tmp_path / "executor.lock")
    lock.acquire()
    try:
        with pytest.raises(DomainError):
            module.seed(tmp_path)
    finally:
        lock.release()


def test_process_restart_after_third_commit_requires_explicit_continuation(
    client, app, monkeypatch
):
    v = mission(client)
    s = v["steps"][0]
    rnd = post(
        client, f"/steps/{s['id']}/rounds", {"expected_revision": 1, "mode": "fixture"}
    )
    from zerowall import executor as module

    original = module.submission

    class ProcessCrash(BaseException):
        pass

    def crash(seat, sources):
        if seat == "algorithms":
            raise ProcessCrash()
        return original(seat, sources)

    monkeypatch.setattr(module, "submission", crash)
    with pytest.raises(ProcessCrash):
        app.state.executor.run_once()
    with app.state.research.store.tx() as c:
        before = app.state.research.store.list(c, "submission", v["mission"]["id"])
    assert len(before) == 3
    app.state.research.store.recover()
    assert not app.state.executor.run_once()
    monkeypatch.setattr(module, "submission", original)
    post(client, f"/rounds/{rnd['id']}/continue", {"expected_revision": 1})
    app.state.executor.run_once()
    result = post(client, f"/rounds/{rnd['id']}/reveal", {"expected_revision": 1})
    assert len(result["submissions"]) == 4
    assert {s["id"] for s in before} <= {s["id"] for s in result["submissions"]}


def test_cancel_before_dispatch_leaves_no_run(client, app):
    v = reviewed(client, app)
    s = v["steps"][0]
    e = post(
        client,
        f"/steps/{s['id']}/experiments",
        {
            "expected_revision": 1,
            "title": "A cancellable calculation",
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
    e = post(client, f"/experiments/{e['id']}/approve", {"expected_revision": 1})
    post(client, f"/experiments/{e['id']}/cancel", {"expected_revision": e["revision"]})
    assert not app.state.executor.run_once()
    assert client.get(f"/api/experiments/{e['id']}/runs").json() == []
