"""Model-directed parallel discovery, followed by one durable shared-source barrier."""

import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx

from .db import DomainError, digest, now
from .research_tools import catalogue
from .web_fetch import canonical_url

POLICY = "collective-research/1"
LENSES = (
    ("Foundations", "primary sources definitions governing principles and boundaries"),
    (
        "Approaches",
        "practical mechanisms implementations research papers and measured evidence",
    ),
    (
        "Challenges",
        "counterexamples feasibility limitations tradeoffs and contradictory evidence",
    ),
    (
        "Applications",
        "operating conditions deployment constraints and independent comparisons",
    ),
)
_guard = threading.Lock()
_locks = {}


def identifier(chat):
    return (
        "collective_"
        + digest([chat["id"], chat.get("review_cycle", chat["generation"])])[:24]
    )


def snapshot(research, c, chat):
    key = identifier(chat)
    if not c.execute("SELECT 1 FROM records WHERE id=?", (key,)).fetchone():
        return None
    record = research.store.get(c, key, "collective_research")
    return {
        **record,
        "members": [
            x
            for x in research.store.list(c, "research_contribution", chat["mission_id"])
            if x["collective_id"] == key
        ],
    }


def save(research, kind, record):
    with research.store.tx() as c:
        research.store.put(c, kind, record)
        research.store.event(
            c,
            record["mission_id"],
            "research.collective_progress",
            {
                "chat_id": record["chat_id"],
                "id": record["id"],
                "state": record.get("state"),
            },
        )


def question(research, c, chat):
    from .council_message_edits import on_path

    record = research.chat.review.record(c, chat)
    current = [
        m
        for m in on_path(research.chat, c, chat, research.chat.messages(c, chat))
        if m["role"] == "user" and m.get("review_cycle") == record["cycle"]
    ]
    return chat.get("research_query") or (
        (record["contract"]["question"][:150] + " " + current[-1]["content"][:150])
        if current and current[-1]["content"] != record["contract"]["question"]
        else record["contract"]["question"]
    )


