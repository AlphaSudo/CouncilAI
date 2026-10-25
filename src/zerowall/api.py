import asyncio
import hashlib
import hmac
import json
import secrets
import threading
import time
from contextlib import asynccontextmanager, closing
from datetime import UTC, datetime
from ipaddress import ip_address
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .artifacts import Artifacts
from .budget import Budget
from .cloud_responses import CloudJSONResponse, streamed_download
from .contracts import (
    ChallengeGroupInput,
    ChatControl,
    ChatCreate,
    ChatMessageEdit,
    ChatMessageInput,
    ConcernDisposition,
    ConcernInput,
    ContextCompactionInput,
    ContinueRound,
    ConversationAllowanceInput,
    DecisionInput,
    ExperimentInput,
    LiveVerification,
    MissionBrief,
    ReframeInput,
    ReviewContractChange,
    ReviewDispositionInput,
    ReviewEvidenceInput,
    ReviewReassignment,
    RevisionAction,
    RoundInput,
    SessionInput,
    SharedSpendingInput,
    ThinkingPreferenceInput,
    TradeoffInput,
)
from .db import DomainError, open_store, canonical, digest, uid
from .durable_files import DurableFiles, SupabaseObjects
from .executor import Executor
from .fixtures import demo_brief
from .free_limits import DAILY_ATTEMPTS
from .hosting import PublicHealthHostMiddleware
from .provider import Provider
from .reports import export_pack
from .service import Research
from .settings import Settings
from .telemetry import log_request, request_logger


