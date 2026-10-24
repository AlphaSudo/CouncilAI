import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
from test_council_chat import drain

from zerowall.db import DomainError
from zerowall.token_factory_testing import authorize


def setup_testing(app, *, include_beam=False):
    r = app.state.research
    # Most historical regression fixtures use the captured October 21 catalog.
    # Beam integration tests explicitly use the new five-entry catalog instead.
    if not include_beam:
        r.settings.models = ["nvidia/Nemotron-3.5-Super-VL", "zai-org/GLM-5.3-Flash", "nvidia/Nemotron-3_5-Lightning", "deepseek-ai/DeepSeek-V4-Flash-0731"]
        r.settings.policy = deepcopy(r.settings.policy)
        r.settings.policy["council_default_models"] = [r.settings.models[i] for i in (0, 1, 3)]
        r.settings.policy["retired_council_models"] = []
    with r.store.tx() as c:
        r.store.set_setting(
            c,
            "token_factory_spending_authority",
            {
                "reported_existing_credit_usd": 25,
                "authorized_cap_usd": 24,
                "additional_payment_authority_usd": 0,
                "origin": "test_user",
            },
        )
    catalogue = json.loads(
        Path("docs/validation/reflection-beam-catalog.json" if include_beam else "docs/validation/token-factory-model-catalog-2026-10-21.json").read_text(
            encoding="utf-8"
        )
    )
    authorize(r, catalogue, origin="offline test user authorization")
    return r


def test_credit_testing_authority_does_not_claim_card_settings_and_requires_exact_link(
    app,
):
    r = setup_testing(app)
    with r.store.tx() as c:
        v = r.budget.verification(c, r.settings.models[0])
        assert v["automatic_payments_disabled"] is None
        assert v["account_payment_settings_verified"] is False
        assert r.budget.summary(c)["operational_cap_usd"] == 24
        v["authority_id"] = "unrelated"
        r.store.set_setting(c, "live_verification", v)
        with pytest.raises(DomainError):
            r.budget.verification(c, r.settings.models[0])