def plan(research, chat, member, contribution, topic, cancelled):
    if contribution.get("query"):
        return contribution
    fallback = (
        re.sub(r"\s+", " ", re.sub(r"[#*`{}<>]", " ", topic)).strip()[:260]
        + " "
        + contribution["focus"]
    )
    logical = f"collective-research:{chat['id']}:{chat.get('review_cycle', chat['generation'])}:{member['id']}"
    with research.store.tx() as c:
        prior = [
            x
            for x in research.store.list(c, "call", chat["mission_id"])
            if x["purpose"] == logical
        ]
    contribution.update(state="planning", query_origin="fallback", query=fallback[:400])
    if prior or contribution.get("plan_dispatched"):
        contribution.update(
            planning_limitation="Earlier planning attempt retained; no automatic model retry",
            call_id=prior[-1]["id"] if prior else None,
        )
        save(research, "research_contribution", contribution)
        return contribution
    slot = None
    try:
        with research.store.tx() as c:
            slot = research.tools.policy.reserve(
                c, chat, "research_calls", 1, contribution["id"] + ":plan"
            )
        contribution["plan_dispatched"] = True
        save(research, "research_contribution", contribution)
        provider = (
            research.provider
            if chat["provider"] == "nebius_token_factory"
            else research.direct_provider
        )
        prompt = json.dumps(
            {
                "task": 'Choose one focused public web-search query for the assigned research angle. Do not answer the user\'s question, make a proposal, or generate private reasoning. Return only {"research_actions":[{"name":"web_search","arguments":{"query":"your query, at most 400 characters","limit":3}}]}. Prefer original papers, official documentation and primary evidence. Other council members research different angles concurrently.',
                "question": topic,
                "assigned_angle": contribution["focus"],
            },
            ensure_ascii=False,
        )
        options = {
            "catalogue": [t for t in catalogue(web=True) if t["name"] == "web_search"],
            "mode": "structured",
            "history": [],
            "prefix": "",
            "purpose_kind": "collective_research_plan",
            "context_pack_id": None,
        }
        kwargs = {}
        if chat["provider"] == "nebius_token_factory":
            from .token_factory_generation import profile, reasoning_instruction

            generation = profile(
                research.settings,
                {"phase": "research_plan", "participant": member},
                thinking_level="quick",
            )
            generation.update(
                requested_output_tokens=8192,
                reasoning_budget_tokens=1024,
                reasoning_budget_instruction=reasoning_instruction(1024),
                read_idle_timeout_seconds=45,
            )
            kwargs["generation"] = generation

            def stream_cancelled():
                if not cancelled():
                    return False
                with research.store.tx() as c:
                    return (
                        research.store.get(c, chat["id"], "chat")["status"] != "paused"
                    )

            kwargs["stream_cancelled"] = stream_cancelled
        answer, call = provider.call(
            chat["mission_id"],
            prompt,
            8192,
            model=member["model"],
            purpose=logical,
            cancelled=cancelled,
            research_options=options,
            **kwargs,
        )
        contribution["call_id"] = call["id"]
        value = (
            answer
            if isinstance(answer, dict)
            else json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", answer.strip()))
        )
        actions = value.get("actions", value.get("research_actions", []))
        query = next(
            a["arguments"]["query"] for a in actions if a.get("name") == "web_search"
        )
        if not isinstance(query, str) or not query.strip() or len(query) > 400:
            raise ValueError("No bounded search query")
        research.library.check_secret(query)
        contribution.update(query=query.strip(), query_origin="model")
    except (
        DomainError,
        ValueError,
        TypeError,
        KeyError,
        StopIteration,
        OSError,
        httpx.HTTPError,
    ) as error:
        contribution["planning_limitation"] = (
            error.message
            if isinstance(error, DomainError)
            else "No usable research query; assigned-angle query used"
        )
    finally:
        with research.store.tx() as c:
            calls = [
                x
                for x in research.store.list(c, "call", chat["mission_id"])
                if x["purpose"] == logical
            ]
            if calls:
                contribution.update(
                    call_id=calls[-1]["id"], planning_outcome=calls[-1]["state"]
                )
            if slot:
                research.tools.policy.update(
                    c,
                    slot,
                    "consumed"
                    if calls and calls[-1]["state"] != "cancelled_undispatched"
                    else "released",
                )
        contribution["state"] = "planned"
        save(research, "research_contribution", contribution)
    return contribution


def search(research, chat, contribution, cancelled):
    if contribution.get("search_finished"):
        return contribution
    contribution["state"] = "searching"
    save(research, "research_contribution", contribution)
    try:
        found = research.tools.execute(
            chat,
            {
                "name": "web_search",
                "arguments": {"query": contribution["query"], "limit": 3},
            },
            seat=contribution["member_id"],
            logical_turn_id=contribution["id"],
            step_key=contribution["id"] + ":search",
            cancelled=cancelled,
        )
        contribution.update(
            results=found.get("results", []),
            search_receipt_id=found.get("receipt_id"),
            reused=bool(found.get("reused")),
            search_finished=True,
        )
        if found.get("reason"):
            contribution["search_limitation"] = found["reason"]
    except DomainError as error:
        contribution.update(
            search_limitation=error.message, search_finished=not cancelled()
        )
    contribution["state"] = "searched" if contribution.get("results") else "limited"
    save(research, "research_contribution", contribution)
    return contribution


