"""Governed research transitions. Each public mutation and its audit share a transaction."""

import json
from datetime import UTC, datetime, timedelta

from .db import DomainError, digest, now, uid
from .fixtures import SEATS


def plan_payload(experiment):
    mutable = {
        "revision",
        "status",
        "schema_version",
        "created_at",
        "plan_hash",
        "frozen_plan",
        "approved_at",
        "error",
    }
    return {k: v for k, v in experiment.items() if k not in mutable}


def validate_plan(experiment):
    if digest(plan_payload(experiment)) != experiment["plan_hash"]:
        raise DomainError(
            "Experiment plan hash changed; approval and execution refused", 422
        )


class Research:
    def __init__(
        self, store, settings, budget, artifacts, provider, free_provider=None
    ):
        self.store, self.settings, self.budget, self.artifacts, self.provider = (
            store,
            settings,
            budget,
            artifacts,
            provider,
        )
        from .free_provider import OpenRouterFreeProvider

        self.free_provider = free_provider or OpenRouterFreeProvider(
            store, settings, artifacts
        )
        from .direct_provider import DirectProvider
        self.direct_provider = DirectProvider(self)
        from .council_chat import CouncilChat

        self.chat = CouncilChat(self)
        from .accounting import Accounting
        from .context_packs import ContextPacks
        from .research_execution import ResearchExecution
        from .research_tools import ResearchTools
        from .source_library import SourceLibrary
        self.accounting = Accounting(self)
        self.library = SourceLibrary(self)
        self.tools = ResearchTools(self)
        self.context_packs = ContextPacks(self)
        self.research_execution = ResearchExecution(self)
        self.provider.research = self
        from .context_compaction import ContextCompaction
        self.context_compaction = ContextCompaction(self)
        from .council_preferences import CouncilPreferences
        self.council_preferences = CouncilPreferences(self)

    def provider_for(self, c, mission_id):
        mission = self.store.get(c, mission_id, "mission")
        if mission["brief"].get("provider") == "direct_council":
            raise DomainError("Direct seats execute council chat only. Local typed experiments remain available; API benchmark missions require their own verified provider contract.", 412)
        if mission["brief"].get("provider") != "openrouter_free":
            return self.provider
        model = mission["brief"].get("openrouter_model") or self.free_provider.model
        if model == self.free_provider.model:
            return self.free_provider
        from .free_provider import OpenRouterFreeProvider

        return OpenRouterFreeProvider(
            self.store, self.settings, self.artifacts, model=model
        )

    def budget_summary(self, c, mission_id):
        mission = self.store.get(c, mission_id, "mission")
        return self.budget.summary(
            c, mission_id, mission["brief"].get("provider", "nebius_token_factory")
        )

    def create_mission(self, c, brief):
        if brief.provider == "openrouter_free" and not self.settings.openrouter_enabled:
            raise DomainError("OpenRouter is disabled; historical missions remain readable.", 412)
        if brief.provider == "direct_council" and not self.settings.direct_free_confirmed:
            raise DomainError("Direct-provider free access has not been confirmed", 412)
        data = brief.model_dump()
        mid = uid("mission")
        mission = {
            "id": mid,
            "mission_id": mid,
            "revision": 1,
            "status": "draft",
            "brief": data,
        }
        self.store.put(c, "mission", mission)
        mapping = {s["key"]: uid("step") for s in data["steps"]}
        for s in data["steps"]:
            self.store.put(
                c,
                "step",
                {
                    "id": mapping[s["key"]],
                    "mission_id": mid,
                    "key": s["key"],
                    "title": s["title"],
                    "depends_on": [mapping[k] for k in s["depends_on"]],
                    "revision": 1,
                    "concern_revision": 0,
                    "status": "draft",
                    "paused": False,
                    "stale": False,
                },
            )
        self.store.event(c, mid, "mission.created", {"id": mid, "mode": data["mode"]})
        return mission

    def freeze(self, c, mid, expected):
        mission = self.store.get(c, mid, "mission")
        self.store.check(mission, expected)
        if mission["status"] != "draft":
            raise DomainError("Mission is already frozen")
        mission.update(
            status="frozen", frozen_at=now(), protocol_hash=digest(mission["brief"])
        )
        self.store.put(c, "mission", mission)
        self.store.put(
            c,
            "mission_revision",
            {
                "id": uid("revision"),
                "mission_id": mid,
                "revision": mission["revision"],
                "brief": mission["brief"],
                "protocol_hash": mission["protocol_hash"],
            },
        )
        for step in self.store.list(c, "step", mid):
            step["status"] = "ready"
            self.store.put(c, "step", step)
        self.store.event(
            c,
            mid,
            "mission.frozen",
            {
                "revision": mission["revision"],
                "protocol_hash": mission["protocol_hash"],
            },
        )
        return mission

    def draft(self, c, mid, expected, brief):
        m = self.store.get(c, mid, "mission")
        self.store.check(m, expected)
        if m["status"] != "draft":
            raise DomainError(
                "Frozen missions are immutable; create a new mission for a new protocol"
            )
        if [s.model_dump() for s in brief.steps] != m["brief"]["steps"]:
            raise DomainError("Create a new mission to change a draft dependency graph")
        m["brief"] = brief.model_dump()
        m["revision"] += 1
        self.store.put(c, "mission", m)
        self.store.event(c, mid, "mission.draft_updated", {"revision": m["revision"]})
        return m

    def active_step(self, c, sid, expected=None):
        s = self.store.get(c, sid, "step")
        if expected is not None:
            self.store.check(s, expected)
        m = self.store.get(c, s["mission_id"], "mission")
        if m["status"] != "frozen":
            raise DomainError("Freeze the mission first")
        if s["paused"]:
            raise DomainError("Step is paused")
        if s["status"] == "approved":
            raise DomainError(
                "Reopen this approved step before changing its research record"
            )
        if s["stale"]:
            raise DomainError("Step is stale; reopen after prerequisites are approved")
        for dep in s["depends_on"]:
            d = self.store.get(c, dep, "step")
            if d["status"] != "approved" or d["stale"]:
                raise DomainError("A prerequisite decision is not currently approved")
        return s, m

    def snapshot(self, c, step, mission):
        concerns = [
            x
            for x in self.store.list(c, "concern", mission["id"])
            if x["step_id"] == step["id"]
        ]
        evidence = [
            x
            for x in self.store.list(c, "evidence", mission["id"])
            if x["step_id"] == step["id"]
        ]
        deps = [self.store.get(c, k, "step") for k in step["depends_on"]]
        dependency_decisions = [
            d
            for d in self.store.list(c, "decision", mission["id"])
            if d["step_id"] in step["depends_on"] and d["status"] == "approved"
        ]
        value = {
            "mission_revision": mission["revision"],
            "protocol_hash": mission["protocol_hash"],
            "step_revision": step["revision"],
            "concern_revision": step["concern_revision"],
            "mission": mission["brief"],
            "step": {"id": step["id"], "title": step["title"]},
            "dependency_revisions": {d["id"]: d["revision"] for d in deps},
            "dependency_decisions": dependency_decisions,
            "research_memory": {
                kind: [
                    x
                    for x in self.store.list(c, kind, mission["id"])
                    if x.get("step_id") == step["id"]
                    and (kind != "decision" or x["status"] in ("approved", "stale"))
                ]
                for kind in ("hypothesis", "tradeoff", "reframe", "decision")
            },
            "history_policy": "Only previously revealed hypotheses, recorded evidence and director research memory are shared. Current-round private answers never enter this packet; stale decisions are history, not authority.",
            "concerns": concerns,
            "evidence": [
                {
                    "id": e["id"],
                    "sha256": e["sha256"],
                    "class": e["evidence_class"],
                    "result": e["result"],
                }
                for e in evidence
            ],
            "prompt_version": "research-v1",
            "packing_version": "source-facts-v1",
        }
        value["hash"] = digest(value)
        return value

    def enqueue(self, c, kind, target):
        jid = uid("job")
        c.execute(
            "INSERT INTO jobs VALUES(?,?,?,?,?,?,?)",
            (jid, target["mission_id"], kind, target["id"], "queued", "{}", now()),
        )
        return jid

    def round(self, c, sid, action):
        s, m = self.active_step(c, sid, action.expected_revision)
        if s.get("needs_reframe"):
            raise DomainError(
                "Contrary evidence requires an evidence-linked reframe before more rounds"
            )
        if s["status"] in ("committing", "approved"):
            raise DomainError(
                "This step cannot start another round in its current phase"
            )
        rounds = [
            r
            for r in self.store.list(c, "round", m["id"])
            if r["step_id"] == sid and r["step_revision"] == s["revision"]
        ]
        if len(rounds) >= 3:
            raise DomainError(
                "Three-round limit reached; reopen with a recorded revision before more work"
            )
        if len(rounds) >= 2 and not any(
            x["step_id"] == sid
            and x["step_revision"] == s["revision"]
            and x["created_at"] > rounds[-1]["created_at"]
            for x in self.store.list(c, "reframe", m["id"])
        ):
            raise DomainError(
                "Repeated rounds require an evidence-linked reframe before more generation"
            )
        if action.mode != m["brief"]["mode"]:
            raise DomainError("Round mode must match the frozen mission")
        model = (
            "fixture / no inference"
            if action.mode == "fixture"
            else self.provider_for(c, m["id"]).choose(c)
        )
        if action.mode == "live" and m["brief"].get("provider") == "openrouter_free":
            self.free_provider.capacity(c, m["id"], required=8)
        context = self.snapshot(c, s, m)
        r = {
            "id": uid("round"),
            "mission_id": m["id"],
            "step_id": sid,
            "step_revision": s["revision"],
            "concern_revision": s["concern_revision"],
            "context": context,
            "mode": action.mode,
            "provider": m["brief"].get("provider", "nebius_token_factory"),
            "status": "queued",
            "revealed": False,
            "reviews_complete": False,
            "review_passes": 0,
            "seats": [
                {
                    "id": k,
                    "name": name,
                    "role": role,
                    "model": model,
                    "state": "pending",
                }
                for k, name, role in SEATS
            ],
        }
        self.store.put(c, "round", r)
        self.enqueue(c, "round", r)
        s["status"] = "committing"
        self.store.put(c, "step", s)
        self.store.event(
            c,
            m["id"],
            "round.queued",
            {
                "round_id": r["id"],
                "context_hash": context["hash"],
                "model": model,
                "mode": action.mode,
            },
        )
        return self.public_round(c, r)

    def public_round(self, c, r):
        value = {k: v for k, v in r.items() if k not in ("context",)}
        value["context_hash"] = r["context"]["hash"]
        if r["revealed"]:
            value["submissions"] = [
                s
                for s in self.store.list(c, "submission", r["mission_id"])
                if s["round_id"] == r["id"]
            ]
            value["reviews"] = [
                s
                for s in self.store.list(c, "review", r["mission_id"])
                if s["round_id"] == r["id"]
            ]
            value["context"] = r["context"]
        return value

    def reveal(self, c, rid, expected):
        r = self.store.get(c, rid, "round")
        s, m = self.active_step(c, r["step_id"], expected)
        if r["revealed"]:
            return self.public_round(c, r)
        if (
            r["status"] != "committed"
            or len(
                [
                    x
                    for x in self.store.list(c, "submission", m["id"])
                    if x["round_id"] == rid
                ]
            )
            != 4
        ):
            raise DomainError("Reveal requires four valid private submissions")
        if (
            r["step_revision"] != s["revision"]
            or r["concern_revision"] != s["concern_revision"]
        ):
            raise DomainError("Round context is stale; create a new round")
        r.update(revealed=True, status="revealed", revealed_at=now())
        self.store.put(c, "round", r)
        submissions = [
            x for x in self.store.list(c, "submission", m["id"]) if x["round_id"] == rid
        ]
        for sub in submissions:
            self.store.put(
                c,
                "hypothesis",
                {
                    "id": uid("hypothesis"),
                    "mission_id": m["id"],
                    "step_id": s["id"],
                    "round_id": rid,
                    "submission_id": sub["id"],
                    "seat": sub["seat"],
                    "model": sub["model"],
                    "context_hash": sub["context_hash"],
                    "protocol_hash": m["protocol_hash"],
                    "source_ids": sub["content"]["source_ids"],
                    "mechanism": sub["content"]["mechanism"],
                    "prediction": sub["content"]["prediction"],
                    "kill_rule": sub["content"]["kill_rule"],
                    "affected_layers": sub["content"]["affected_layers"],
                    "status": "proposed",
                    "history": [{"status": "proposed", "at": now()}],
                },
            )
        s["status"] = "reviewing"
        self.store.put(c, "step", s)
        self.store.event(
            c,
            m["id"],
            "round.revealed",
            {"round_id": rid, "commitments": [x["commitment"] for x in submissions]},
        )
        return self.public_round(c, r)

    def continue_round(self, c, rid, action):
        r = self.store.get(c, rid, "round")
        s, m = self.active_step(c, r["step_id"], action.expected_revision)
        if r["status"] not in ("failed", "interrupted"):
            raise DomainError("Only a failed or interrupted round can continue")
        if (
            r["step_revision"] != s["revision"]
            or r["concern_revision"] != s["concern_revision"]
        ):
            raise DomainError("Changed context requires a new independent round")
        unknown = [
            call
            for call in self.store.list(c, "call", m["id"])
            if call["purpose"].startswith(f"round:{rid}:")
            and call["state"] == "unknown"
        ]
        if (
            unknown
            and not action.authorize_retry_with_unknown_charge
            and m["brief"].get("provider") != "openrouter_free"
        ):
            raise DomainError(
                "An earlier attempt may be billed. Reconcile it or explicitly authorize a new reserved attempt; its old maximum charge remains counted."
            )
        phase = r.get("active_phase", "round")
        if m["brief"].get("provider") == "openrouter_free":
            kind = "review" if phase == "review" else "submission"
            done = sum(
                x["round_id"] == rid
                and (kind != "review" or x.get("review_pass", 1) == r["review_passes"])
                for x in self.store.list(c, kind, m["id"])
            )
            self.free_provider.choose(c)
            self.free_provider.capacity(c, m["id"], required=4 - done)
        r["status"] = "queued"
        r.pop("error", None)
        self.store.put(c, "round", r)
        self.enqueue(c, phase, r)
        s["status"] = "reviewing" if phase == "review" else "committing"
        self.store.put(c, "step", s)
        self.store.event(
            c,
            m["id"],
            "round.continued",
            {
                "round_id": rid,
                "valid_seats_preserved": True,
                "unknown_retry_authorized": action.authorize_retry_with_unknown_charge,
            },
        )
        return self.public_round(c, r)

    def cancel_round(self, c, rid, expected):
        r = self.store.get(c, rid, "round")
        s = self.store.get(c, r["step_id"], "step")
        self.store.check(s, expected)
        if r["status"] in ("cancelled", "stale"):
            raise DomainError("Round is already terminal")
        r["status"] = "cancelled"
        self.store.put(c, "round", r)
        c.execute(
            "UPDATE jobs SET state='cancelled' WHERE target_id=? AND state='queued'",
            (rid,),
        )
        if s["revision"] == r["step_revision"] and s["status"] == "committing":
            s["status"] = "ready"
            self.store.put(c, "step", s)
        self.store.event(
            c,
            r["mission_id"],
            "round.cancelled",
            {
                "round_id": rid,
                "note": "Already dispatched charges and results are retained.",
            },
        )
        return self.public_round(c, r)

    def review(self, c, rid, expected):
        r = self.store.get(c, rid, "round")
        s, m = self.active_step(c, r["step_id"], expected)
        if not r["revealed"]:
            raise DomainError("Reveal before cross-review")
        if (
            r["step_revision"] != s["revision"]
            or r["concern_revision"] != s["concern_revision"]
        ):
            raise DomainError(
                "Concern or step changed; a fresh independent round is required"
            )
        if r["status"] == "reviewing" or r["review_passes"] >= 2:
            raise DomainError("Review already running or two-pass limit reached")
        if m["brief"].get("provider") == "openrouter_free":
            self.free_provider.choose(c)
            self.free_provider.capacity(c, m["id"], required=4)
        r["status"] = "reviewing"
        r["reviews_complete"] = False
        r["review_passes"] += 1
        self.store.put(c, "round", r)
        self.enqueue(c, "review", r)
        self.store.event(
            c, m["id"], "review.queued", {"round_id": rid, "pass": r["review_passes"]}
        )
        return self.public_round(c, r)

    def invalidate(self, c, s):
        for round in self.store.list(c, "round", s["mission_id"]):
            if (
                round["step_id"] == s["id"]
                and round["step_revision"] != s["revision"]
                and not round["revealed"]
            ):
                round["status"] = "stale"
                self.store.put(c, "round", round)
                c.execute(
                    "UPDATE jobs SET state='cancelled' WHERE target_id=? AND state='queued'",
                    (round["id"],),
                )
        for decision in self.store.list(c, "decision", s["mission_id"]):
            if decision["step_id"] == s["id"] and decision["status"] in (
                "draft",
                "approved",
            ):
                decision["status"] = "stale"
                self.store.put(c, "decision", decision)
        for experiment in self.store.list(c, "experiment", s["mission_id"]):
            if experiment["step_id"] == s["id"] and experiment["status"] in (
                "planned",
                "queued",
            ):
                experiment["status"] = "stale"
                self.store.put(c, "experiment", experiment)
                c.execute(
                    "UPDATE jobs SET state='cancelled' WHERE target_id=? AND state='queued'",
                    (experiment["id"],),
                )

    def concern(self, c, sid, action):
        s = self.store.get(c, sid, "step")
        self.store.check(s, action.expected_revision)
        s["revision"] += 1
        s["concern_revision"] += 1
        s["status"] = "ready"
        self.invalidate(c, s)
        self.store.put(c, "step", s)
        concern = {
            "id": uid("concern"),
            "mission_id": s["mission_id"],
            "step_id": sid,
            "revision": 1,
            "concern_revision": s["concern_revision"],
            "text": action.text,
            "severity": action.severity,
            "blocking": action.blocking,
            "affected_object_ids": action.affected_object_ids,
            "source": "human_director",
            "required_response": action.required_response,
            "status": "open",
            "acknowledged_by": [],
            "disposition": None,
        }
        self.store.put(c, "concern", concern)
        self.descendants(c, s, include_self=False)
        self.store.event(
            c,
            s["mission_id"],
            "concern.raised",
            {"id": concern["id"], "step_id": sid, "revision": s["revision"]},
        )
        return concern

    def disposition(self, c, cid, action):
        concern = self.store.get(c, cid, "concern")
        self.store.check(concern, action.expected_revision)
        if set(concern["acknowledged_by"]) != {x[0] for x in SEATS}:
            raise DomainError(
                "All four current reviewers must acknowledge this concern"
            )
        if action.status == "accepted_bounded_risk" and concern.get("blocking", True):
            raise DomainError(
                "A blocking requirement cannot be accepted as a discretionary risk"
            )
        concern.update(
            status=action.status,
            disposition=action.disposition,
            revision=concern["revision"] + 1,
        )
        self.store.put(c, "concern", concern)
        self.store.event(c, concern["mission_id"], "concern.resolved", {"id": cid})
        return concern

    def descendants(self, c, root, include_self=True):
        steps = self.store.list(c, "step", root["mission_id"])
        affected = {root["id"]}
        changed = True
        while changed:
            changed = False
            for s in steps:
                if s["id"] not in affected and any(
                    d in affected for d in s["depends_on"]
                ):
                    affected.add(s["id"])
                    changed = True
        for s in steps:
            if s["id"] in affected and s["id"] != root["id"]:
                s["stale"] = True
                s["revision"] += 1
                s["status"] = "blocked"
                self.invalidate(c, s)
                self.store.put(c, "step", s)
        return sorted(affected)

    def intervene(self, c, sid, verb, expected):
        s = self.store.get(c, sid, "step")
        self.store.check(s, expected)
        if verb == "pause":
            if s["paused"]:
                raise DomainError("Already paused")
            s["paused"] = True
        elif verb == "resume":
            if not s["paused"]:
                raise DomainError("Step is not paused")
            s["paused"] = False
        elif verb == "reopen":
            if s["stale"]:
                for dep in s["depends_on"]:
                    d = self.store.get(c, dep, "step")
                    if d["status"] != "approved" or d["stale"]:
                        raise DomainError(
                            "Approve prerequisites before reopening a stale step"
                        )
            s.update(
                revision=s["revision"] + 1, status="ready", stale=False, paused=False
            )
            self.invalidate(c, s)
            self.descendants(c, s)
        else:
            raise DomainError("Unknown intervention", 404)
        self.store.put(c, "step", s)
        self.store.event(
            c, s["mission_id"], "step." + verb, {"id": sid, "revision": s["revision"]}
        )
        return s

    def experiment(self, c, sid, action):
        s, m = self.active_step(c, sid, action.expected_revision)
        hypotheses = [
            self.store.get(c, hid, "hypothesis") for hid in action.hypothesis_ids
        ]
        if any(h["step_id"] != sid for h in hypotheses):
            raise DomainError("Hypotheses must belong to this step", 422)
        if action.refinement_of:
            previous = self.store.get(c, action.refinement_of, "experiment")
            if previous["step_id"] != sid or previous["status"] != "completed":
                raise DomainError(
                    "Refinements require a completed experiment in this step"
                )
            if not action.refinement_reason or len(action.refinement_reason) < 10:
                raise DomainError("State the evidence-motivated refinement reason", 422)
            if (
                sum(
                    bool(x.get("refinement_of"))
                    for x in self.store.list(c, "experiment", m["id"])
                    if x["step_id"] == sid
                )
                >= 2
            ):
                raise DomainError("Two-refinement limit reached")
        for tid in action.tradeoff_ids:
            if self.store.get(c, tid, "tradeoff")["step_id"] != sid:
                raise DomainError("Trade-off belongs to another step", 422)
        if action.capability == "analysis.evaluate_rubric":
            self.check_evidence(c, s, action.args["reviewed_evidence_ids"])
        e = {
            **action.model_dump(exclude={"expected_revision"}),
            "id": uid("experiment"),
            "mission_id": m["id"],
            "step_id": sid,
            "step_revision": s["revision"],
            "concern_revision": s["concern_revision"],
            "protocol_hash": m["protocol_hash"],
            "source_packet_hash": digest(m["brief"]["sources"]),
            "revision": 1,
            "status": "planned",
            "mode": m["brief"]["mode"],
        }
        e["priority_score"] = (
            sum(
                e[k]
                for k in ("information_value", "impact", "feasibility", "cost_score")
            )
            / 4
        )
        if not e["tradeoff_ids"]:
            card = {
                "id": uid("tradeoff"),
                "mission_id": m["id"],
                "step_id": sid,
                "revision": 1,
                "category": "conflict",
                "title": "Expected trade-off: " + e["title"],
                "expected_pros": [e["prediction"]],
                "expected_cons": [
                    "Any finding is limited to the declared control, inputs and evidence scope."
                ],
                "observed_pros": [],
                "observed_cons": [],
                "hidden_costs": [
                    "Evidence collection/review effort; all actual model attempts must be counted."
                ],
                "mitigations": [
                    "Use the frozen controls and preserve negative or inconclusive results."
                ],
                "operating_region": e["control"],
                "complexity": e["capability"],
                "rejection_rule": e["kill_rule"],
                "evidence_ids": [],
            }
            self.store.put(c, "tradeoff", card)
            e["tradeoff_ids"] = [card["id"]]
        e["frozen_plan"] = json.loads(json.dumps(plan_payload(e)))
        e["plan_hash"] = digest(e["frozen_plan"])
        self.store.put(c, "experiment", e)
        self.store.event(
            c,
            m["id"],
            "experiment.planned",
            {"id": e["id"], "capability": e["capability"], "plan_hash": e["plan_hash"]},
        )
        return e

    def approve_experiment(self, c, eid, expected):
        e = self.store.get(c, eid, "experiment")
        self.store.check(e, expected)
        s, m = self.active_step(c, e["step_id"])
        if e["status"] != "planned":
            raise DomainError("Only a planned experiment can be approved")
        validate_plan(e)
        if (
            e["step_revision"] != s["revision"]
            or e["concern_revision"] != s["concern_revision"]
        ):
            raise DomainError("Experiment is stale")
        if e["capability"].startswith("inference.run") and e["mode"] == "live":
            if (
                m["brief"].get("provider") == "openrouter_free"
                and e["capability"] == "inference.run_benchmark"
            ):
                raise DomainError(
                    "The cost benchmark requires verified Token Factory models; free missions support councils and bounded trials",
                    412,
                )
            self.provider_for(c, m["id"]).choose(c)
        e.update(status="queued", approved_at=now(), revision=e["revision"] + 1)
        self.store.put(c, "experiment", e)
        self.enqueue(c, "experiment", e)
        for hid in e["hypothesis_ids"]:
            h = self.store.get(c, hid, "hypothesis")
            h["status"] = "testing"
            h["history"].append(
                {"status": "testing", "at": now(), "experiment_id": eid}
            )
            self.store.put(c, "hypothesis", h)
        s["status"] = "awaiting_evidence"
        self.store.put(c, "step", s)
        self.store.event(
            c, m["id"], "experiment.approved", {"id": eid, "plan_hash": e["plan_hash"]}
        )
        return e

    def cancel_experiment(self, c, eid, expected):
        e = self.store.get(c, eid, "experiment")
        self.store.check(e, expected)
        if e["status"] not in ("queued", "running", "planned"):
            raise DomainError("Experiment is already terminal")
        e["status"] = "cancelled"
        e["revision"] += 1
        self.store.put(c, "experiment", e)
        c.execute(
            "UPDATE jobs SET state='cancelled' WHERE target_id=? AND state='queued'",
            (eid,),
        )
        self.store.event(
            c,
            e["mission_id"],
            "experiment.cancelled",
            {
                "id": eid,
                "note": "Already dispatched calls may complete and retain charges.",
            },
        )
        return e

    def check_evidence(self, c, s, evidence_ids):
        for eid in evidence_ids:
            e = self.store.get(c, eid, "evidence")
            if e["step_id"] != s["id"]:
                raise DomainError("Evidence must belong to this research step", 422)
            self.artifacts.read(self.store.get(c, e["artifact_id"], "artifact"))

    def tradeoff(self, c, sid, action):
        s, m = self.active_step(c, sid, action.expected_revision)
        self.check_evidence(c, s, action.evidence_ids)
        card = {
            **action.model_dump(exclude={"expected_revision"}),
            "id": uid("tradeoff"),
            "mission_id": m["id"],
            "step_id": sid,
            "revision": 1,
        }
        self.store.put(c, "tradeoff", card)
        self.store.event(c, m["id"], "tradeoff.recorded", {"id": card["id"]})
        return card

    def challenge_group(self, c, sid, action):
        _s, m = self.active_step(c, sid, action.expected_revision)
        for hid in action.hypothesis_ids:
            if self.store.get(c, hid, "hypothesis")["step_id"] != sid:
                raise DomainError("Hypothesis belongs to another step", 422)
        rounds = {
            r["id"]
            for r in self.store.list(c, "round", m["id"])
            if r["step_id"] == sid and r["revealed"]
        }
        for rid in action.review_ids:
            if self.store.get(c, rid, "review")["round_id"] not in rounds:
                raise DomainError("Review belongs to another step", 422)
        group = {
            "id": action.group_id or uid("group"),
            "mission_id": m["id"],
            "step_id": sid,
            "revision": 1,
            "title": action.title,
            "hypothesis_ids": action.hypothesis_ids,
            "review_ids": action.review_ids,
        }
        if action.group_id:
            previous = self.store.get(c, action.group_id, "challenge_group")
            self.store.check(previous, action.group_revision)
            if previous["step_id"] != sid:
                raise DomainError("Group belongs to another step", 422)
            group["revision"] = previous["revision"] + 1
        self.store.put(c, "challenge_group", group)
        self.store.event(
            c,
            m["id"],
            "challenges.grouped",
            {"id": group["id"], "revision": group["revision"]},
        )
        return group

    def reframe(self, c, sid, action):
        s, m = self.active_step(c, sid, action.expected_revision)
        self.check_evidence(c, s, action.evidence_ids)
        for hid, status in action.hypothesis_states.items():
            h = self.store.get(c, hid, "hypothesis")
            if h["step_id"] != sid:
                raise DomainError("Hypothesis belongs to another step", 422)
            h["status"] = status
            h["history"].append(
                {"status": status, "at": now(), "evidence_ids": action.evidence_ids}
            )
            self.store.put(c, "hypothesis", h)
        r = {
            **action.model_dump(exclude={"expected_revision"}),
            "id": uid("reframe"),
            "mission_id": m["id"],
            "step_id": sid,
            "step_revision": s["revision"],
        }
        self.store.put(c, "reframe", r)
        s["needs_reframe"] = False
        self.store.put(c, "step", s)
        self.store.put(
            c,
            "causal_edge",
            {
                "id": uid("edge"),
                "mission_id": m["id"],
                "step_id": sid,
                "from": "Observed evidence",
                "to": action.interpretation,
                "status": "inferred",
                "evidence_ids": action.evidence_ids,
                "next_test": action.next_action,
            },
        )
        self.store.event(c, m["id"], "research.reframed", {"id": r["id"]})
        return r

    def decision(self, c, sid, action):
        s, m = self.active_step(c, sid, action.expected_revision)
        self.check_evidence(c, s, action.evidence_ids)
        if s.get("needs_reframe"):
            raise DomainError(
                "Record what the contrary evidence changed before drafting the decision"
            )
        current = [
            r
            for r in self.store.list(c, "round", m["id"])
            if r["step_id"] == sid
            and r["step_revision"] == s["revision"]
            and r["concern_revision"] == s["concern_revision"]
            and r["reviews_complete"]
        ]
        if not current:
            raise DomainError("A current four-seat cross-review is required")
        d = {
            **action.model_dump(exclude={"expected_revision"}),
            "id": uid("decision"),
            "mission_id": m["id"],
            "step_id": sid,
            "step_revision": s["revision"],
            "concern_revision": s["concern_revision"],
            "revision": 1,
            "status": "draft",
            "context_hash": current[-1]["context"]["hash"],
        }
        d["gates"] = self.gates(c, s, d)
        self.store.put(c, "decision", d)
        s["status"] = "decision_ready"
        self.store.put(c, "step", s)
        self.store.event(
            c, m["id"], "decision.drafted", {"id": d["id"], "verdict": d["verdict"]}
        )
        return d

    def gates(self, c, s, d):
        evidence = [self.store.get(c, eid, "evidence") for eid in d["evidence_ids"]]
        m = self.store.get(c, s["mission_id"], "mission")
        budget = self.budget.summary(
            c, provider=m["brief"].get("provider", "nebius_token_factory")
        )
        _credit = (
            "pass"
            if budget["global_committed_usd"] <= min(budget["absolute_cap_usd"], budget["operational_cap_usd"])
            else "fail"
        )
        integrity = "pass"
        for e in evidence:
            try:
                self.artifacts.read(self.store.get(c, e["artifact_id"], "artifact"))
            except (DomainError, OSError):
                integrity = "invalid"
        from .analysis import decision_gates

        return decision_gates(evidence, budget, s["revision"], integrity)

    def approve_decision(self, c, did, expected):
        d = self.store.get(c, did, "decision")
        self.store.check(d, expected)
        s, m = self.active_step(c, d["step_id"])
        if (
            d["status"] != "draft"
            or d["step_revision"] != s["revision"]
            or d["concern_revision"] != s["concern_revision"]
        ):
            raise DomainError("Decision is stale or already terminal")
        concerns = [
            x for x in self.store.list(c, "concern", m["id"]) if x["step_id"] == s["id"]
        ]
        if any(
            (x.get("blocking", True) and x["status"] != "resolved")
            or x["status"] in ("open", "blocked")
            or set(x["acknowledged_by"]) != {r[0] for r in SEATS}
            for x in concerns
        ):
            raise DomainError(
                "Resolve blocking concerns after all-seat acknowledgement; record dispositions for remaining risks"
            )
        d["gates"] = self.gates(c, s, d)
        if d["verdict"] == "confirmed" and any(
            g["status"] != "pass" for g in d["gates"]
        ):
            raise DomainError(
                "A confirmed finding requires every hard gate to pass; approve an honest inconclusive report instead"
            )
        d.update(status="approved", approved_at=now(), revision=d["revision"] + 1)
        self.store.put(c, "decision", d)
        s["status"] = "approved"
        self.store.put(c, "step", s)
        self.store.event(
            c,
            m["id"],
            "decision.approved",
            {"id": did, "verdict": d["verdict"], "gates": d["gates"]},
        )
        return d

    def artifact_visible(self, c, a):
        if a.get("private_round_id"):
            r = self.store.get(c, a["private_round_id"], "round")
            if not r["revealed"]:
                return False
        return True

    def view(self, c, mid):
        m = self.store.get(c, mid, "mission")
        kinds = (
            "step",
            "concern",
            "hypothesis",
            "experiment",
            "evidence",
            "decision",
            "tradeoff",
            "reframe",
            "causal_edge",
            "causal_node",
            "challenge_group",
        )
        value = {
            "mission": m,
            **{
                ("hypotheses" if k == "hypothesis" else k + "s"): self.store.list(
                    c, k, mid
                )
                for k in kinds
            },
        }
        value["rounds"] = [
            self.public_round(c, r) for r in self.store.list(c, "round", mid)
        ]
        value["budget"] = self.budget_summary(c, mid)
        value["artifacts"] = [
            a
            for a in self.store.list(c, "artifact", mid)
            if self.artifact_visible(c, a)
        ]
        value["calls"] = [
            {k: v for k, v in a.items() if k not in ("prompt", "response")}
            for a in self.store.list(c, "call", mid)
        ]
        value["jobs"] = [
            dict(r)
            for r in c.execute(
                "SELECT id,kind,target_id,state,created_at FROM jobs WHERE mission_id=? ORDER BY created_at",
                (mid,),
            )
        ]
        value["events"] = [
            {**dict(r), "body": json.loads(r["body"])}
            for r in c.execute(
                "SELECT * FROM events WHERE mission_id=? ORDER BY seq DESC LIMIT 100",
                (mid,),
            )
        ]
        return value

    def verify_live(self, c, action):
        if not all(
            (
                action.credit_only_confirmed,
                action.automatic_payments_disabled,
                action.token_bound_verified,
                action.all_billing_categories_bounded,
            )
        ):
            raise DomainError(
                "All live prerequisites must be confirmed with actual account evidence",
                412,
            )
        if action.operational_cap_usd > action.existing_credit_usd:
            raise DomainError("Operational cap exceeds verified credit", 422)
        if any(model not in self.settings.models for model in action.catalog_model_ids):
            raise DomainError("Only the configured exact model IDs are allowed", 422)
        if any(
            k not in self.settings.models
            or set(v) != {"input", "output"}
            or any(
                not isinstance(rate, (int, float)) or not 0 < rate <= 100
                for rate in v.values()
            )
            for k, v in action.prices.items()
        ):
            raise DomainError(
                "Prices require positive input/output USD per million for enabled exact models",
                422,
            )
        v = {
            **action.model_dump(),
            "id": uid("verification"),
            "verified_at": now(),
            "expires_at": (
                datetime.now(UTC) + timedelta(hours=action.expires_in_hours)
            ).isoformat(),
        }
        self.store.set_setting(c, "live_verification", v)
        return v
