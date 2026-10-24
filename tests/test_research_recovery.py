import json
import runpy
from pathlib import Path

import pytest
from test_unified_council import create
from test_workflow import post

from zerowall.api import create_app
from zerowall.db import DomainError
from zerowall.research_execution import public_response
from zerowall.settings import Settings


def test_A14_no_automatic_upload_of_question_as_search_query(client, app, monkeypatch):
    from test_direct_provider import setup_direct

    r = setup_direct(app)
    r.settings.tavily_api_key = "synthetic"
    initial = create(
        client,
        provider="direct_council",
        models=list(r.direct_provider.entries()),
        search_web=True,
        defer_start=True,
    )
    monkeypatch.setattr(
        r.tools.provider,
        "search",
        lambda **kw: pytest.fail("No neutral query was approved"),
    )
    r.research_execution.prepare_neutral(
        initial["chat"], {"phase": "opening"}, lambda: False
    )
    with r.store.tx() as c:
        plan = r.store.list(c, "research_plan", initial["chat"]["mission_id"])[0]
        assert not plan["query"] and plan["state"] == "complete"


def test_A23_completed_checkpoint_actions_are_reused_on_explicit_resume(client, app):
    r, chat = app.state.research, create(client)["chat"]
    with r.store.tx() as c:
        snapshot = r.tools.stage(c, chat, {"phase": "scrutiny"})
        checkpoint = {
            "id": "checkpoint_resume",
            "mission_id": chat["mission_id"],
            "chat_id": chat["id"],
            "snapshot_id": snapshot["id"],
            "logical_turn_id": "resume_turn",
            "state": "pending",
            "results": [],
            "exchange": {
                "actions": [
                    {"name": "library_search", "arguments": {"query": "boundary"}}
                ]
            },
        }
        r.store.put(c, "research_checkpoint", checkpoint)
    turn = {"phase": "scrutiny", "participant": chat["participants"][0]}
    r.research_execution.finish_checkpoint(chat, turn, checkpoint, lambda: False)
    r.research_execution.finish_checkpoint(chat, turn, checkpoint, lambda: False)
    with r.store.tx() as c:
        assert len(r.store.list(c, "tool_invocation", chat["mission_id"])) == 1
        assert r.store.get(c, checkpoint["id"])["state"] == "complete"


def test_A13_citation_requires_the_exact_passage_to_have_been_exposed(client, app):
    r, chat = app.state.research, create(client)["chat"]
    version = r.library.ingest(
        chat, b"Boundary line one.\nBoundary line two.\n", title="Citation source"
    )
    with r.store.tx() as c:
        call = {
            "id": "cite_call",
            "mission_id": chat["mission_id"],
            "purpose": "citation_turn",
        }
        r.store.put(c, "call", call)
        message = {
            "id": "cite_message",
            "call_id": call["id"],
            "content": f"Only this passage [source:{version['id']}:L1-L2]",
        }
        before = r.library.bind_message(c, chat, message)[0]
        assert before["span_exists"] and not before["exposed_passage"]
        r.library.read(
            c,
            chat,
            version["id"],
            line_start=1,
            line_end=2,
            logical_turn_id=call["purpose"],
        )
        after = r.library.bind_message(c, chat, message)[0]
        assert after["exposed_passage"] and not after["human_assessed"]


def test_A07_A24_backup_restore_preserves_sources_without_credentials(
    client, app, tmp_path
):
    r, chat = app.state.research, create(client)["chat"]
    version = r.library.ingest(
        chat, b"A portable source qualification.", title="Backup source"
    )
    module = runpy.run_path(str(Path("scripts/backup.py").resolve()))
    archive = tmp_path / "backup.zip"
    assert not module["backup"](archive, r.settings)["credential_files_included"]
    restored = tmp_path / "restored"
    module["restore"](archive, restored)
    settings = Settings(restored)
    settings.direct_keys, settings.api_key, settings.tavily_api_key = {}, "", ""
    restored_r = create_app(settings, run_worker=False).state.research
    with restored_r.store.tx() as c:
        assert (
            restored_r.library.read(c, chat, version["id"])["text"]
            == "A portable source qualification."
        )
        assert not restored_r.store.setting(c, "live_verification", {})


def test_A07_explicit_source_removal_reports_replay_limit(client, app):
    r, chat = app.state.research, create(client)["chat"]
    version = r.library.ingest(
        chat, b"Removable original source.", title="Remove source"
    )
    with r.store.tx() as c:
        r.library.forget(c, chat, version["source_id"])
        assert not r.store.list(c, "source_chunk", chat["mission_id"])
        with pytest.raises(DomainError, match="removed"):
            r.library.read(c, chat, version["id"])
    r.library.cleanup_orphans()
    assert not (r.library.root / version["raw_sha256"]).exists()


def test_A07_document_attachment_can_be_imported_before_any_work(client, app):
    initial = create(client, defer_start=True)
    assert initial["chat"]["status"] == "paused"
    assert not app.state.executor.run_once()
    post(
        client,
        f"/chats/{initial['chat']['id']}/library/import",
        {"title": "Input", "text": "An exact user constraint."},
    )
    view = post(client, f"/chats/{initial['chat']['id']}/control", {"action": "resume"})
    assert view["chat"]["status"] == "running"
    assert len(view["library"]["versions"]) == 1