def prepare(research, chat, cancelled):
    key = identifier(chat)
    with _guard:
        lock = _locks.setdefault(key, threading.Lock())
    with lock:
        with research.store.tx() as c:
            existing = snapshot(research, c, chat)
            if existing and existing["state"] in ("ready", "limited"):
                return existing
            if existing and not chat.get("research_enabled"):
                frozen = research.library.snapshot(c, chat, key + ":shared")
                record = {k: v for k, v in existing.items() if k != "members"}
                preferred = list(frozen["version_ids"])[:12]
                record.update(
                    state="limited",
                    snapshot_id=frozen["id"],
                    preferred_version_ids=preferred,
                    source_count=len(preferred),
                    extracted_pages=record.get("extracted_pages", 0),
                    completed_at=now(),
                    extraction_limitation="Research was turned off; remaining preparation was skipped and only saved sources are shared",
                )
                research.store.put(c, "collective_research", record)
                return {**record, "members": existing["members"]}
            if not existing and any(
                m.get("phase") == "opening"
                and m.get("review_cycle") == chat.get("review_cycle")
                for m in research.chat.messages(c, chat)
            ):
                return None  # New research does not retroactively change an opening cohort.
            topic = question(research, c, chat)
            members = research.chat.active_members(chat)
            record = (
                {k: v for k, v in existing.items() if k != "members"}
                if existing
                else {
                    "id": key,
                    "mission_id": chat["mission_id"],
                    "chat_id": chat["id"],
                    "cycle": chat.get("review_cycle"),
                    "policy": POLICY,
                    "created_at": now(),
                    "state": "planning",
                    "planning_parallelism": min(3, len(members)),
                    "peer_answers_seen": False,
                    "topic": topic,
                }
            )
            contributions = {}
            for index, member in enumerate(members):
                cid = key + "_" + member["id"]
                if c.execute("SELECT 1 FROM records WHERE id=?", (cid,)).fetchone():
                    contribution = research.store.get(c, cid, "research_contribution")
                else:
                    title, focus = LENSES[index % len(LENSES)]
                    contribution = {
                        "id": cid,
                        "collective_id": key,
                        "chat_id": chat["id"],
                        "mission_id": chat["mission_id"],
                        "member_id": member["id"],
                        "model": member["model"],
                        "name": member["name"],
                        "angle": title,
                        "focus": focus,
                        "state": "queued",
                        "results": [],
                    }
                    research.store.put(c, "research_contribution", contribution)
                contributions[member["id"]] = contribution
        record["state"] = "planning"
        save(research, "collective_research", record)
        try:
            allowance = research.tools.provider.allowance()
            if allowance["limit"] - allowance["used"] < len(members):
                raise DomainError(
                    "Insufficient confirmed free allowance for parallel discovery", 402
                )
        except (
            DomainError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            httpx.HTTPError,
        ) as error:
            for contribution in contributions.values():
                contribution.update(
                    query=(
                        re.sub(r"\s+", " ", topic)[:260] + " " + contribution["focus"]
                    )[:400],
                    query_origin="fallback",
                    planning_limitation="Model planning skipped because free web research is unavailable",
                    search_limitation=error.message
                    if isinstance(error, DomainError)
                    else "Free web allowance check unavailable; no planning or search dispatched",
                    search_finished=True,
                )
        with ThreadPoolExecutor(
            max_workers=3, thread_name_prefix="council-research-plan"
        ) as pool:
            futures = [
                pool.submit(
                    plan, research, chat, m, contributions[m["id"]], topic, cancelled
                )
                for m in members
            ]
            planned = [future.result() for future in futures]
        if cancelled():
            record["state"] = "paused"
            save(research, "collective_research", record)
            raise DomainError(
                "Collective research paused; completed work is saved", 409
            )
        # Avoid three identical model-generated queries while keeping the adjustment explicit.
        seen = set()
        for contribution in planned:
            normalized = contribution["query"].lower().strip()
            if normalized in seen:
                contribution.update(
                    query=(contribution["query"][:260] + " " + contribution["focus"])[
                        :400
                    ],
                    query_adjusted_for_overlap=True,
                )
            seen.add(normalized)
            save(research, "research_contribution", contribution)
        record["state"] = "searching"
        save(research, "collective_research", record)
        with ThreadPoolExecutor(
            max_workers=3, thread_name_prefix="council-search"
        ) as pool:
            contributions = list(
                pool.map(lambda x: search(research, chat, x, cancelled), planned)
            )
        if cancelled():
            record["state"] = "paused"
            save(research, "collective_research", record)
            raise DomainError(
                "Collective research paused; completed work is saved", 409
            )
        # Round-robin selection keeps all contributors represented before deduplication.
        pages = {}
        for rank in range(3):
            for contribution in contributions:
                for item in contribution.get("results", [])[rank : rank + 1]:
                    try:
                        url = canonical_url(item["url"])
                    except DomainError:
                        continue
                    if url not in pages:
                        pages[url] = {
                            "url": url,
                            "title": item.get("title", url),
                            "contributors": [],
                            "snippet_version_ids": [],
                        }
                    page = pages[url]
                    if contribution["member_id"] not in page["contributors"]:
                        page["contributors"].append(contribution["member_id"])
                    if (
                        item.get("snippet_version_id")
                        and item["snippet_version_id"]
                        not in page["snippet_version_ids"]
                    ):
                        page["snippet_version_ids"].append(item["snippet_version_id"])
        selected = list(pages.values())[:6]
        record.update(
            state="extracting",
            pages=list(pages.values()),
            unique_urls=len(pages),
            selected_urls=len(selected),
        )
        save(research, "collective_research", record)
        extracted = []
        if selected:
            try:
                batch = research.tools.execute(
                    chat,
                    {
                        "name": "web_extract",
                        "arguments": {"urls": [x["url"] for x in selected]},
                    },
                    seat="collective_library",
                    logical_turn_id=key,
                    step_key=key + ":extract",
                    cancelled=cancelled,
                )
                extracted = batch.get("versions", [])
                record.update(
                    extraction_receipt_id=batch.get("receipt_id"),
                    extraction_failures=batch.get("failed_results", []),
                )
                if batch.get("reason"):
                    record["extraction_limitation"] = batch["reason"]
            except DomainError as error:
                record["extraction_limitation"] = error.message
        by_url = {v["url"]: v for v in extracted}
        preferred = []
        for page in pages.values():
            if page["url"] in by_url:
                page.update(
                    version_id=by_url[page["url"]]["id"], access="extracted_page"
                )
                preferred.append(page["version_id"])
            else:
                page["access"] = "search_snippet_only"
                preferred.extend(page["snippet_version_ids"][:1])
        with research.store.tx() as c:
            frozen = research.library.snapshot(c, chat, key + ":shared")
            supplied = [
                vid
                for vid in frozen["version_ids"]
                if research.library.version(c, chat, vid)["origin"] == "user_supplied"
            ]
        preferred = list(dict.fromkeys(supplied + preferred))
        limited = (
            not extracted
            or record.get("extraction_failures")
            or record.get("extraction_limitation")
            or any(
                x.get("planning_limitation") or x.get("search_limitation")
                for x in contributions
            )
        )
        record.update(
            state="limited" if limited else "ready",
            pages=list(pages.values()),
            snapshot_id=frozen["id"],
            preferred_version_ids=list(dict.fromkeys(preferred)),
            extracted_pages=len(extracted),
            source_count=len(preferred),
            completed_at=now(),
            barrier="All selected researchers finished before opening answers; every opening receives this snapshot",
        )
        save(research, "collective_research", record)
        with research.store.tx() as c:
            return snapshot(research, c, chat)


