import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import httpx
import pytest
from test_council_chat import drain
from test_direct_provider import setup_direct
from test_unified_council import create

from zerowall.db import DomainError
from zerowall.research_execution import (
    append_results,
    extract_exchange,
    transport_tools,
)
from zerowall.research_tools import catalogue


def test_A15_full_review_tool_continuation_and_usage_within_envelope(
    client, app, monkeypatch
):
    r = setup_direct(app)
    r.settings.tavily_api_key = "synthetic-search-key"
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
    physical, action_done = [], []
    original = httpx.Client

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
        usage = {
            "prompt_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens": 20,
            "completion_tokens_details": {"reasoning_tokens": 0},
        }
        if request.url.host == "generativelanguage.googleapis.com":
            model = request.url.path.split("/models/")[1].split(":")[0]
            return httpx.Response(
                200,
                json={
                    "modelVersion": model,
                    "candidates": [
                        {"finishReason": "STOP", "content": {"parts": [{"text": text}]}}
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 100,
                        "cachedContentTokenCount": 0,
                        "candidatesTokenCount": 20,
                        "thoughtsTokenCount": 0,
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [{"finish_reason": "stop", "message": {"content": text}}],
                "usage": usage,
            },
        )

    monkeypatch.setattr(
        "zerowall.direct_provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    initial = create(
        client,
        provider="direct_council",
        models=list(r.direct_provider.entries()),
        search_web=True,
        search_query="Public generic software comparison evidence",
        collective_research=False,
    )
    assert initial["direct_capacity"]["remaining_calls"] == 20
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert len(physical) == 13
    assert view["accounting"]["total"]["attempts"] == 13
    assert view["accounting"]["total"]["usage_reported_attempts"] == 13
    assert (
        sum(x["attempt_class"] == "research" for x in view["accounting"]["attempts"])
        == 1
    )
    assert sum(x["name"] == "web_search" for x in view["research_tools"]) == 6
    assert sum(x["name"] == "library_search" for x in view["research_tools"]) == 1
    openings = [p for p in view["context_packs"] if p["namespace"]["role"] == "opening"]
    assert len(openings) == 4 and len({p["snapshot_id"] for p in openings}) == 1
    with r.store.tx() as c:
        assert r.chat.runtime.recovery_usage(c, view["chat"]) == 0
    assert len(physical) <= 12 + 5 + 3


@pytest.mark.parametrize("provider", ["groq", "zai", "nvidia_nim", "gemini"])
def test_A15_native_contract_preserves_ids_signatures_and_ordinary_completion(provider):
    entry = {"provider": provider}
    request = (
        {
            "messages": [
                {"role": "system", "content": "Policy"},
                {"role": "user", "content": "Question"},
            ]
        }
        if provider != "gemini"
        else {
            "systemInstruction": {"parts": [{"text": "Policy"}]},
            "contents": [{"role": "user", "parts": [{"text": "Question"}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
    )
    options = {
        "prefix": "Stable prefix",
        "mode": "native",
        "catalogue": catalogue(),
        "history": [],
    }
    body = transport_tools(entry, request, options)
    assert "tools" in body
    if provider == "gemini":
        assistant = {
            "role": "model",
            "parts": [
                {
                    "functionCall": {
                        "name": "library_search",
                        "args": {"query": "boundary"},
                        "id": "function-1",
                    },
                    "thoughtSignature": "opaque-signature",
                },
                {"text": "private text never retained", "thought": True},
            ],
        }
        raw = {"candidates": [{"content": assistant}]}
    else:
        raw = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "reasoning_content": "private text never retained",
                        "tool_calls": [
                            {
                                "id": "function-1",
                                "type": "function",
                                "function": {
                                    "name": "library_search",
                                    "arguments": '{"query":"boundary"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
    exchange = extract_exchange(provider, raw, "", options)
    assert exchange["actions"][0]["name"] == "library_search"
    history = []
    append_results(
        provider, history, exchange, [{"results": [], "untrusted_source": True}]
    )
    assert "private text never retained" not in json.dumps(history)
    assert "function-1" in json.dumps(history)
    if provider == "gemini":
        assert "opaque-signature" in json.dumps(history)
    final = transport_tools(
        entry, request, {**options, "history": history, "catalogue": []}
    )
    assert "tools" not in final


def test_A16_resource_limits_and_no_new_automatic_window(client, app):
    r, chat = app.state.research, create(client)["chat"]
    with r.store.tx() as c:
        for i in range(5):
            r.tools.policy.reserve(c, chat, "research_calls", 1, str(i))
        with pytest.raises(DomainError, match="limit"):
            r.tools.policy.reserve(c, chat, "research_calls", 1, "sixth")
        assert r.tools.policy.reserve(c, chat, "research_calls", 1, "1")["amount"] == 1
        assert not r.store.list(c, "chat_allowance", chat["mission_id"])


def test_A17_missing_key_and_web_off_never_dispatch(client, app, monkeypatch):
    r, chat = app.state.research, create(client)["chat"]
    monkeypatch.setattr(
        r.tools.provider,
        "search",
        lambda **kw: pytest.fail("No web dispatch permitted"),
    )
    with pytest.raises(DomainError, match="off"):
        r.tools.execute(
            chat, {"name": "web_search", "arguments": {"query": "Public information"}}
        )
    with pytest.raises(DomainError, match="unavailable"):
        r.tools.provider.allowance()


def test_A17_monthly_credit_ceiling_is_global_and_atomic(client, app):
    r = app.state.research
    chats = [create(client)["chat"] for _ in range(2)]
    r.settings.search_monthly_limit = 1

    def reserve(i):
        try:
            with r.store.tx() as c:
                r.tools.policy.reserve_monthly_search(
                    c, chats[i], "concurrent-" + str(i)
                )
            return True
        except DomainError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(reserve, range(2))) == 1


def test_A18_prefix_identity_and_source_invalidation(client, app):
    r, chat = app.state.research, create(client)["chat"]
    version = r.library.ingest(chat, b"Only for a fixed boundary.", title="Boundary")
    turn = {
        "phase": "opening",
        "key": "opening:1",
        "participant": chat["participants"][0],
    }
    with r.store.tx() as c:
        snap = r.tools.stage(c, chat, turn)
        _, prefix1, pack1 = r.context_packs.compile(
            c,
            chat,
            turn,
            json.dumps({"question": "First", "response_schema": {"type": "object"}}),
            snap,
        )
        _, prefix2, pack2 = r.context_packs.compile(
            c,
            chat,
            turn,
            json.dumps({"question": "Second", "response_schema": {"type": "object"}}),
            snap,
        )
        assert prefix1 == prefix2
        assert pack1["dynamic_hash"] != pack2["dynamic_hash"]
        assert pack1["actual_cache_hit"] == "not_established"
    r.library.ingest(chat, b"A different boundary.", title="Boundary")
    with r.store.tx() as c:
        newer = r.library.snapshot(c, chat, "next")
        _, prefix3, _ = r.context_packs.compile(c, chat, turn, "{}", newer)
        assert prefix1 != prefix3
        assert version["id"] in snap["version_ids"]


def test_A20_A21_mandatory_context_is_not_lost_or_summarized(client, app):
    r, chat = app.state.research, create(client)["chat"]
    turn = {"phase": "scrutiny", "key": "test", "participant": chat["participants"][0]}
    payload = {
        "hard_constraint": "No additional payment",
        "open_findings": [
            {"id": "finding_a", "qualifier": "Only under stated conditions"}
        ],
        "dissent": "Do not infer agreement",
    }
    with r.store.tx() as c:
        snapshot = r.tools.stage(c, chat, turn)
        prompt, _, pack = r.context_packs.compile(
            c, chat, turn, json.dumps(payload), snapshot
        )
        assert json.loads(prompt) == payload
        assert pack["protected_review_input_complete"]
        summaries = r.store.list(c, "context_compaction", chat["mission_id"])
        assert (
            summaries[-1]["llm_summary_calls"] == 0
            and not summaries[-1]["original_history_deleted"]
        )
        with pytest.raises(DomainError, match="Required review context"):
            r.context_packs.compile(
                c, chat, turn, json.dumps({"must_keep": "X" * 95000}), snapshot
            )


def test_A22_request_credit_race_does_not_overshoot(client, app):
    r, chat = app.state.research, create(client)["chat"]

    def reserve(index):
        try:
            with r.store.tx() as c:
                r.tools.policy.reserve(c, chat, "search_credits", 1, str(index))
            return True
        except DomainError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(8))) == 3


def test_A23_unknown_search_is_counted_and_not_redispatched(client, app, monkeypatch):
    r, chat = app.state.research, create(client)["chat"]
    chat["research_enabled"] = True
    with r.store.tx() as c:
        r.store.put(c, "chat", chat)
    calls = []
    monkeypatch.setattr(r.tools.provider, "allowance", dict)

    def lost(**kw):
        calls.append(kw)
        raise httpx.ReadTimeout("ambiguous")

    monkeypatch.setattr(r.tools.provider, "search", lost)
    action = {"name": "web_search", "arguments": {"query": "Public sources"}}
    with pytest.raises(DomainError):
        r.tools.execute(chat, action)
    with pytest.raises(DomainError, match="unknown outcome"):
        r.tools.execute(chat, action)
    assert len(calls) == 1
    with r.store.tx() as c:
        assert (
            r.store.list(c, "search_credit", chat["mission_id"])[0]["state"]
            == "unknown"
        )


def test_A23_restart_does_not_release_unknown_external_reservation(client, app):
    r, chat = app.state.research, create(client)["chat"]
    with r.store.tx() as c:
        reservation = r.tools.policy.reserve(
            c, chat, "search_credits", 1, "interrupted"
        )
    r.tools.policy.recover()
    with r.store.tx() as c:
        assert r.store.get(c, reservation["id"])["state"] == "unknown"


@pytest.mark.parametrize(
    "name,args",
    [
        ("shell", {"command": "dir"}),
        ("web_search", {"query": "x", "include_answer": True}),
        ("web_fetch", {"url": "https://example.com", "api_key": "x"}),
        ("library_read", {"version_id": "v", "line_start": False}),
    ],
)
def test_A12_A15_unapproved_tools_or_arguments_are_rejected(client, app, name, args):
    with pytest.raises((ValueError, DomainError)):
        app.state.research.tools.validate_action({"name": name, "arguments": args})


@pytest.mark.parametrize("provider", ["groq", "zai", "nvidia_nim", "gemini"])
def test_A15_exact_configured_native_transport_is_counted_and_preserves_identity(
    client, app, monkeypatch, provider
):
    r = setup_direct(app)
    chat = create(
        client,
        provider="direct_council",
        models=list(r.direct_provider.entries()),
        defer_start=True,
    )["chat"]
    mid, entry = next(
        (k, e)
        for k, e in r.direct_provider.entries().items()
        if e["provider"] == provider
    )
    original = httpx.Client

    def handler(request):
        body = json.loads(request.content)
        assert "tools" in body
        if provider == "gemini":
            assert "parametersJsonSchema" in body["tools"][0]["functionDeclarations"][0]
            raw = {
                "modelVersion": entry["model"],
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "role": "model",
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "library_search",
                                        "args": {"query": "boundary"},
                                        "id": "exact-1",
                                    },
                                    "thoughtSignature": "opaque",
                                }
                            ],
                        },
                    }
                ],
                "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 5},
            }
        else:
            raw = {
                "model": entry["model"],
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "exact-1",
                                    "type": "function",
                                    "function": {
                                        "name": "library_search",
                                        "arguments": '{"query":"boundary"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 5},
            }
        return httpx.Response(200, json=raw)

    monkeypatch.setattr(
        "zerowall.direct_provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    exchange, call = r.direct_provider.call(
        chat["mission_id"],
        "{}",
        128,
        model=mid,
        purpose="native-fixture",
        research_options={
            "mode": "native",
            "catalogue": catalogue(),
            "prefix": "",
            "history": [],
        },
    )
    assert exchange["actions"][0]["call_id"] == "exact-1"
    assert call["state"] == "tool_response" and call["attempt_class"] == "research"
    assert call["returned_model"] == entry["model"]
    with r.store.tx() as c:
        assert r.accounting.projection(c, chat)["total"]["attempts"] == 1
