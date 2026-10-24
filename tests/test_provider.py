import json
import httpx
import pytest
from zerowall.db import DomainError
from test_budget import configured


class FakeClient:
    handler = None
    calls = []

    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.handler(url, kwargs)


def fake(monkeypatch, handler):
    FakeClient.handler = staticmethod(handler)
    FakeClient.calls = []
    monkeypatch.setattr("zerowall.provider.httpx.Client", FakeClient)


def test_single_attempt_timeout_retains_maximum_and_raw_call(app, monkeypatch):
    r, mid, model = configured(app, 0.1)

    def timeout(url, kwargs):
        raise httpx.ReadTimeout("sensitive diagnostic must not be emitted")

    fake(monkeypatch, timeout)
    with pytest.raises(DomainError):
        r.provider.call(mid, "A bounded prompt", 32)
    assert len(FakeClient.calls) == 1
    with r.store.tx() as c:
        assert r.budget.summary(c)["unknown_usd"] > 0
        calls = r.store.list(c, "call", mid)
        assert calls[0]["state"] == "unknown"
        assert "sensitive" not in json.dumps(calls)


def test_success_records_usage_and_no_auth_header_artifact(app, monkeypatch):
    r, mid, model = configured(app, 0.1)
    fake(
        monkeypatch,
        lambda url, kw: httpx.Response(
            200,
            json={
                "model": model,
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            },
        ),
    )
    content, call = r.provider.call(mid, "A bounded prompt", 32)
    assert json.loads(content)["ok"]
    assert FakeClient.calls[0][1]["json"]["max_completion_tokens"] == 32
    assert call["ttft_ms"] is None
    with r.store.tx() as c:
        artifact = r.artifacts.read(r.store.get(c, call["artifact_id"], "artifact"))
        assert "test-key-never-network" not in json.dumps(artifact)
        assert "Authorization" not in json.dumps(artifact)
        assert r.budget.summary(c)["settled_usd"] == 0.000014


def test_http_failure_missing_usage_is_not_free_and_not_retried(app, monkeypatch):
    r, mid, model = configured(app, 0.1)
    fake(
        monkeypatch, lambda url, kw: httpx.Response(429, json={"error": "rate limited"})
    )
    with pytest.raises(DomainError):
        r.provider.call(mid, "A bounded prompt", 32)
    assert len(FakeClient.calls) == 1
    with r.store.tx() as c:
        assert r.budget.summary(c)["unknown_usd"] > 0


def test_truncated_response_retains_charge_and_explains_token_limit(app, monkeypatch):
    r, mid, model = configured(app, 0.1)
    fake(
        monkeypatch,
        lambda url, kw: httpx.Response(
            200,
            json={
                "model": model,
                "usage": {"prompt_tokens": 10, "completion_tokens": 32},
                "choices": [
                    {"finish_reason": "length", "message": {"content": '{"partial":'}}
                ],
            },
        ),
    )
    with pytest.raises(DomainError) as error:
        r.provider.call(mid, "A bounded prompt", 32)
    assert "output token limit" in error.value.message
    assert len(FakeClient.calls) == 1
    with r.store.tx() as c:
        assert r.budget.summary(c)["settled_usd"] == 0.000042


def test_full_schedule_hold_transfers_without_double_counting(app, monkeypatch):
    r, mid, model = configured(app, 0.1)
    with r.store.tx() as c:
        hold = r.provider.schedule_hold(
            c, mid, [(model, "first", 32), (model, "second", 32)], "schedule-1"
        )
        before = r.budget.summary(c)["global_committed_usd"]
    fake(
        monkeypatch,
        lambda url, kw: httpx.Response(
            200,
            json={
                "model": model,
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            },
        ),
    )
    r.provider.call(mid, "first", 32, hold_id=hold)
    with r.store.tx() as c:
        after = r.budget.summary(c)["global_committed_usd"]
        assert after < before
        assert r.budget.summary(c)["reserved_usd"] > 0
        r.budget.release_hold(c, hold)
        assert r.budget.summary(c)["global_committed_usd"] == 0.000014


def test_wrong_model_response_cannot_pass(app, monkeypatch):
    r, mid, model = configured(app, 0.1)
    fake(
        monkeypatch,
        lambda url, kw: httpx.Response(
            200,
            json={
                "model": "wrong/model",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            },
        ),
    )
    with pytest.raises(DomainError):
        r.provider.call(mid, "first", 32)


def test_rate_limit_backoff_blocks_an_immediate_explicit_retry(app, monkeypatch):
    r, mid, model = configured(app, 0.1)
    fake(
        monkeypatch,
        lambda url, kw: httpx.Response(
            429, json={"error": "rate limited"}, headers={"Retry-After": "30"}
        ),
    )
    with pytest.raises(DomainError):
        r.provider.call(mid, "first", 32)
    with pytest.raises(DomainError, match="backoff"):
        r.provider.call(mid, "second", 32)
    assert len(FakeClient.calls) == 1
