"""Local, authenticated research surfaces. Page loads never dispatch external work."""

import base64
import threading

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from .db import DomainError, canonical, digest
from .research_tools import ResearchAction


class ImportSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=240)
    text: str | None = Field(default=None, max_length=2097152)
    base64_content: str | None = Field(default=None, max_length=2796204)
    mime: str = "text/plain"


class ResearchSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


def install(app, research, auth, mutate):
    store = research.store
    locks, guard = {}, threading.Lock()

    async def outside_transaction(request, operation):
        key = request.headers.get("Idempotency-Key", "")
        if not key or len(key) > 180:
            raise DomainError("An Idempotency-Key is required", 400)
        body = await request.body()
        if len(body) > 3000000:
            raise DomainError("Source request exceeds upload limit", 413)
        hashed = digest([request.url.path, request.url.query, body.decode("utf-8")])

        def run():
            with guard:
                lock = locks.setdefault(key, threading.Lock())
            with lock, store.operation_lock('research:' + key):
                with store.tx() as c:
                    prior = c.execute(
                        "SELECT request_hash,response FROM idempotency WHERE key=?",
                        (key,),
                    ).fetchone()
                    if prior:
                        if prior["request_hash"] != hashed:
                            raise DomainError(
                                "Idempotency key reused with different input", 409
                            )
                        import json

                        return json.loads(prior["response"])
                result = operation(key)
                with store.tx() as c:
                    c.execute(
                        "INSERT INTO idempotency VALUES(?,?,?)",
                        (key, hashed, canonical(result)),
                    )
                return result

        return await run_in_threadpool(run)

    def chat_record(cid):
        with store.tx() as c:
            return store.get(c, cid, "chat")

    @app.get("/api/chats/{cid}/usage", dependencies=auth)
    def usage(cid: str):
        with store.tx() as c:
            return research.accounting.projection(c, store.get(c, cid, "chat"))

    @app.get("/api/chats/{cid}/library", dependencies=auth)
    def library(cid: str):
        with store.tx() as c:
            return research.library.view(c, store.get(c, cid, "chat"))

    @app.post("/api/chats/{cid}/library/import", dependencies=auth)
    async def import_source(cid: str, request: Request, body: ImportSource):
        if (body.text is None) == (body.base64_content is None):
            raise DomainError("Provide either text or a selected file, not both", 422)
        try:
            raw = (
                body.text.encode()
                if body.text is not None
                else base64.b64decode(body.base64_content, validate=True)
            )
        except ValueError:
            raise DomainError("Invalid selected-file encoding", 422) from None
        return await outside_transaction(
            request,
            lambda key: research.library.ingest(
                chat_record(cid), raw, title=body.title, mime=body.mime
            ),
        )

    @app.post("/api/chats/{cid}/research/tools", dependencies=auth)
    async def tool(
        cid: str,
        request: Request,
        body: ResearchAction,
        authorize_unknown_retry: bool = False,
    ):
        # An explicit URL-fetch click is allowed even when broad model search is off.
        return await outside_transaction(
            request,
            lambda key: research.tools.execute(
                chat_record(cid),
                body.model_dump(),
                seat="human",
                logical_turn_id="human:" + key,
                step_key="api:" + key,
                allow_web=True if body.name == "web_fetch" else None,
                authorize_unknown_retry=authorize_unknown_retry,
            ),
        )

    @app.post("/api/chats/{cid}/research/settings", dependencies=auth)
    async def settings(cid: str, request: Request, body: ResearchSetting):
        def change(c):
            chat = store.get(c, cid, "chat")
            if body.enabled and (
                chat["provider"] not in ("direct_council", "nebius_token_factory")
                or not research.settings.tavily_api_key
                or not chat.get("execution_descriptor")
            ):
                raise DomainError(
                    "Web research is unavailable for this saved execution contract", 412
                )
            if body.enabled:
                chat["web_search_policy"] = "per-reply-search/1"
                chat["collective_research_enabled"] = True
            if chat.get("active_turn") or chat["status"] in ("running", "waiting"):
                # Never invalidate the in-flight response or its research lease.
                chat["next_turn_research_enabled"] = body.enabled
            else:
                chat.update(research_enabled=body.enabled, next_research_enabled=body.enabled,
                            research_tools_enabled=True, revision=chat["revision"] + 1)
            store.put(c, "chat", chat)
            store.event(
                c,
                chat["mission_id"],
                "research.setting_changed",
                {"enabled": body.enabled, "applies_to": "next_model_request"},
            )
            return research.chat.view(c, cid)

        return await mutate(request, change)

    @app.post("/api/chats/{cid}/library/{sid}/remove", dependencies=auth)
    async def remove(
        cid: str, sid: str, request: Request, forget_content: bool = False
    ):
        def change(c):
            chat = store.get(c, cid, "chat")
            source = store.get(c, sid, "source")
            if source["chat_id"] != cid:
                raise DomainError("Source outside this conversation", 404)
            if forget_content:
                research.library.forget(c, chat, sid)
                return research.library.view(c, chat)
            source["removed"] = True
            store.put(c, "source", source)
            store.event(
                c,
                chat["mission_id"],
                "library.source_removed",
                {"source_id": sid, "historical_versions_retained": True},
            )
            return research.library.view(c, chat)

        return await mutate(request, change)
