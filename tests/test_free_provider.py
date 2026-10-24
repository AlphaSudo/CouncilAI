import json

import httpx
import pytest

from zerowall.artifacts import Artifacts
from zerowall.contracts import Submission
from zerowall.db import DomainError, canonical
from zerowall.free_provider import BASE_URL, MODEL, OpenRouterFreeProvider, zero_priced


def setup_free(
    app, monkeypatch, *, pricing=None, response=None, status=200, timeout=False
):
    research = app.state.research
    research.settings.openrouter_api_key = "free-key-never-network"
    provider = OpenRouterFreeProvider(
        research.store, research.settings, research.artifacts
    )
    posts = []
    real_client = httpx.Client

    def handle(request):
        assert str(request.url).startswith(BASE_URL)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": MODEL,
                            "pricing": pricing or {"prompt": "0", "completion": "0"},
                        }
                    ]
                },
            )
        posts.append(json.loads(request.content))
        if timeout:
            raise httpx.ReadTimeout("never log sensitive provider diagnostics")
        return httpx.Response(
            status,
            json=response
            if response is not None
            else {
                "model": MODEL,
                "usage": {"cost": 0, "prompt_tokens": 20, "completion_tokens": 4},
                "choices": [{"message": {"content": '{"ok": true}'}}],
            },
        )

    monkeypatch.setattr(
        "zerowall.free_provider.httpx.Client",
        lambda **kwargs: real_client(**kwargs, transport=httpx.MockTransport(handle)),
    )
    return research, provider, posts


def test_free_call_has_zero_guard_no_fallback_and_does_not_unlock_nebius(
    app, monkeypatch
):
    r, provider, posts = setup_free(app, monkeypatch)
    text, call = provider.call("free-test", "Return JSON", 128)
    assert json.loads(text)["ok"]
    assert posts[0]["model"].endswith(":free")
    assert posts[0]["provider"] == {
        "max_price": {"prompt": 0, "completion": 0, "request": 0},
        "allow_fallbacks": False,
        "require_parameters": True,
    }
    assert "models" not in posts[0] and "plugins" not in posts[0]
    assert posts[0]["reasoning"] == {"enabled": False, "exclude": True}
    with r.store.tx() as c:
        assert r.budget.summary(c, provider="openrouter_free")["attempts"] == 1
        assert r.budget.summary(c)["attempts"] == 0
        assert r.budget.summary(c)["settled_usd"] == 0
        assert not r.store.setting(c, "live_verification", {})
        assert call["provider"] == "openrouter_free"
        with pytest.raises(DomainError):
            r.provider.choose(c)


@pytest.mark.parametrize(
    "pricing",
    [
        {"prompt": "0.00001", "completion": "0"},
        {"prompt": "0", "completion": "0", "request": "0.01"},
        {"prompt": "0", "completion": "0", "image": "NaN"},
        {"prompt": "0"},
    ],
)
def test_repriced_or_unknown_catalog_blocks_before_dispatch(app, monkeypatch, pricing):
    r, provider, posts = setup_free(app, monkeypatch, pricing=pricing)
    with pytest.raises(DomainError):
        provider.call("free-test", "Return JSON")
    assert posts == []
    with r.store.tx() as c:
        assert r.budget.summary(c)["attempts"] == 0


def test_paid_model_rejected_even_when_caller_requests_it(app, monkeypatch):
    _, provider, posts = setup_free(app, monkeypatch)
    with pytest.raises(DomainError):
        provider.call("free-test", "Return JSON", model=MODEL.removesuffix(":free"))
    assert posts == []
    assert not zero_priced(
        {"id": "openrouter/free", "pricing": {"prompt": 0, "completion": 0}}
    )


def test_council_requests_pass_the_typed_schema_to_structured_output(app, monkeypatch):
    _, provider, posts = setup_free(app, monkeypatch)
    provider.call(
        "free-test", json.dumps({"output_schema": Submission.model_json_schema()})
    )
    response_format = posts[0]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"]
    assert "prediction" in response_format["json_schema"]["schema"]["required"]


