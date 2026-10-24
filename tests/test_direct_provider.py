import json
import httpx
import pytest
from zerowall.db import DomainError
from zerowall.free_errors import FreeProviderError
from test_council_chat import drain
from test_workflow import post


def setup_direct(app):
    r = app.state.research
    r.settings.direct_keys = {
        e["provider"]: "synthetic-direct-key-" + e["provider"]
        for e in r.settings.direct_policy["models"]
    }
    r.artifacts.secrets.extend(r.settings.direct_keys.values())
    r.settings.direct_free_confirmed = True
    return r


def transport(app, monkeypatch, status=200, *, mutate=None, cost=None):
    r = setup_direct(app)
    seen = []
    original = httpx.Client

    def handler(request):
        body = json.loads(request.content)
        assert request.url.host in (
            "api.z.ai",
            "generativelanguage.googleapis.com",
            "integrate.api.nvidia.com",
            "api.groq.com",
        )
        assert "tools" not in body
        seen.append((request, body))
        if status != 200:
            return httpx.Response(
                status,
                headers={"Retry-After": "2"},
                json={
                    "error": {"code": status, "message": "Synthetic transport failure"}
                },
            )
        if request.url.host == "generativelanguage.googleapis.com":
            model = request.url.path.split("/models/")[1].split(":")[0]
            out = {
                "modelVersion": model,
                "candidates": [
                    {
                        "content": {"parts": [{"text": "A complete public answer."}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 10},
            }
        else:
            out = {
                "model": body["model"],
                "choices": [
                    {
                        "message": {"content": "A complete public answer."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            }
            if cost is not None:
                out["usage"]["cost"] = cost
        if mutate:
            mutate(out)
        return httpx.Response(200, json=out)

    monkeypatch.setattr(
        "zerowall.direct_provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    return r, seen


def direct_chat(client, r, mode="discussion"):
    return post(
        client,
        "/chats",
        {
            "prompt": "Compare two generic software designs.",
            "provider": "direct_council",
            "models": list(r.direct_provider.entries()),
            "mode": mode,
            "review_protocol": "reviewed_v1",
            "max_rounds": 1,
        },
    )


def test_four_distinct_direct_models_complete_discussion_without_openrouter(
    client, app, monkeypatch
):
    r, seen = transport(app, monkeypatch)
    v = direct_chat(client, r)
    drain(app)
    v = client.get("/api/chats/" + v["chat"]["id"]).json()
    assert v["chat"]["status"] == "completed", v["chat"].get("error")
    assert len(seen) == 9
    assert {m["provider"] for m in v["messages"] if m["phase"] == "opening"} == {
        "zai",
        "gemini",
        "nvidia_nim",
        "groq",
    }
    assert v["budget"]["attempts"] == 9
    with r.store.tx() as c:
        calls = r.store.list(c, "call", v["chat"]["mission_id"])
    assert all(
        x["cost_usd"] is None and x["cost_status"] == "not_reported" for x in calls
    )
    assert all("::" not in x["model"] for x in calls)
    with r.store.tx() as c:
        artifacts = r.store.list(c, "artifact", v["chat"]["mission_id"])
    assert artifacts
    assert all(
        "synthetic-direct-key" not in json.dumps(r.artifacts.read(a)) for a in artifacts
    )


@pytest.mark.parametrize(
    "status,retryable",
    [
        (302, False),
        (401, False),
        (402, False),
        (403, False),
        (404, False),
        (429, True),
        (500, True),
        (502, True),
        (503, True),
    ],
)
def test_direct_errors_are_classified_and_counted(
    client, app, monkeypatch, status, retryable
):
    r, seen = transport(app, monkeypatch, status)
    v = direct_chat(client, r)
    with pytest.raises(FreeProviderError) as exc:
        r.direct_provider.call(
            v["chat"]["mission_id"],
            "Answer briefly",
            model=list(r.direct_provider.entries())[0],
        )
    assert exc.value.retryable == retryable
    assert len(seen) == 1
    with r.store.tx() as c:
        assert (
            r.direct_provider.capacity(c, v["chat"]["mission_id"])["remaining_calls"]
            == 19
        )


def test_reported_cost_locks_further_dispatch_even_on_error(client, app, monkeypatch):
    r, seen = transport(app, monkeypatch, cost=0.01)
    v = direct_chat(client, r)
    model = list(r.direct_provider.entries())[0]
    with pytest.raises(FreeProviderError, match="nonzero"):
        r.direct_provider.call(v["chat"]["mission_id"], "Answer briefly", model=model)
    with pytest.raises(DomainError, match="locked"):
        r.direct_provider.call(v["chat"]["mission_id"], "Answer briefly", model=model)
    assert len(seen) == 1
    assert (
        client.get("/api/chats/" + v["chat"]["id"]).json()["budget"]["settled_usd"]
        == 0.01
    )


def test_model_identity_and_truncation_are_not_admitted(client, app, monkeypatch):
    r, seen = transport(
        app, monkeypatch, mutate=lambda out: out.update(model="different-model")
    )
    v = direct_chat(client, r)
    with pytest.raises(FreeProviderError, match="different model"):
        r.direct_provider.call(
            v["chat"]["mission_id"],
            "Answer briefly",
            model=list(r.direct_provider.entries())[0],
        )
    with r.store.tx() as c:
        assert r.store.list(c, "call", v["chat"]["mission_id"])[0]["state"] == "failed"


def test_four_model_review_preflight_has_twelve_calls_and_shared_reserve(
    client, app, monkeypatch
):
    r = setup_direct(app)
    v = direct_chat(client, r, "reviewed")
    assert v["remaining_planned_calls"] == 12
    assert v["review"]["contract"]["planned_calls"] == 12
    assert v["review"]["contract"]["retry_allowance"] == 3
    r.settings.direct_policy["daily_attempt_cap"] = 14
    import uuid

    response = client.post(
        "/api/chats",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "prompt": "A new reviewed question",
            "provider": "direct_council",
            "models": list(r.direct_provider.entries()),
            "mode": "reviewed",
            "max_rounds": 1,
        },
    )
    assert response.status_code == 429


def test_free_confirmation_and_key_presence_block_network(client, app, monkeypatch):
    r, seen = transport(app, monkeypatch)
    r.settings.direct_free_confirmed = False
    import uuid

    response = client.post(
        "/api/chats",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "prompt": "No dispatch before free access confirmation",
            "provider": "direct_council",
            "models": list(r.direct_provider.entries()),
        },
    )
    assert response.status_code == 412
    assert not seen


def test_http_200_error_payload_is_not_a_successful_answer(client, app, monkeypatch):
    r, seen = transport(
        app,
        monkeypatch,
        mutate=lambda out: out.update(
            error={"code": 429, "message": "Synthetic rate limit inside HTTP 200"}
        ),
    )
    v = direct_chat(client, r)
    with pytest.raises(FreeProviderError) as error:
        r.direct_provider.call(
            v["chat"]["mission_id"],
            "A public answer",
            model=list(r.direct_provider.entries())[0],
        )
    assert error.value.kind == "platform_rate_limit"
    assert error.value.retryable
    with r.store.tx() as c:
        assert r.store.list(c, "call", v["chat"]["mission_id"])[0]["state"] == "failed"


def test_truncated_direct_output_is_retained_but_not_admitted(client, app, monkeypatch):
    def truncate(out):
        out["choices"][0]["finish_reason"] = "length"

    r, seen = transport(app, monkeypatch, mutate=truncate)
    v = direct_chat(client, r)
    with pytest.raises(FreeProviderError) as error:
        r.direct_provider.call(
            v["chat"]["mission_id"],
            "A public answer",
            model=list(r.direct_provider.entries())[0],
        )
    assert error.value.kind == "output_incomplete"
    with r.store.tx() as c:
        call = r.store.list(c, "call", v["chat"]["mission_id"])[0]
        assert call["artifact_id"]
        assert call["state"] == "failed"


def test_ambiguous_direct_transport_keeps_its_counted_attempt(client, app, monkeypatch):
    r = setup_direct(app)
    original = httpx.Client

    def lost(request):
        raise httpx.ReadTimeout("Synthetic connection loss", request=request)

    monkeypatch.setattr(
        "zerowall.direct_provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(lost)),
    )
    v = direct_chat(client, r)
    with pytest.raises(FreeProviderError) as error:
        r.direct_provider.call(
            v["chat"]["mission_id"],
            "A public answer",
            model=list(r.direct_provider.entries())[0],
        )
    assert error.value.kind == "network_ambiguous"
    with r.store.tx() as c:
        assert r.store.list(c, "call", v["chat"]["mission_id"])[0]["state"] == "unknown"
        assert (
            r.direct_provider.capacity(c, v["chat"]["mission_id"])["remaining_calls"]
            == 19
        )
