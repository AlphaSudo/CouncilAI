import json

import httpx
import pytest
from test_budget import configured
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing

from zerowall.db import DomainError
from zerowall.response_timing import summarize
from zerowall.token_factory_generation import profile
from zerowall.usage import normalize


@pytest.mark.parametrize(
    "phase,recovery", [("opening", False), ("scrutiny", False), ("opening", True)]
)
def test_lightning_keeps_thinking_enabled_and_4k_instruction_in_every_phase(
    app, monkeypatch, phase, recovery
):
    r, mid, _ = configured(app, 1)
    setup_testing(app)
    model = r.settings.models[2]
    generation = profile(
        r.settings, {"phase": phase, "participant": {"model": model}}, recovery=recovery
    )
    original, requests, timeouts = httpx.Client, [], []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        timeouts.append(request.extensions["timeout"])
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, text=sse(model)
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    text, call = r.provider.call(
        mid,
        "Return the requested engineering answer.",
        generation["requested_output_tokens"],
        model=model,
        generation=generation,
    )
    assert text == "A complete public answer."
    assert requests[0]["chat_template_kwargs"] == {"enable_thinking": True}
    assert "at most 4,000 reasoning tokens" in requests[0]["messages"][0]["content"]
    assert requests[0]["max_completion_tokens"] > 4000
    assert call["generation"]["reasoning"] == "enabled"
    assert (
        call["generation"]["reasoning_budget_enforcement"] == "system_instruction_only"
    )
    assert timeouts[0]["read"] == 90 and timeouts[0]["connect"] == 10
    assert timeouts[0]["write"] == 90 and timeouts[0]["pool"] == 90
    assert call["read_idle_timeout_seconds"] == 90
    if phase == "opening" and not recovery:
        # The smaller envelope was authorized for two diagnostics only.
        assert generation["requested_output_tokens"] == generation["context_tokens"]
        assert requests[0]["max_completion_tokens"] > 16384
    assert len(requests) == 1
    for other in [r.settings.models[0], r.settings.models[1], r.settings.models[3]]:
        assert (
            profile(r.settings, {"phase": "opening", "participant": {"model": other}})[
                "read_idle_timeout_seconds"
            ]
            == 90
        )


@pytest.mark.parametrize("started", [False, True])
@pytest.mark.parametrize("read_idle", [30, 90])
def test_lightning_timeout_is_classified_saves_receipt_and_never_retries_or_frees_unknown_charge(
    app, monkeypatch, started, read_idle
):
    r, mid, _ = configured(app, 1)
    setup_testing(app)
    model = r.settings.models[2]
    generation = profile(
        r.settings, {"phase": "opening", "participant": {"model": model}}
    )
    generation["read_idle_timeout_seconds"] = read_idle
    original, requests = httpx.Client, []

    class Interrupted(httpx.SyncByteStream):
        def __iter__(self):
            yield (
                "data: "
                + json.dumps(
                    {
                        "model": model,
                        "choices": [
                            {"index": 0, "delta": {"content": "A saved public draft."}}
                        ],
                    }
                )
                + "\n\n"
            ).encode()
            raise httpx.ReadTimeout("PRIVATE_TRANSPORT_DIAGNOSTIC")

    def handler(request):
        requests.append(json.loads(request.content))
        assert request.extensions["timeout"]["read"] == read_idle
        if not started:
            raise httpx.ReadTimeout("PRIVATE_TRANSPORT_DIAGNOSTIC")
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=Interrupted()
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(DomainError) as caught:
        r.provider.call(
            mid,
            "A bounded engineering comparison.",
            generation["requested_output_tokens"],
            model=model,
            generation=generation,
        )
    assert f"{read_idle}-second read timeout" in caught.value.message
    assert (
        "response stalled" if started else "sent no HTTP response"
    ) in caught.value.message
    assert len(requests) == 1
    with r.store.tx() as c:
        call = r.store.list(c, "call", mid)[0]
        assert call["state"] == "unknown"
        assert call.get("usage") is None
        assert call["timeout_details"] == {
            "stage": "response_body" if started else "response_headers",
            "read_idle_seconds": read_idle,
            "response_started": started,
        }
        artifact = r.artifacts.read(r.store.get(c, call["artifact_id"], "artifact"))
        assert artifact["request"] == requests[0]
        assert (
            artifact["transport_error"] == "ReadTimeout"
            and artifact["transport_incomplete"]
        )
        assert "PRIVATE_TRANSPORT_DIAGNOSTIC" not in json.dumps([call, artifact])
        assert "test-key-never-network" not in json.dumps(artifact)
        if started:
            assert (
                artifact["response"]["choices"][0]["message"]["content"]
                == "A saved public draft."
            )
        else:
            assert "response" not in artifact
        assert r.budget.summary(c)["unknown_usd"] > 0
        assert r.budget.summary(c)["settled_usd"] == 0


def test_old_no_header_timeout_gets_read_only_diagnostic_without_changing_its_limits():
    original = {
        "error": "ReadTimeout",
        "latency_ms": 90180.4852,
        "stream_progress": {"phase": "waiting_for_provider", "events": 0},
    }
    timing = summarize(original, normalize("nebius_token_factory", None))
    assert timing["interruption_reason"] == "read_timeout_before_headers"
    assert timing["elapsed_seconds"] > 90
    assert timing["read_idle_timeout_seconds"] is None
    assert "interruption_reason" not in original


def test_saved_failure_receipt_retains_private_round_scope(app, monkeypatch):
    r, mid, model = configured(app, 0.1)
    original = httpx.Client

    def handler(request):
        raise httpx.ReadTimeout("Private failure diagnostic")

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(DomainError):
        r.provider.call(
            mid,
            "Private round submission prompt.",
            32,
            model=model,
            purpose="round:private_round:submit",
        )
    with r.store.tx() as c:
        call = r.store.list(c, "call", mid)[0]
        artifact = r.store.get(c, call["artifact_id"], "artifact")
        assert artifact["private_round_id"] == "private_round"
        assert "Private failure diagnostic" not in json.dumps(
            r.artifacts.read(artifact)
        )