@pytest.mark.parametrize(
    "response",
    [
        {"model": MODEL, "usage": {"cost": 0.01}},
        {"model": MODEL, "usage": {}},
        {"model": "different-model", "usage": {"cost": 0}},
    ],
)
def test_unverified_cost_or_identity_locks_more_calls(app, monkeypatch, response):
    r, provider, posts = setup_free(app, monkeypatch, response=response)
    with pytest.raises(DomainError):
        provider.call("free-test", "Return JSON")
    with pytest.raises(DomainError):
        provider.call("free-test", "Return JSON")
    assert len(posts) == 1
    with r.store.tx() as c:
        assert r.store.setting(c, "openrouter_free_locked")
        assert not r.store.setting(c, "live_verification", {})
        if response.get("usage", {}).get("cost") == 0.01:
            assert (
                r.budget.summary(c, provider="openrouter_free")["settled_usd"] == 0.01
            )


def test_quota_errors_stop_without_hidden_retries(app, monkeypatch):
    _, provider, posts = setup_free(
        app, monkeypatch, status=429, response={"error": {"message": "Limited"}}
    )
    with pytest.raises(DomainError):
        provider.call("free-test", "Return JSON")
    with pytest.raises(DomainError):
        provider.call("free-test", "Return JSON")
    assert len(posts) == 1


def test_timeout_preserves_attempt_and_twelve_attempt_cap_is_durable(app, monkeypatch):
    r, provider, posts = setup_free(app, monkeypatch, timeout=True)
    with pytest.raises(DomainError):
        provider.call("free-test", "Return JSON")
    assert len(posts) == 1
    with r.store.tx() as c:
        assert c.execute("SELECT state FROM reservations").fetchone()[0] == "unknown"
        for i in range(11):
            c.execute(
                "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
                (
                    str(i),
                    "free-test",
                    str(i),
                    0,
                    None,
                    "unknown",
                    canonical({"provider": "openrouter_free"}),
                ),
            )
    with pytest.raises(DomainError):
        provider.call("free-test", "Return JSON")
    assert len(posts) == 1


def test_all_provider_credentials_are_redacted(tmp_path):
    artifacts = Artifacts(tmp_path, ["first-secret", "second-secret"])
    redacted = artifacts.redact(
        {"text": "first-secret plus second-secret", "authorization": "anything"}
    )
    assert redacted == {
        "text": "[REDACTED] plus [REDACTED]",
        "authorization": "[REDACTED]",
    }


def test_truncation_reports_the_token_limit_instead_of_a_json_error(app, monkeypatch):
    _, provider, posts = setup_free(
        app,
        monkeypatch,
        response={
            "model": MODEL,
            "usage": {"cost": 0},
            "choices": [{"finish_reason": "length", "message": {"content": '{"cut":'}}],
        },
    )
    with pytest.raises(DomainError) as error:
        provider.call("free-test", "Return JSON")
    assert "output token limit" in error.value.message
    assert len(posts) == 1


def test_cancellation_after_reservation_releases_an_unsent_attempt(app, monkeypatch):
    r, provider, posts = setup_free(app, monkeypatch)
    checks = iter([False, False, True])
    with pytest.raises(DomainError):
        provider.call("free-test", "Return JSON", cancelled=lambda: next(checks))
    assert posts == []
    with r.store.tx() as c:
        assert c.execute("SELECT state FROM reservations").fetchone()[0] == "released"


def test_whitespace_keep_alives_cannot_extend_generation_indefinitely(monkeypatch):
    ticks = [0]

    class KeepAlive(httpx.SyncByteStream):
        def __iter__(self):
            yield b" "
            ticks[0] = 121
            yield b" "
            raise AssertionError("The response deadline did not stop keep-alives")

    monkeypatch.setattr("zerowall.free_provider.time.monotonic", lambda: ticks[0])
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=KeepAlive())
        )
    ) as client:
        with pytest.raises(httpx.ReadTimeout):
            OpenRouterFreeProvider.bounded_post(
                client, BASE_URL + "/chat/completions", json={"model": MODEL}
            )