def test_full_four_model_token_factory_review_uses_sources_tools_prices_and_same_chat_followup(
    client, app, monkeypatch
):
    r = setup_testing(app)
    r.settings.tavily_api_key = "test-search-only"
    monkeypatch.setattr(
        r.tools.provider,
        "allowance",
        lambda: {"plan": "Researcher", "used": 0, "limit": 1000},
    )
    monkeypatch.setattr(
        r.tools.provider,
        "search",
        lambda **kw: {"results": [], "provider": "fixture", "query": kw["query"]},
    )
    original, physical, action_done = httpx.Client, [], []

    def handler(request):
        body = json.loads(request.content)
        with r.store.tx() as c:
            chat = json.loads(
                c.execute(
                    "SELECT body FROM records WHERE kind='chat' ORDER BY rowid DESC LIMIT 1"
                ).fetchone()[0]
            )
            messages = r.chat.messages(c, chat)
            turn = r.chat.next_turn(chat, messages, c)
            if turn["phase"] == "opening":
                demo_turn = deepcopy(turn)
                demo_turn["participant"]["model"] = [
                    "demo/analyst",
                    "demo/critic",
                    "demo/builder",
                ][len(physical) % 3]
                text = r.chat.demo_answer(chat, messages, demo_turn)
            else:
                text = r.chat.review.demo(c, chat, messages, turn)
        if turn["phase"] == "extraction" and not action_done:
            text = json.dumps(
                {
                    "research_actions": [
                        {"name": "library_search", "arguments": {"query": "boundary"}}
                    ]
                }
            )
            action_done.append(True)
        physical.append((turn["phase"], body))
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [{"finish_reason": "stop", "message": {"content": text}}],
                "usage": {
                    "prompt_tokens": 100,
                    "prompt_tokens_details": {"cached_tokens": 20},
                    "completion_tokens": 20,
                    "completion_tokens_details": {"reasoning_tokens": 0},
                },
            },
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    response = client.post(
        "/api/chats",
        headers={"Idempotency-Key": "tf-full"},
        json={
            "prompt": "Compare generic engineering approaches with their boundary conditions.",
            "provider": "nebius_token_factory",
            "models": r.settings.models,
            "budget_usd": 1,
            "search_web": True,
            "search_query": "Public engineering boundary evidence",
            "collective_research": False,
        },
    )
    assert response.is_success, response.text
    initial = response.json()
    cid = initial["chat"]["id"]
    assert initial["lead"]["model"] == r.settings.models[0]
    drain(app)
    view = client.get("/api/chats/" + cid).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert view["resource_policy"]["limits"]["output_tokens"] == 20 * 262144
    glm_requests = [
        body for _, body in physical if body["model"] == "zai-org/GLM-5.3-Flash"
    ]
    assert glm_requests
    assert glm_requests[0]["max_completion_tokens"] > 12000
    assert glm_requests[0]["reasoning_effort"] == "low"
    assert glm_requests[0]["chat_template_kwargs"]["clear_thinking"] is True
    assert all(
        body["max_completion_tokens"] == 32768 and body["reasoning_effort"] == "low"
        for body in glm_requests[1:]
    )
    with r.store.tx() as c:
        glm_calls = [
            call
            for call in r.store.list(c, "call", view["chat"]["mission_id"])
            if call["model"] == "zai-org/GLM-5.3-Flash"
        ]
        assert glm_calls
        for call in glm_calls:
            reserved_output = c.execute(
                "SELECT json_extract(body,'$.output_bound') FROM reservations WHERE id=?",
                (call["reservation_id"],),
            ).fetchone()[0]
            assert reserved_output == call["generation"]["effective_output_tokens"]
    assert len(physical) == 13
    assert view["accounting"]["total"]["attempts"] == 13
    assert (
        sum(x["attempt_class"] == "research" for x in view["accounting"]["attempts"])
        == 1
    )
    assert any(x["name"] == "web_search" for x in view["research_tools"])
    assert any(x["name"] == "library_search" for x in view["research_tools"])
    assert all(
        x["price_card"]["verification_id"] for x in view["accounting"]["attempts"]
    )
    first = next(
        x for x in view["accounting"]["attempts"] if x["model"] == r.settings.models[0]
    )
    assert first["price_card"]["rates"]["cache_read_input"] == "0.06"
    assert first["cost"]["known_subtotal_usd"] != "0"
    openings = [p for p in view["context_packs"] if p["namespace"]["role"] == "opening"]
    assert len(openings) == 4 and len({p["snapshot_id"] for p in openings}) == 1
    with r.store.tx() as c:
        assert r.chat.runtime.recovery_usage(c, view["chat"]) == 0
        assert r.budget.summary(c)["global_committed_usd"] > 0
    followup = client.post(
        f"/api/chats/{cid}/messages",
        headers={"Idempotency-Key": "tf-followup"},
        json={"text": "Compare the options again with a different general goal."},
    )
    assert followup.is_success, followup.text
    assert followup.json()["chat"]["id"] == cid
    drain(app)
    latest = client.get("/api/chats/" + cid).json()
    assert latest["chat"]["status"] == "completed", latest["chat"].get("error")
    assert latest["accounting"]["total"]["attempts"] > 20
    assert latest["budget"]["absolute_cap_usd"] == 24


def test_token_factory_cached_price_and_algorithm_are_frozen_after_rates_change(
    app, monkeypatch
):
    r = setup_testing(app)
    from test_budget import configured

    _, mid, model = configured(app, 1)
    original = httpx.Client

    def handler(request):
        return httpx.Response(
            200,
            json={
                "model": model,
                "choices": [
                    {"finish_reason": "stop", "message": {"content": "A saved answer"}}
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            },
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    _, call = r.provider.call(mid, "A compact trial prompt", 32, model=model)
    with r.store.tx() as c:
        before = r.accounting.attempt(c, call)
        v = r.store.setting(c, "live_verification")
        v["prices"][model]["input"] = 99
        r.store.set_setting(c, "live_verification", v)
        after = r.accounting.attempt(c, call)
        assert before["price_card"] == after["price_card"]
        assert before["cost"] == after["cost"]
