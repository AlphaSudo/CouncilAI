"""Per-reply discovery without an extra model turn or fabricated search claims."""

import re

from .db import DomainError, digest, now

POLICY = "per-reply-search/1"
FOCUS = {
    "opening": "primary sources evidence overview",
    "extraction": "definitions claims evidence primary sources",
    "scrutiny": "limitations counterexamples evidence primary sources",
    "repair": "limitations practical alternatives evidence primary sources",
    "recheck": "verification limitations independent evidence",
    "synthesis": "comparison recommendations limitations primary sources",
}


def resolve_default(council, body):
    if body.search_web is not None:
        return body
    enabled = (
        bool(council.settings.tavily_api_key)
        and body.provider in ("direct_council", "nebius_token_factory")
        and body.mode == "reviewed"
        and body.review_protocol in ("reviewed_v3", "reviewed_v4")
    )
    return body.model_copy(update={"search_web": enabled})


def apply_pending(council, c, chat):
    if "next_turn_research_enabled" in chat:
        enabled = chat.pop("next_turn_research_enabled")
        chat.update(
            research_enabled=enabled,
            next_research_enabled=enabled,
            research_tools_enabled=True,
            revision=chat["revision"] + 1,
        )
        council.store.put(c, "chat", chat)


def prepare(research, chat, turn, logical, cancelled):
    identifier = "reply_search_" + digest([chat["id"], logical])[:24]
    with research.store.tx() as c:
        if c.execute("SELECT 1 FROM records WHERE id=?", (identifier,)).fetchone():
            return research.store.get(c, identifier, "response_search")
        record = research.chat.review.record(c, chat)
        question = chat.get("research_query") or record["contract"]["question"]
        if not chat.get("research_query"):
            from .council_message_edits import on_path

            messages = on_path(research.chat, c, chat, research.chat.messages(c, chat))
            current = [
                m
                for m in messages
                if m["role"] == "user" and m.get("review_cycle") == record["cycle"]
            ]
            if current and current[-1]["content"] != question:
                # Keep the latest request visible even when the root is very long.
                question = question[:150] + " " + current[-1]["content"][:150]
    # A compact public query, never a transcript, attachment or private reasoning.
    topic = re.sub(r"\s+", " ", re.sub(r"[#*`{}<>]", " ", question)).strip()[:300]
    query = topic + " " + FOCUS.get(turn["phase"], "primary sources evidence")
    result = {
        "id": identifier,
        "chat_id": chat["id"],
        "mission_id": chat["mission_id"],
        "logical_turn_id": logical,
        "review_cycle": chat.get("review_cycle"),
        "phase": turn["phase"],
        "member_id": turn["participant"]["id"],
        "query": query[:400],
        "policy": POLICY,
        "created_at": now(),
        "status": "unavailable",
        "reused": False,
        "source_version_ids": [],
    }
    try:
        found = research.tools.execute(
            chat,
            {
                "name": "web_search",
                "arguments": {
                    "query": result["query"],
                    "limit": 3,
                },
            },
            seat=turn["participant"]["id"],
            logical_turn_id=logical,
            step_key=identifier,
            cancelled=cancelled,
        )
        result.update(
            status="completed" if "results" in found else "unavailable",
            receipt_id=found.get("receipt_id"),
            reused=bool(found.get("reused")),
            result_count=len(found.get("results", [])),
            source_version_ids=[
                x["snippet_version_id"]
                for x in found.get("results", [])
                if x.get("snippet_version_id")
            ],
        )
        if found.get("reason"):
            result["reason"] = found["reason"]
    except DomainError as error:
        result.update(reason=error.message, code=error.code)
    # Discovery failure is a visible limitation, never a reason to discard an answer.
    with research.store.tx() as c:
        stage = (
            ("web-opening:" + str(chat.get("review_cycle", chat["generation"])))
            if turn["phase"] == "opening"
            else identifier
        )
        snapshots = [
            s
            for s in research.store.list(c, "library_snapshot", chat["mission_id"])
            if s["stage"] == stage
        ]
        snapshot = (
            snapshots[0] if snapshots else research.library.snapshot(c, chat, stage)
        )
        result["snapshot_id"] = snapshot["id"]
        research.store.put(c, "response_search", result)
    return result


def finish(research, answer, call, search):
    if search:
        call["web_search"] = {
            k: search[k]
            for k in (
                "id",
                "status",
                "query",
                "reused",
                "receipt_id",
                "result_count",
                "reason",
                "collective_research_id",
                "shared_source_count",
                "extracted_pages",
            )
            if k in search
        }
        with research.store.tx() as c:
            saved = research.store.get(c, call["id"], "call")
            saved["web_search"] = call["web_search"]
            research.store.put(c, "call", saved)
    return answer, call