def test_A15_private_reasoning_is_not_persisted_but_opaque_signatures_survive():
    value = {
        "choices": [
            {"message": {"reasoning_content": "private", "content": "Public answer"}}
        ],
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "private thought", "thought": True},
                        {
                            "functionCall": {"name": "library_search"},
                            "thoughtSignature": "opaque",
                        },
                    ]
                }
            }
        ],
        "usage": {"completion_tokens_details": {"reasoning_tokens": 12}},
    }
    result = public_response(value)
    assert "private" not in json.dumps(result)
    assert result["usage"]["completion_tokens_details"]["reasoning_tokens"] == 12
    assert "opaque" in json.dumps(result)


def test_A04_released_resource_is_readmitted_against_current_cap(client, app):
    r, chat = app.state.research, create(client)["chat"]
    with r.store.tx() as c:
        first = r.tools.policy.reserve(c, chat, "search_credits", 1, "first")
        r.tools.policy.update(c, first, "released")
        r.tools.policy.reserve(c, chat, "search_credits", 3, "other")
        with pytest.raises(DomainError):
            r.tools.policy.reserve(c, chat, "search_credits", 1, "first")


def test_A04_focused_exchange_reallocates_unused_research_instead_of_exceeding_twenty(
    client, app
):
    from test_direct_provider import setup_direct

    r = setup_direct(app)
    r.settings.tavily_api_key = "synthetic"
    chat = create(
        client,
        provider="direct_council",
        models=list(r.direct_provider.entries()),
        search_web=True,
        defer_start=True,
    )["chat"]
    with r.store.tx() as c:
        r.chat.runtime.expand(c, chat, 2)
        mission = r.store.get(c, chat["mission_id"], "mission")
        assert mission["direct_attempt_window"]["research_call_limit"] == 3
        assert r.store.list(c, "chat_capacity", chat["mission_id"])[-1]["initial"] == 20
        with pytest.raises(DomainError):
            r.tools.policy.reserve(c, chat, "research_calls", 4, "too-many")


def test_A23_unknown_search_requires_explicit_human_retry_and_keeps_both_reservations(
    client, app, monkeypatch
):
    import httpx

    r, chat = app.state.research, create(client)["chat"]
    chat["research_enabled"] = True
    with r.store.tx() as c:
        r.store.put(c, "chat", chat)
    monkeypatch.setattr(r.tools.provider, "allowance", dict)

    def lost(**kwargs):
        raise httpx.ReadTimeout("ambiguous")

    monkeypatch.setattr(r.tools.provider, "search", lost)
    action = {"name": "web_search", "arguments": {"query": "Public document"}}
    with pytest.raises(DomainError):
        r.tools.execute(chat, action)
    unavailable = r.tools.execute(chat, action, authorize_unknown_retry=True, seat="model")
    assert unavailable["status"] == "unavailable" and unavailable["repeated_dispatch"] is False
    monkeypatch.setattr(r.tools.provider, "search", lambda **kwargs: {"results": []})
    assert not r.tools.execute(chat, action, authorize_unknown_retry=True)["reused"]
    with r.store.tx() as c:
        credits = r.store.list(c, "search_credit", chat["mission_id"])
        assert (
            len(credits) == 2
            and credits[0]["state"] == "unknown"
            and credits[1]["state"] == "consumed"
        )


def test_A18_parallel_public_fetches_are_bounded_and_checkpointed(
    client, app, monkeypatch
):
    import threading

    r, chat = app.state.research, create(client)["chat"]
    chat["research_enabled"] = True
    with r.store.tx() as c:
        r.store.put(c, "chat", chat)
        snapshot = r.tools.stage(c, chat, {"phase": "scrutiny"})
    lock, active, peak = threading.Lock(), 0, 0
    paired_fetches = threading.Barrier(2)

    def fetch(url, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        # Prove overlap without relying on a 30 ms scheduler window under load.
        paired_fetches.wait(timeout=5)
        with lock:
            active -= 1
        return {
            "raw": ("Source " + url).encode(),
            "mime": "text/plain",
            "raw_bytes": 40,
            "metadata": {"final_url": url},
            "not_modified": False,
        }

    monkeypatch.setattr("zerowall.research_tools.fetch", fetch)
    checkpoint = {
        "id": "checkpoint_parallel",
        "mission_id": chat["mission_id"],
        "chat_id": chat["id"],
        "snapshot_id": snapshot["id"],
        "logical_turn_id": "parallel_turn",
        "state": "pending",
        "results": [],
        "exchange": {
            "actions": [
                {
                    "name": "web_fetch",
                    "arguments": {"url": "https://example.com/" + str(i)},
                }
                for i in range(4)
            ]
        },
    }
    r.research_execution.finish_checkpoint(
        chat,
        {"phase": "scrutiny", "participant": chat["participants"][0]},
        checkpoint,
        lambda: False,
    )
    assert peak == 2
    assert len(checkpoint["results"]) == 4 and checkpoint["state"] == "complete"
    assert len(checkpoint["completed_results"]) == 4
    with r.store.tx() as c:
        assert len(r.store.list(c, "tool_invocation", chat["mission_id"])) == 4