def create_app(settings=None, run_worker=None):
    settings = settings or Settings()
    run_worker = settings.role == 'combined' if run_worker is None else run_worker
    if settings.database_url and settings.role == 'web' and run_worker:
        raise ValueError('Cloud API instances must not start council workers')
    store = open_store(settings)
    objects = SupabaseObjects(settings.supabase_url, settings.supabase_key, settings.supabase_bucket) if store.remote else None
    files = DurableFiles(settings.data, store, objects)
    artifacts = Artifacts(
        settings.artifacts,
        [settings.api_key, settings.openrouter_api_key, settings.tavily_api_key, settings.director_token, settings.database_url, settings.supabase_key, *settings.direct_keys.values()],
        files=files,
    )
    budget = Budget(store, settings)
    provider = Provider(store, settings, budget, artifacts)
    research = Research(store, settings, budget, artifacts, provider)
    executor = Executor(research)
    cookie = hmac.new(
        settings.director_token.encode(),
        b"zerowall-director-session-v1",
        hashlib.sha256,
    ).hexdigest()
    export_lock = threading.Lock()
    logger = request_logger(settings.data)

    @asynccontextmanager
    async def lifespan(app):
        if settings.hosting.hosted:
            from .hosting import validate_runtime
            validate_runtime(settings, store, worker=run_worker)
        if run_worker:
            executor.start()
        yield
        if run_worker:
            executor.close()
        if store.remote:
            store.close()
            objects.close()

    app = FastAPI(
        title="ZeroWall",
        default_response_class=CloudJSONResponse if store.remote else JSONResponse,
        version="1.5.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.research = research
    app.state.executor = executor
    app.add_middleware(
        PublicHealthHostMiddleware, allowed_hosts=settings.hosting.allowed_hosts,
        hosted=settings.hosting.hosted,
    )

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse({"detail": exc.message}, status_code=exc.code)

    @app.middleware("http")
    async def local_boundary(request, call_next):
        request.state.correlation_id = uid("request")
        started = time.perf_counter()
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            same_origin = settings.hosting.public_origin if settings.hosting.hosted else request.url.scheme + "://" + request.headers.get("host", "")
            allowed_origins = (same_origin,) if settings.hosting.hosted else (
                same_origin, "http://127.0.0.1:5173", "http://localhost:5173"
            )
            if origin and origin not in allowed_origins:
                return JSONResponse(
                    {"detail": "Cross-origin control requests are refused"}, 403
                )
            if request.headers.get("X-ZeroWall-Director") != "1":
                return JSONResponse({"detail": "Director request header required"}, 403)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.correlation_id
        route = getattr(request.scope.get("route"), "path", "static")
        log_request(
            logger,
            request.state.correlation_id,
            request.method,
            route,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    def has_session(request: Request):
        return secrets.compare_digest(request.cookies.get("zw_session", "").encode(), cookie.encode())

    def director(request: Request):
        if not has_session(request):
            raise DomainError(
                "Open with 'zerowall open' or enter your local director token", 401
            )

    async def mutate(request, action):
        key = request.headers.get("Idempotency-Key")
        if not key or len(key) > 180:
            raise DomainError("An Idempotency-Key is required", 400)
        payload = await request.body()
        identity = request.url.path + ('?' + request.url.query if request.url.query else '')
        hashed = hashlib.sha256(identity.encode() + payload).hexdigest()
        with store.tx() as c:
            previous = c.execute(
                "SELECT * FROM idempotency WHERE key=?", (key,)
            ).fetchone()
            if previous:
                if previous["request_hash"] != hashed:
                    raise DomainError(
                        "Idempotency key was reused for a different request"
                    )
                return json.loads(previous["response"])
            result = action(c)
            if isinstance(result, dict) and result.get("mission_id"):
                store.event(
                    c,
                    result["mission_id"],
                    "director.action",
                    {
                        "request_id": request.state.correlation_id,
                        "route": getattr(request.scope.get("route"), "path", "control"),
                        "idempotency_hash": hashlib.sha256(key.encode()).hexdigest(),
                    },
                )
            c.execute(
                "INSERT INTO idempotency VALUES(?,?,?)",
                (key, hashed, canonical(result)),
            )
            return result

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "1.5.0", "provider_calls_on_startup": False}

    @app.get("/api/ready")
    def ready():
        worker_ok = not run_worker or bool(executor.thread and executor.thread.is_alive() and not executor.stop.is_set())
        if not worker_ok or not (settings.frontend / "index.html").is_file():
            return JSONResponse({"status": "not_ready"}, status_code=503)
        # Health checks never refresh prices, call providers or mutate the ledger.
        import sqlite3
        try:
            if store.remote:
                store.healthy()
            else:
                with closing(sqlite3.connect(Path(store.path).resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as connection:
                    connection.execute("SELECT 1 FROM schema_version LIMIT 1").fetchone()
        except sqlite3.Error:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return {"status": "ready"}

    @app.get("/api/session")
    def session_status(request: Request):
        return {
            "authenticated": has_session(request),
            "local_entry": not settings.hosting.hosted,
        }

    operations_cache, operations_lock = {}, threading.Lock()

    @app.get('/api/operations/status')
    def operations_status():
        from .cloud_operations import snapshot
        # A public status check reveals no history, keys or spending amounts.
        with operations_lock:
            if time.monotonic() >= operations_cache.get('expires', 0):
                operations_cache.update(
                    body=snapshot(store, (settings.frontend / 'index.html').is_file()),
                    expires=time.monotonic() + 30,
                )
            body = operations_cache['body']
        return JSONResponse(body, status_code=200 if body['status'] == 'ready' else 503,
                            headers={'Cache-Control': 'no-store'})

    def session_response():
        response = JSONResponse({"authenticated": True})
        response.set_cookie(
            "zw_session",
            cookie,
            httponly=True,
            samesite="strict",
            secure=settings.cookie_secure,
            max_age=43200,
        )
        return response

    @app.post("/api/session/local")
    def local_session(request: Request):
        if settings.hosting.hosted:
            raise DomainError("Enter the access code for this hosted council", 403)
        try:
            loopback = (
                bool(request.client) and ip_address(request.client.host).is_loopback
            )
        except ValueError:
            loopback = False
        if not loopback or request.headers.get("sec-fetch-site") not in (
            None,
            "same-origin",
            "same-site",
            "none",
        ):
            raise DomainError(
                "Direct entry is available only from this local workspace", 403
            )
        return session_response()

    @app.post("/api/session")
    def session(body: SessionInput):
        if not secrets.compare_digest(body.token.encode(), settings.director_token.encode()):
            raise DomainError("Invalid access code" if settings.hosting.hosted else "Invalid local director token", 401)
        return session_response()

    @app.post("/api/logout", dependencies=[Depends(director)])
    def logout():
        response = JSONResponse({"authenticated": False})
        response.delete_cookie("zw_session")
        return response

    auth = [Depends(director)]

    @app.get("/api/bootstrap", dependencies=auth)
    def bootstrap():
        with store.tx() as c:
            v = store.setting(c, "live_verification", {})
            return {
                "missions": [
                    json.loads(r[0])
                    for r in c.execute(
                        "SELECT body FROM records WHERE kind='mission' AND COALESCE(json_extract(body,'$.surface'),'research')!='chat' ORDER BY rowid DESC"
                    )
                ],
                "models": settings.models,
                "optional_models": settings.policy["optional_models"],
                "key_present": bool(settings.api_key),
                "budget": budget.summary(c),
                "live_verification": {
                    k: v[k]
                    for k in (
                        "id",
                        "expires_at",
                        "catalog_model_ids",
                        "operational_cap_usd",
                        "authorization_mode",
                        "account_payment_settings_verified",
                    )
                    if k in v
                },
                "live_ready": bool(
                    settings.api_key
                    and v
                    and datetime.fromisoformat(v["expires_at"])
                    > datetime.now(UTC)
                    and budget.funding_confirmed(c, v)
                    and all(
                        v.get(k)
                        for k in (
                            "credit_only_confirmed",
                            "all_billing_categories_bounded",
                            "token_bound_verified",
                        )
                    )
                ),
                "demo_brief": demo_brief(),
                "openrouter_free": {
                    "enabled": settings.openrouter_enabled,
                    "key_present": settings.openrouter_enabled
                    and bool(settings.openrouter_api_key),
                    "ready": settings.openrouter_enabled
                    and bool(settings.openrouter_api_key)
                    and not store.setting(c, "openrouter_free_locked", False),
                    "model": research.free_provider.model,
                    "attempt_cap": 12,
                    "daily_attempt_cap": DAILY_ATTEMPTS,
                },
            }

    @app.post("/api/missions", dependencies=auth)
    async def create(request: Request, body: MissionBrief):
        return await mutate(request, lambda c: research.create_mission(c, body))

    @app.get("/api/chats/bootstrap", dependencies=auth)
    def chat_bootstrap():
        from .token_factory_prices import refresh_prices
        refresh_prices(research)
        with store.tx() as c:
            return research.chat.bootstrap(c)

    @app.post("/api/chats/token-factory/refresh", dependencies=auth)
    def chat_refresh_token_factory():
        from .token_factory_prices import refresh_prices
        refresh_prices(research, force=True)
        with store.tx() as c:
            return research.chat.bootstrap(c)

    @app.post("/api/chats", dependencies=auth)
    async def chat_create(request: Request, body: ChatCreate):
        if body.provider == "nebius_token_factory":
            from .token_factory_prices import refresh_prices
            await run_in_threadpool(refresh_prices, research)
        with store.tx() as c:
            replay = c.execute(
                "SELECT 1 FROM idempotency WHERE key=?",
                (request.headers.get("Idempotency-Key"),),
            ).fetchone()
        if body.provider == "openrouter_free" and not replay:
            if not settings.openrouter_enabled:
                raise DomainError("OpenRouter is disabled for new councils.", 412)
            await run_in_threadpool(
                research.free_provider.check_account,
                required=2 * len(body.models) + 7
                if body.mode == "reviewed"
                else len(body.models) * (1 + body.max_rounds) + 1,
            )
        return await mutate(request, lambda c: research.chat.create(c, body))

    @app.get("/api/chats/preview", dependencies=auth)
    def chat_preview(provider: str, models: str, mode: str = "reviewed", max_rounds: int = 1, review_protocol: str | None = None, search_web: bool | None = None, research_tools: bool = False):
        if provider == "nebius_token_factory":
            from .token_factory_prices import refresh_prices
            refresh_prices(research)
        try:
            body = ChatCreate(
                prompt="Preview the proposed council",
                provider=provider,
                mode=mode,
                models=models.split(","),
                max_rounds=max_rounds,
                search_web=search_web,
                research_tools=research_tools,
                **({"review_protocol": review_protocol} if review_protocol else {}),
            )
        except ValueError:
            raise DomainError("Invalid council preview configuration", 422)
        with store.tx() as c:
            return research.chat.preview(c, body)

    @app.get("/api/chats/availability", dependencies=auth)
    def chat_availability():
        if not settings.openrouter_enabled or not settings.openrouter_api_key:
            return {"known": False, "remaining": None, "limit": None}
        try:
            return research.free_provider.account_status(force=True)
        except DomainError as exc:
            return {
                "known": False,
                "remaining": None,
                "limit": None,
                "error": exc.message,
            }

    @app.get("/api/chats/{cid}", dependencies=auth)
    def chat_view(cid: str):
        with store.tx() as c:
            return research.chat.view(c, cid)

    @app.get("/api/chats/{cid}/messages/{mid}/original", dependencies=auth)
    def original_model_response(cid: str, mid: str):
        from .response_presentation import original_reply
        with store.tx() as c:
            return original_reply(research.chat, c, cid, mid)

    @app.get("/api/chats/{cid}/streams/{call_id}", dependencies=auth)
    def chat_public_stream(cid: str, call_id: str, after: int = 0, limit: int = 64):
        if after < 0 or not 1 <= limit <= 64:
            raise DomainError("Invalid public replay cursor or page size", 400)
        with store.tx() as c:
            chat = store.get(c, cid, "chat")
            call = store.get(c, call_id, "call")
            if call["mission_id"] != chat["mission_id"] or not call.get("purpose", "").startswith(f"chat:{cid}:"):
                raise DomainError("Public stream does not belong to this council", 404)
            stream = store.get(c, "public_stream_" + call_id, "public_stream")
            chunks = [chunk for chunk in stream["chunks"] if chunk["seq"] > after][:limit]
            cursor = chunks[-1]["seq"] if chunks else after
            return {"call_id": call_id, "model": stream["model"], "chunks": chunks, "next_seq": cursor,
                    "complete": stream["complete"] and cursor >= len(stream["chunks"]), "total_chunks": len(stream["chunks"])}

    @app.post("/api/chats/{cid}/messages", dependencies=auth)
    async def chat_message(cid: str, request: Request, body: ChatMessageInput):
        from .token_factory_prices import refresh_prices
        await run_in_threadpool(refresh_prices, research)
        return await mutate(request, lambda c: research.chat.add_message(c, cid, body))

    @app.post("/api/chats/{cid}/control", dependencies=auth)
    async def chat_control(cid: str, request: Request, body: ChatControl):
        from .token_factory_prices import refresh_prices
        await run_in_threadpool(refresh_prices, research)
        return await mutate(request, lambda c: research.chat.control(c, cid, body))

    @app.post("/api/chats/{cid}/messages/{mid}/regenerate", dependencies=auth)
    async def chat_message_edit(cid: str, mid: str, request: Request, body: ChatMessageEdit):
        from .token_factory_prices import refresh_prices
        await run_in_threadpool(refresh_prices, research)
        return await mutate(request, lambda c: research.chat.edit_message(c, cid, mid, body))

    @app.post("/api/chats/{cid}/context/compact", dependencies=auth)
    async def chat_context_compact(cid: str, request: Request, body: ContextCompactionInput):
        return await mutate(request, lambda c: research.context_compaction.request(c, cid, body))

    @app.post("/api/chats/{cid}/thinking", dependencies=auth)
    async def chat_thinking(cid: str, request: Request, body: ThinkingPreferenceInput):
        return await mutate(request, lambda c: research.council_preferences.set_thinking(c, cid, body))

    @app.post("/api/chats/{cid}/allowance", dependencies=auth)
    async def chat_allowance(cid: str, request: Request, body: ConversationAllowanceInput):
        return await mutate(request, lambda c: research.council_preferences.add_allowance(c, cid, body))

    @app.post("/api/chats/{cid}/spending", dependencies=auth)
    async def chat_spending(cid: str, request: Request, body: SharedSpendingInput):
        return await mutate(request, lambda c: research.council_preferences.share_cap(c, cid))

    @app.get("/api/chats/{cid}/review", dependencies=auth)
    def chat_review(cid: str):
        with store.tx() as c:
            chat = store.get(c, cid, "chat")
            if chat.get("mode") != "reviewed":
                raise DomainError("This is an ordinary discussion", 422)
            return research.chat.review.snapshot(c, chat)

    @app.post("/api/chats/{cid}/review/evidence", dependencies=auth)
    async def review_evidence(cid: str, request: Request, body: ReviewEvidenceInput):
        return await mutate(
            request, lambda c: research.chat.review.evidence(c, cid, body)
        )

    @app.post("/api/chats/{cid}/review/dispositions", dependencies=auth)
    async def review_disposition(
        cid: str, request: Request, body: ReviewDispositionInput
    ):
        return await mutate(
            request, lambda c: research.chat.review.disposition(c, cid, body)
        )

    @app.post("/api/chats/{cid}/review/reassignments", dependencies=auth)
    async def review_reassign(cid: str, request: Request, body: ReviewReassignment):
        return await mutate(
            request, lambda c: research.chat.review.reassign(c, cid, body)
        )

    @app.post("/api/chats/{cid}/review/contracts", dependencies=auth)
    async def review_contract(cid: str, request: Request, body: ReviewContractChange):
        def change(c):
            chat, _ = research.chat.review.governed(c, cid, body.expected_revision)
            return research.chat.review.new_cycle(
                c, chat, body.question, body.options, body.expected_revision
            )

        return await mutate(request, change)

    @app.post("/api/chats/{cid}/review/resynthesize", dependencies=auth)
    async def review_resynthesize(cid: str, request: Request, body: RevisionAction):
        return await mutate(
            request,
            lambda c: research.chat.review.resynthesize(c, cid, body.expected_revision),
        )

    @app.post("/api/chats/{cid}/review/exports", dependencies=auth)
    async def review_export(cid: str, request: Request, include_source_content: bool = True):
        from .review_exports import export_review

        def create_export(c):
            chat = store.get(c, cid, "chat")
            if chat.get("mode") != "reviewed":
                raise DomainError("This conversation has no review ledger", 422)
            eid = uid("review_export")
            folder = settings.data / "review-exports"
            folder.mkdir(exist_ok=True)
            data = export_review(research, c, chat, include_source_content)
            files.write('review-exports/' + eid + '.zip', data)
            item = {
                "id": eid,
                "mission_id": chat["mission_id"],
                "chat_id": cid,
                "sha256": hashlib.sha256(data).hexdigest(),
                "download": f"/api/chats/{cid}/review/exports/{eid}",
            }
            store.put(c, "review_export", item)
            return item

        return await mutate(request, create_export)

    @app.get("/api/chats/{cid}/review/exports/{eid}", dependencies=auth)
    def review_download(cid: str, eid: str):
        with store.tx() as c:
            item = store.get(c, eid, "review_export")
            if item["chat_id"] != cid:
                raise DomainError("Export belongs to another conversation", 422)
            path = files.materialize('review-exports/' + item['id'] + '.zip', item['sha256'])
            if store.remote:
                return streamed_download(path, 'zerowall-review-' + cid + '.zip')
            return FileResponse(
                path,
                media_type="application/zip",
                filename="zerowall-review-" + cid + ".zip",
            )

    @app.patch("/api/missions/{mid}/draft", dependencies=auth)
    async def draft(
        mid: str, request: Request, body: MissionBrief, expected_revision: int
    ):
        return await mutate(
            request, lambda c: research.draft(c, mid, expected_revision, body)
        )

    @app.post("/api/missions/{mid}/freeze", dependencies=auth)
    async def freeze(mid: str, request: Request, body: RevisionAction):
        return await mutate(
            request, lambda c: research.freeze(c, mid, body.expected_revision)
        )

    @app.get("/api/missions/{mid}", dependencies=auth)
    def mission(mid: str):
        with store.tx() as c:
            return research.view(c, mid)

    @app.get("/api/missions/{mid}/steps", dependencies=auth)
    def steps(mid: str):
        with store.tx() as c:
            store.get(c, mid, "mission")
            return store.list(c, "step", mid)

    @app.get("/api/missions/{mid}/budget", dependencies=auth)
    def mission_budget(mid: str):
        with store.tx() as c:
            store.get(c, mid, "mission")
            return research.budget_summary(c, mid)

    @app.post("/api/steps/{sid}/rounds", dependencies=auth)
    async def round_start(sid: str, request: Request, body: RoundInput):
        return await mutate(request, lambda c: research.round(c, sid, body))

    @app.get("/api/rounds/{rid}", dependencies=auth)
    def round_get(rid: str):
        with store.tx() as c:
            return research.public_round(c, store.get(c, rid, "round"))

    @app.post("/api/rounds/{rid}/reveal", dependencies=auth)
    async def reveal(rid: str, request: Request, body: RevisionAction):
        return await mutate(
            request, lambda c: research.reveal(c, rid, body.expected_revision)
        )

    @app.post("/api/rounds/{rid}/review", dependencies=auth)
    async def cross_review(rid: str, request: Request, body: RevisionAction):
        return await mutate(
            request, lambda c: research.review(c, rid, body.expected_revision)
        )

    @app.post("/api/rounds/{rid}/continue", dependencies=auth)
    async def continue_round(rid: str, request: Request, body: ContinueRound):
        return await mutate(request, lambda c: research.continue_round(c, rid, body))

    @app.post("/api/rounds/{rid}/cancel", dependencies=auth)
    async def cancel_round(rid: str, request: Request, body: RevisionAction):
        return await mutate(
            request, lambda c: research.cancel_round(c, rid, body.expected_revision)
        )

    @app.post("/api/steps/{sid}/concerns", dependencies=auth)
    async def concern(sid: str, request: Request, body: ConcernInput):
        return await mutate(request, lambda c: research.concern(c, sid, body))

    @app.post("/api/concerns/{cid}/resolve", dependencies=auth)
    async def resolve(cid: str, request: Request, body: ConcernDisposition):
        return await mutate(request, lambda c: research.disposition(c, cid, body))

    @app.post("/api/steps/{sid}/control/{verb}", dependencies=auth)
    async def control(sid: str, verb: str, request: Request, body: RevisionAction):
        return await mutate(
            request, lambda c: research.intervene(c, sid, verb, body.expected_revision)
        )

    @app.post("/api/steps/{sid}/experiments", dependencies=auth)
    async def experiment(sid: str, request: Request, body: ExperimentInput):
        return await mutate(request, lambda c: research.experiment(c, sid, body))

    @app.post("/api/experiments/{eid}/approve", dependencies=auth)
    async def approve_experiment(eid: str, request: Request, body: RevisionAction):
        return await mutate(
            request,
            lambda c: research.approve_experiment(c, eid, body.expected_revision),
        )

    @app.post("/api/experiments/{eid}/cancel", dependencies=auth)
    async def cancel_experiment(eid: str, request: Request, body: RevisionAction):
        return await mutate(
            request,
            lambda c: research.cancel_experiment(c, eid, body.expected_revision),
        )

    @app.get("/api/experiments/{eid}/runs", dependencies=auth)
    def runs(eid: str):
        with store.tx() as c:
            e = store.get(c, eid, "experiment")
            return [
                r
                for r in store.list(c, "run", e["mission_id"])
                if r["experiment_id"] == eid
            ]

    @app.get("/api/experiments/{eid}/evidence", dependencies=auth)
    def evidence(eid: str):
        with store.tx() as c:
            e = store.get(c, eid, "experiment")
            return [
                r
                for r in store.list(c, "evidence", e["mission_id"])
                if r["experiment_id"] == eid
            ]

    @app.post("/api/steps/{sid}/tradeoffs", dependencies=auth)
    async def tradeoff(sid: str, request: Request, body: TradeoffInput):
        return await mutate(request, lambda c: research.tradeoff(c, sid, body))

    @app.post("/api/steps/{sid}/challenge-groups", dependencies=auth)
    async def challenge_group(sid: str, request: Request, body: ChallengeGroupInput):
        return await mutate(request, lambda c: research.challenge_group(c, sid, body))

    @app.get("/api/steps/{sid}/related-hypotheses", dependencies=auth)
    def related(sid: str):
        from .memory import suggestions

        with store.tx() as c:
            s = store.get(c, sid, "step")
            return suggestions(
                [
                    h
                    for h in store.list(c, "hypothesis", s["mission_id"])
                    if h["step_id"] == sid
                ]
            )

    @app.get("/api/missions/{mid}/negative-results", dependencies=auth)
    def negative_results(mid: str):
        with store.tx() as c:
            store.get(c, mid, "mission")
            hypotheses = [
                h
                for h in store.list(c, "hypothesis", mid)
                if h["status"] in ("falsified", "blocked", "superseded")
            ]
            experiments = store.list(c, "experiment", mid)
            return [
                {
                    "hypothesis": h,
                    "experiments": [
                        e for e in experiments if h["id"] in e["hypothesis_ids"]
                    ],
                }
                for h in hypotheses
            ]

    @app.post("/api/steps/{sid}/reframes", dependencies=auth)
    async def reframe(sid: str, request: Request, body: ReframeInput):
        return await mutate(request, lambda c: research.reframe(c, sid, body))

    @app.post("/api/steps/{sid}/decisions", dependencies=auth)
    async def decision(sid: str, request: Request, body: DecisionInput):
        return await mutate(request, lambda c: research.decision(c, sid, body))

    @app.post("/api/decisions/{did}/approve", dependencies=auth)
    async def approve_decision(did: str, request: Request, body: RevisionAction):
        return await mutate(
            request, lambda c: research.approve_decision(c, did, body.expected_revision)
        )

    @app.get("/api/artifacts/{aid}", dependencies=auth)
    def artifact(aid: str):
        with store.tx() as c:
            a = store.get(c, aid, "artifact")
            if not research.artifact_visible(c, a):
                raise DomainError("This artifact is private until atomic reveal", 403)
            return artifacts.read(a)

    @app.get("/api/missions/{mid}/events", dependencies=auth)
    async def events(mid: str, request: Request, after: int = 0):
        with store.tx() as c:
            store.get(c, mid, "mission")
        try:
            last = max(after, int(request.headers.get("last-event-id", "0")))
        except ValueError:
            raise DomainError("Invalid event cursor", 400)

        async def stream():
            nonlocal last
            deadline = time.monotonic() + 240 if store.remote else float('inf')
            # End before the hosted request ceiling. EventSource reconnects with
            # Last-Event-ID; the durable daemon continues independently.
            while time.monotonic() < deadline and not await request.is_disconnected():
                with store.tx() as c:
                    rows = [
                        dict(r)
                        for r in c.execute(
                            "SELECT * FROM events WHERE mission_id=? AND seq>? ORDER BY seq LIMIT 100",
                            (mid, last),
                        )
                    ]
                for row in rows:
                    last = row["seq"]
                    yield f"id: {last}\nevent: research\ndata: {canonical(row)}\n\n"
                if not rows:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )

    @app.post("/api/missions/{mid}/exports", dependencies=auth)
    async def export(mid: str, request: Request):
        # Export is read-snapshot work; deterministic idempotency is serialized outside the DB transaction.
        key = request.headers.get("Idempotency-Key")
        if not key:
            raise DomainError("Idempotency-Key required", 400)
        hashed = digest({"export": mid})
        with export_lock, store.operation_lock('export:' + key):
            with store.tx() as c:
                old = c.execute(
                    "SELECT * FROM idempotency WHERE key=?", (key,)
                ).fetchone()
                if old:
                    if old["request_hash"] != hashed:
                        raise DomainError("Idempotency key conflict")
                    return json.loads(old["response"])
            result = export_pack(research, mid)
            with store.tx() as c:
                c.execute(
                    "INSERT INTO idempotency VALUES(?,?,?)",
                    (key, hashed, canonical(result)),
                )
            return result

    @app.get("/api/exports/{eid}/download", dependencies=auth)
    def download(eid: str):
        with store.tx() as c:
            e = store.get(c, eid, "export")
        path = files.materialize('exports/' + e['filename'], e['sha256'])
        if store.remote:
            return streamed_download(path, 'zerowall-' + e['id'] + '.zip')
        return FileResponse(
            path, media_type="application/zip", filename="zerowall-" + e["id"] + ".zip"
        )

    @app.post("/api/settings/live-verification", dependencies=auth)
    async def verification(request: Request, body: LiveVerification):
        return await mutate(request, lambda c: research.verify_live(c, body))

    @app.delete("/api/settings/live-verification", dependencies=auth)
    async def lock_live(request: Request):
        def action(c):
            store.set_setting(c, "live_verification", {})
            return {"live_enabled": False}

        return await mutate(request, action)

    @app.post("/api/settings/catalog", dependencies=auth)
    def catalog():
        if not settings.api_key:
            raise DomainError("NEBIUS_API_KEY missing", 412)
        try:
            with httpx.Client(timeout=15, follow_redirects=False) as client:
                r = client.get(
                    settings.base_url + "/models",
                    headers={"Authorization": "Bearer " + settings.api_key},
                )
            if not r.is_success:
                raise DomainError(f"Catalog HTTP {r.status_code}", 502)
            ids = [m["id"] for m in r.json().get("data", [])]
            return {
                "enabled_models": [
                    {"id": m, "available": m in ids} for m in settings.models
                ],
                "inference_dispatched": False,
            }
        except (httpx.HTTPError, ValueError, KeyError):
            raise DomainError("Catalog check failed; no inference dispatched", 502)

    from .research_api import install as install_research_api
    install_research_api(app, research, auth, mutate)
    if settings.frontend.exists():
        app.mount("/", StaticFiles(directory=settings.frontend, html=True), name="web")
    return app