def for_reply(research, chat, turn, logical, cancelled):
    collective = prepare(research, chat, cancelled)
    if not collective:
        return None
    member = next(
        (
            m
            for m in collective["members"]
            if m["member_id"] == turn["participant"]["id"]
        ),
        {},
    )
    result = {
        "id": "reply_search_" + digest([chat["id"], logical])[:24],
        "chat_id": chat["id"],
        "mission_id": chat["mission_id"],
        "logical_turn_id": logical,
        "review_cycle": chat.get("review_cycle"),
        "phase": "opening",
        "member_id": turn["participant"]["id"],
        "policy": POLICY,
        "collective_research_id": collective["id"],
        "status": "completed" if collective.get("unique_urls", 0) else "unavailable",
        "query": member.get("query", "Shared research"),
        "query_origin": member.get("query_origin"),
        "result_count": len(member.get("results", [])),
        "reused": bool(member.get("reused")),
        "source_version_ids": collective["preferred_version_ids"],
        "snapshot_id": collective["snapshot_id"],
        "shared_source_count": collective["source_count"],
        "extracted_pages": collective["extracted_pages"],
        "shared_topic": collective.get("topic", ""),
        "created_at": now(),
    }
    if not collective.get("unique_urls", 0):
        result["reason"] = (
            "Collective discovery returned no readable sources; answer with an explicit evidence limitation"
        )
    with research.store.tx() as c:
        research.store.put(c, "response_search", result)
    return result
