import gzip
import json
import zlib

import httpx
import pytest
from test_budget import configured
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing

from zerowall.db import DomainError, digest
from zerowall.stream_receipt_restore import restore_completed_opening
from zerowall.token_factory_generation import profile
from zerowall.token_factory_stream import complete


@pytest.mark.parametrize(
    "encoding,encode", [("gzip", gzip.compress), ("deflate", zlib.compress)]
)
def test_encoded_sse_is_decoded_once_and_reconstructed_json_has_fresh_headers(
    app, monkeypatch, encoding, encode
):
    r, mid, model = configured(app, 0.1)
    original, requests = httpx.Client, []

    def handler(request):
        requests.append(json.loads(request.content))
        body = encode(sse(model).encode())
        return httpx.Response(
            200,
            headers={
                "content-type": "text/event-stream",
                "content-encoding": encoding,
                "content-length": str(len(body)),
                "x-request-id": "provider-request",
            },
            content=body,
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    generation = profile(
        r.settings, {"phase": "opening", "participant": {"model": model}}
    )
    text, call = r.provider.call(
        mid,
        "A raw question.",
        generation["requested_output_tokens"],
        model=model,
        generation=generation,
    )
    assert text == "A complete public answer."
    assert call["state"] == "completed" and call["settlement"] == "settled"
    assert len(requests) == 1
    with r.store.tx() as c:
        assert r.budget.summary(c)["unknown_usd"] == 0
        assert r.budget.summary(c)["settled_usd"] == 0.00016


def decoding_failure(client, app, monkeypatch, *, partial=False):
    r = setup_testing(app)
    original, requests = httpx.Client, []

    class PartialStream(httpx.SyncByteStream):
        def __iter__(self):
            yield (
                "data: "
                + json.dumps(
                    {
                        "model": r.settings.models[0],
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": "An incomplete public draft."},
                            }
                        ],
                    }
                )
                + "\n\n"
            ).encode()
            raise httpx.DecodingError("Truncated encoded transport")

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if partial:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=PartialStream(),
            )
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, text=sse(body["model"])
        )

    def former_wrapper_bug(*args, **kwargs):
        result = complete(*args, **kwargs)
        if not partial:
            # The former wrapper failed only after the full final usage was received.
            return httpx.Response(
                result.status_code,
                headers={"content-encoding": "gzip"},
                json=result.json(),
            )
        return result

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr("zerowall.token_factory_stream.complete", former_wrapper_bug)
    response = client.post(
        "/api/chats",
        headers={"Idempotency-Key": "restore-saved-completion"},
        json={
            "provider": "nebius_token_factory",
            "review_protocol": "reviewed_v3",
            "prompt": "Give a useful independent engineering answer.",
            "models": r.settings.models,
            "budget_usd": 0.25,
        },
    )
    assert response.is_success, response.text
    assert app.state.executor.run_once()
    view = client.get("/api/chats/" + response.json()["chat"]["id"]).json()
    with r.store.tx() as c:
        call = r.store.list(c, "call", view["chat"]["mission_id"])[0]
        assert call["state"] == "unknown" and call["error"] == "DecodingError"
    return r, view, call, requests


def test_completed_saved_receipt_restores_answer_and_actual_estimate_without_network(
    client, app, monkeypatch
):
    r, view, call, requests = decoding_failure(client, app, monkeypatch)
    original_hash = digest(call)
    result = restore_completed_opening(r, call["id"])
    latest = client.get("/api/chats/" + view["chat"]["id"]).json()
    assert latest["chat"]["status"] == "paused" and latest["chat"].get("error") is None
    assert latest["messages"][-1]["content"] == "A complete public answer."
    assert latest["messages"][-1]["call_id"] == call["id"]
    assert latest["next_turn"]["participant"]["model"] == r.settings.models[1]
    assert (
        latest["budget"]["unknown_usd"] == 0
        and latest["budget"]["settled_usd"] == 0.000084
    )
    # The context window can limit a reservation before the whole conversation
    # allowance is committed. Release exactly the original hold less settlement.
    assert result["released_unknown_hold_usd"] == pytest.approx(
        view["budget"]["unknown_usd"] - latest["budget"]["settled_usd"]
    )
    assert result["released_unknown_hold_usd"] > 0
    assert result["new_inference_calls"] == 0
    assert len(requests) == 1 and not app.state.executor.run_once()
    with r.store.tx() as c:
        audit = r.store.list(c, "completion_restoration", call["mission_id"])[0]
        assert digest(audit["original_call"]) == original_hash
        assert audit["original_reservation"]["state"] == "unknown"
        assert r.store.get(c, call["id"], "call")["original_error"] == "DecodingError"
    assert restore_completed_opening(r, call["id"]) == result
    assert len(client.get("/api/chats/" + view["chat"]["id"]).json()["messages"]) == 2


def test_partial_receipt_cannot_release_money_or_be_published_as_complete(
    client, app, monkeypatch
):
    r, view, call, requests = decoding_failure(client, app, monkeypatch, partial=True)
    with pytest.raises(DomainError, match="no verified complete response"):
        restore_completed_opening(r, call["id"])
    latest = client.get("/api/chats/" + view["chat"]["id"]).json()
    assert latest["budget"]["unknown_usd"] == view["budget"]["unknown_usd"]
    assert len(latest["messages"]) == 1 and len(requests) == 1


def test_changed_context_prevents_local_receipt_publication_and_settlement(
    client, app, monkeypatch
):
    r, view, call, requests = decoding_failure(client, app, monkeypatch)
    r.library.ingest(view["chat"], b"A new material constraint.", title="Changed input")
    with pytest.raises(DomainError, match="unchanged council turn"):
        restore_completed_opening(r, call["id"])
    latest = client.get("/api/chats/" + view["chat"]["id"]).json()
    assert latest["budget"]["unknown_usd"] == view["budget"]["unknown_usd"]
    assert len(latest["messages"]) == 1 and len(requests) == 1
