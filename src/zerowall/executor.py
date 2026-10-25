"""One durable local executor. Interrupted network work is never automatically replayed."""

import json
import platform
import threading
import time
from datetime import UTC, datetime

from pydantic import ValidationError

from .analysis import calculate_bound, compare_trials, evaluate_rubric
from .benchmark import run_benchmark
from .contracts import CrossReview, Submission
from .db import DomainError, digest, now, uid
from .fixtures import review, submission
from .process_lock import ProcessLock
from .provider import parse_json
from .service import validate_plan


class Executor:
    def __init__(self, research):
        self.research = research
        self.store = research.store
        self.settings = research.settings
        self.stop = threading.Event()
        self.draining = threading.Event()
        self.thread = None
        if self.store.remote:
            from .postgres import WorkerLock
            self.ownership = WorkerLock(self.store)
        else:
            self.ownership = ProcessLock(self.settings.data / "executor.lock")
        self.mirror = None
        self.last_owner_check = 0
        self.owner_ok = True
        self.busy = threading.Event()
        self.next_wakeup = None

    def start(self):
        self.ownership.acquire()
        try:
            self.store.recover()
            self.research.tools.policy.recover()
            from .answer_delivery import AnswerDelivery
            AnswerDelivery(self.research.chat).reconcile()
        except BaseException:
            self.ownership.release()
            raise

        def owned_loop():
            try:
                self.loop()
            finally:
                self.ownership.release()

        self.thread = threading.Thread(
            target=owned_loop, daemon=True, name="zerowall-executor"
        )
        self.thread.start()
        if self.store.remote:
            from .durable_files import FileMirror
            self.mirror = FileMirror(self.research.artifacts.files)
            self.mirror.start()

    def close(self):
        self.stop.set()
        self.wake()
        if self.thread:
            self.thread.join(timeout=2)
        if self.mirror:
            self.mirror.close()

    def wake(self):
        if self.store.remote and self.thread and self.thread.is_alive():
            try:
                self.ownership.wake()
            except DomainError:
                pass  # Reconciliation remains bounded if the database is down.

    def drain(self):
        self.draining.set()
        self.wake()

    def ownership_lost(self):
        if not self.store.remote:
            return False
        if self.ownership.disconnected:
            return True
        if time.monotonic() - self.last_owner_check >= 1:
            self.owner_ok = self.ownership.healthy()
            self.last_owner_check = time.monotonic()
        return not self.owner_ok

    def loop(self):
        idle = 0.25
        while not self.stop.is_set() and not self.draining.is_set():
            try:
                if not self.run_once():
                    if self.store.remote:
                        timeout = 60
                        if self.next_wakeup:
                            timeout = min(timeout, max(0.05, (self.next_wakeup - datetime.now(UTC)).total_seconds()))
                        channel = self.ownership.wait(timeout=timeout)
                        if channel == 'zerowall_files' and self.mirror:
                            self.mirror.wake()
                    else:
                        self.stop.wait(idle)
                else:
                    idle = 0.25
                    if self.mirror:
                        self.mirror.wake()
            except Exception:  # noqa: BLE001 - durable worker boundary; never log provider content
                # Do not log exception bodies that could contain provider content or credentials.
                self.stop.wait(0.5)

    def claim(self):
        self.next_wakeup = None
        if self.draining.is_set() or self.ownership_lost():
            return None
        with self.store.tx() as c:
            for row in c.execute(
                "SELECT * FROM jobs WHERE state='queued' ORDER BY created_at"
            ).fetchall():
                record = self.store.get(
                    c,
                    row["target_id"],
                    "chat"
                    if row["kind"] == "chat"
                    else "round"
                    if row["kind"] in ("round", "review")
                    else "experiment",
                )
                if row["kind"] == "chat" and record["status"] not in (
                    "running",
                    "waiting",
                ):
                    continue
                if row["kind"] == "chat":
                    not_before = json.loads(row["body"]).get("not_before")
                    if not_before and not_before > now():
                        due = datetime.fromisoformat(not_before)
                        self.next_wakeup = min(self.next_wakeup, due) if self.next_wakeup else due
                        continue
                step = self.store.get(c, record["step_id"], "step")
                if step["paused"]:
                    continue
                if step["stale"] or step["revision"] != record["step_revision"]:
                    c.execute(
                        "UPDATE jobs SET state='cancelled' WHERE id=?", (row["id"],)
                    )
                    continue
                c.execute("UPDATE jobs SET state='running' WHERE id=?", (row["id"],))
                if row["kind"] == "chat" and record["status"] == "waiting":
                    record.update(status="running", retry_wait=None)
                    self.store.put(c, "chat", record)
                    self.store.event(
                        c,
                        row["mission_id"],
                        "chat.retry_started",
                        {"chat_id": record["id"]},
                    )
                return dict(row)
        return None

    def cancelled(self, record):
        if self.stop.is_set() or self.ownership_lost():
            return True
        with self.store.tx() as c:
            s = self.store.get(c, record["step_id"], "step")
            target = self.store.get(c, record["id"])
            return (
                s["paused"]
                or s["stale"]
                or s["revision"] != record["step_revision"]
                or target["status"] == "cancelled"
            )

    def run_once(self):
        job = self.claim()
        if not job:
            return False
        self.busy.set()
        try:
            return self.run_claimed(job)
        finally:
            self.busy.clear()

    def run_claimed(self, job):
        try:
            if job["kind"] == "chat":
                self.research.chat.run_turn(job, lambda: self.stop.is_set() or self.ownership_lost())
            elif job["kind"] in ("round", "review"):
                self.council(job, job["kind"] == "review")
            else:
                self.experiment(job)
            with self.store.tx() as c:
                c.execute(
                    "UPDATE jobs SET state='completed' WHERE id=? AND state='running'",
                    (job["id"],),
                )
        except Exception as exc:  # noqa: BLE001 - persist every job failure with a redacted public error
            if job["kind"] == "chat" and self.research.chat.handle_failure(job, exc):
                return True
            message = (
                exc.message
                if isinstance(exc, DomainError)
                else "Validation failed"
                if isinstance(exc, (ValueError, ValidationError))
                else f"Local execution failed ({type(exc).__name__})"
            )
            with self.store.tx() as c:
                c.execute(
                    "UPDATE jobs SET state='failed',body=? WHERE id=?",
                    (json.dumps({"error": message}), job["id"]),
                )
                kind = (
                    "chat"
                    if job["kind"] == "chat"
                    else "round"
                    if job["kind"] in ("round", "review")
                    else "experiment"
                )
                record = self.store.get(c, job["target_id"], kind)
                if kind == "chat" and (record.get("active_turn") or {}).get("job_id") in (None, job["id"]):
                    record["active_turn"] = None
                if record["status"] != "cancelled" and not (
                    kind == "chat" and record["status"] == "paused"
                ):
                    record.update(status="failed", error=message)
                    if kind == "chat":
                        record["active_turn"] = None
                self.store.put(c, kind, record)
                if kind == "chat" and record["status"] in ("failed", "cancelled"):
                    self.research.chat.runtime.release_capacity(c, record["mission_id"], record["status"])
                for run in self.store.list(c, "run", job["mission_id"]):
                    if run.get("job_id") == job["id"] and run["state"] == "running":
                        run.update(state="failed", error=message, completed_at=now())
                        self.store.put(c, "run", run)
                step = self.store.get(c, record["step_id"], "step")
                if (
                    step["revision"] == record["step_revision"]
                    and record["status"] != "cancelled"
                    and record["status"] != "paused"
                ):
                    step["status"] = "blocked"
                    self.store.put(c, "step", step)
                self.store.event(
                    c,
                    job["mission_id"],
                    "job.failed",
                    {"job_id": job["id"], "error": message},
                )
        return True

    def council(self, job, is_review):
        with self.store.tx() as c:
            r = self.store.get(c, job["target_id"], "round")
            provider = self.research.provider_for(c, r["mission_id"])
            r["status"] = "reviewing" if is_review else "committing"
            r["active_phase"] = "review" if is_review else "round"
            self.store.put(c, "round", r)
            hypotheses = [
                h
                for h in self.store.list(c, "hypothesis", r["mission_id"])
                if h["round_id"] == r["id"]
            ]
            concerns = r["context"]["concerns"]
            revealed = (
                [
                    s
                    for s in self.store.list(c, "submission", r["mission_id"])
                    if s["round_id"] == r["id"]
                ]
                if is_review
                else []
            )
            completed = {
                item["seat"]
                for item in self.store.list(
                    c, "review" if is_review else "submission", r["mission_id"]
                )
                if item["round_id"] == r["id"]
                and (not is_review or item.get("review_pass", 1) == r["review_passes"])
            }
        for seat in r["seats"]:
            if seat["id"] in completed:
                continue
            if self.cancelled(r):
                raise DomainError(
                    "Round stopped; its context is paused, changed or cancelled"
                )
            payload = {
                "role": seat["role"],
                "shared_context": r["context"],
                "instructions": "Challenge mechanisms and controls. Preserve dissent. Return concise JSON matching this schema.",
                "output_schema": (
                    CrossReview if is_review else Submission
                ).model_json_schema(),
            }
            if is_review:
                payload.update(revealed_submissions=revealed, hypotheses=hypotheses)
            prompt = json.dumps(payload, ensure_ascii=False)
            if r["mode"] == "fixture":
                content = (
                    review(hypotheses, concerns)
                    if is_review
                    else submission(
                        seat["id"],
                        [s["id"] for s in r["context"]["mission"]["sources"]],
                    )
                )
                call_id = None
                time.sleep(0.05)
            else:
                text, call = provider.call(
                    r["mission_id"],
                    prompt,
                    2048,
                    model=seat["model"],
                    purpose=f"round:{r['id']}:{'review' if is_review else 'commit'}:{seat['id']}",
                    cancelled=lambda: self.cancelled(r),
                )
                content = parse_json(text)
                call_id = call["id"]
            content = (
                (CrossReview if is_review else Submission)
                .model_validate(content)
                .model_dump()
            )
            if is_review:
                if not set(content["challenged_hypothesis_ids"]) <= {
                    h["id"] for h in hypotheses
                }:
                    raise ValueError("Unknown hypothesis reference")
                if set(content["concern_responses"]) != {x["id"] for x in concerns}:
                    raise ValueError("Every current concern requires a response")
            elif not set(content["source_ids"]) <= {
                s["id"] for s in r["context"]["mission"]["sources"]
            }:
                raise ValueError("Unknown source ID")
            with self.store.tx() as c:
                artifact = self.research.artifacts.write(
                    r["mission_id"],
                    "review" if is_review else "private_submission",
                    {
                        "context_hash": r["context"]["hash"],
                        "seat": seat["id"],
                        "model": seat["model"],
                        "mode": r["mode"],
                        "provider": r.get("provider", "nebius_token_factory"),
                        "prompt": payload,
                        "content": content,
                        "call_id": call_id,
                    },
                )
                artifact["private_round_id"] = r["id"]
                self.store.put(c, "artifact", artifact)
                item = {
                    "id": uid("review" if is_review else "submission"),
                    "mission_id": r["mission_id"],
                    "round_id": r["id"],
                    "seat": seat["id"],
                    "model": seat["model"],
                    "mode": r["mode"],
                    "provider": r.get("provider", "nebius_token_factory"),
                    "content": content,
                    "context_hash": r["context"]["hash"],
                    "commitment": digest(content),
                    "artifact_id": artifact["id"],
                    "call_id": call_id,
                }
                if is_review:
                    item["review_pass"] = r["review_passes"]
                self.store.put(c, "review" if is_review else "submission", item)
                current = self.store.get(c, r["id"], "round")
                for s in current["seats"]:
                    if s["id"] == seat["id"]:
                        s["state"] = "reviewed" if is_review else "committed"
                        s["commitment"] = item["commitment"]
                self.store.put(c, "round", current)
                self.store.event(
                    c,
                    r["mission_id"],
                    "seat.reviewed" if is_review else "seat.committed",
                    {
                        "round_id": r["id"],
                        "seat": seat["id"],
                        "commitment": item["commitment"],
                    },
                )
        with self.store.tx() as c:
            current = self.store.get(c, r["id"], "round")
            step = self.store.get(c, r["step_id"], "step")
            stale = step["revision"] != r["step_revision"]
            was_cancelled = current["status"] == "cancelled"
            current["status"] = (
                "cancelled"
                if was_cancelled
                else "stale"
                if stale
                else "reviewed"
                if is_review
                else "committed"
            )
            if is_review and not stale and not was_cancelled:
                current["reviews_complete"] = True
                for concern in self.store.list(c, "concern", r["mission_id"]):
                    if concern["step_id"] == r["step_id"]:
                        concern["acknowledged_by"] = [s["id"] for s in r["seats"]]
                        self.store.put(c, "concern", concern)
                step["status"] = "reviewing"
                self.store.put(c, "step", step)
            self.store.put(c, "round", current)
            self.store.event(
                c,
                r["mission_id"],
                "review.completed" if is_review else "round.committed",
                {"round_id": r["id"], "stale": stale},
            )

    def experiment(self, job):
        with self.store.tx() as c:
            e = self.store.get(c, job["target_id"], "experiment")
            provider = self.research.provider_for(c, e["mission_id"])
            validate_plan(e)
            e["status"] = "running"
            self.store.put(c, "experiment", e)
            run = {
                "id": uid("run"),
                "mission_id": e["mission_id"],
                "experiment_id": e["id"],
                "job_id": job["id"],
                "attempt_id": uid("attempt"),
                "state": "running",
                "plan_hash": e["plan_hash"],
                "started_at": now(),
                "client": {
                    "python": platform.python_version(),
                    "platform": platform.system(),
                    "adapter": "single-attempt-httpx-v1",
                    "concurrency": 1,
                    "endpoint": getattr(provider, "base_url", self.settings.base_url),
                    "provider": provider.provider_id,
                    "provider_version": "unknown",
                },
            }
            run["experiment_queue_wait_ms"] = (
                datetime.fromisoformat(run["started_at"])
                - datetime.fromisoformat(e["approved_at"])
            ).total_seconds() * 1000
            self.store.put(c, "run", run)
        cancelled = lambda: self.cancelled(e)
        if cancelled():
            raise DomainError("Experiment stopped before execution")
        started = time.perf_counter()
        cap = e["capability"]
        args = e["args"]
        klass = "calculated"
        if cap == "analysis.calculate_bound":
            result = calculate_bound(args)
        elif cap == "analysis.compare_trials":
            result = compare_trials(args)
            klass = "imported"
        elif cap == "analysis.evaluate_rubric":
            result = evaluate_rubric(args)
            klass = "imported"
        elif cap == "evidence.import":
            result = {
                **args,
                "sha256": digest(args["content"]),
                "note": "External content; authenticity and scientific scope require review.",
            }
            klass = "imported"
        elif cap == "evidence.validate":
            checks = [
                {
                    "claim": x.get("claim", ""),
                    "source_id": x.get("source_id"),
                    "known_source": x.get("source_id") in args["source_ids"],
                }
                for x in args["claims"]
            ]
            result = {
                "checks": checks,
                "valid": all(x["known_source"] for x in checks),
                "scope": "Identifier coverage only; semantic support is untested.",
            }
        elif cap == "inference.validate_request":
            result = {
                "valid": True,
                "prompt_bytes": len(args["prompt"].encode()),
                "max_output_tokens": args["max_output_tokens"],
                "note": "Local syntax and bounds validation. No inference dispatched.",
            }
        elif cap == "inference.run_trial":
            if e["mode"] != "live":
                raise DomainError(
                    "Live trial requires a frozen live mission; use local tools for fixtures",
                    412,
                )
            text, call = provider.call(
                e["mission_id"],
                args["prompt"],
                args["max_output_tokens"],
                purpose=f"experiment:{e['id']}",
                cancelled=cancelled,
            )
            result = {
                "text": text,
                "call_id": call["id"],
                "model": call["model"],
                "latency_ms": call["latency_ms"],
                "usage": call.get("usage"),
                "ttft_ms": None,
                "task_id": args["task_id"],
                "source_ids": args["source_ids"],
                "provider": call.get("provider", "nebius_token_factory"),
            }
            klass = "measured_api"
        elif cap == "inference.run_benchmark":
            result = run_benchmark(self, e, cancelled)
            klass = "measured_api"
        elif cap == "artifacts.package":
            from .reports import export_pack

            result = export_pack(self.research, e["mission_id"])
        else:
            raise DomainError("Unregistered capability", 422)
        with self.store.tx() as c:
            artifact = self.research.artifacts.write(
                e["mission_id"],
                "tool_result",
                {
                    "run": run,
                    "plan": e,
                    "args": args,
                    "result": result,
                    "method_version": "tools-v1",
                    "evidence_class": klass,
                    "elapsed_ms": (time.perf_counter() - started) * 1000,
                },
            )
            self.store.put(c, "artifact", artifact)
            evidence = {
                "id": uid("evidence"),
                "mission_id": e["mission_id"],
                "step_id": e["step_id"],
                "step_revision": e["step_revision"],
                "experiment_id": e["id"],
                "run_id": run["id"],
                "artifact_id": artifact["id"],
                "sha256": artifact["sha256"],
                "evidence_class": klass,
                "capability": cap,
                "result": result,
                "mode": e["mode"],
                "provider": provider.provider_id
                if klass == "measured_api"
                else "local",
                "method_version": "tools-v1",
            }
            self.store.put(c, "evidence", evidence)
            node = {
                "id": uid("node"),
                "mission_id": e["mission_id"],
                "step_id": e["step_id"],
                "label": e["title"],
                "status": klass,
                "evidence_id": evidence["id"],
                "artifact_sha256": artifact["sha256"],
                "scope": result.get(
                    "scope", "API/local result; no provider hardware observation"
                ),
            }
            self.store.put(c, "causal_node", node)
            for hid in e["hypothesis_ids"]:
                self.store.put(
                    c,
                    "causal_edge",
                    {
                        "id": uid("edge"),
                        "mission_id": e["mission_id"],
                        "step_id": e["step_id"],
                        "from": hid,
                        "to": node["id"],
                        "status": "inferred",
                        "evidence_ids": [evidence["id"]],
                        "interpretation": "Experiment tests this hypothesis; support/falsification requires an evidence-linked reframe.",
                    },
                )
            run.update(
                state="completed", completed_at=now(), artifact_id=artifact["id"]
            )
            self.store.put(c, "run", run)
            current = self.store.get(c, e["id"], "experiment")
            if current["status"] != "cancelled":
                current["status"] = "completed"
            self.store.put(c, "experiment", current)
            s = self.store.get(c, e["step_id"], "step")
            if result.get("comparisons") and any(
                v.get("quality_gate") == "fail" or v.get("cost_gate") == "fail"
                for v in result["comparisons"].values()
            ):
                s["needs_reframe"] = True
            if s["revision"] == e["step_revision"] and current["status"] != "cancelled":
                s["status"] = "reviewing"
                self.store.put(c, "step", s)
            self.store.event(
                c,
                e["mission_id"],
                "evidence.created",
                {"id": evidence["id"], "class": klass, "experiment_id": e["id"]},
            )
