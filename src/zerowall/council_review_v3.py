"""One Council: isolated proposals, public deliberation, scoped checks and synthesis.

Legacy profiles retain their original limits. Their source/revision validators
are reused here; current scheduling and publication live under reviewed_v3.
"""

import json
import re

from pydantic import ValidationError

from .contracts import (
    CouncilDeliberation,
    CouncilDeltaScope,
    CouncilExtraction,
    CouncilRecheck,
    CouncilScrutiny,
    CouncilSynthesis,
)
from .council_review_v2 import INSTRUCTIONS as SCOPED_INSTRUCTIONS
from .council_review_v2 import ScopedReview
from .db import DomainError, digest, now
from .review_json import parse_review_json
from .review_admission import (
    FORMAT_RULES,
    check_envelope,
    commentary_text,
    failure_message,
    family_conflicts,
    normalize_extraction,
    normalize_inventory,
    normalize_recheck,
    normalize_transport,
)
from .review_admission import VERSION as ADMISSION_VERSION
from .review_audits import CAPABILITIES, audit_result
from .review_policy_v3 import POLICY_VERSION, publication_decisions
from .review_provenance import observation_cues

SCHEMAS = {
    "extraction": CouncilExtraction,
    "scrutiny": CouncilScrutiny,
    "repair": CouncilDeliberation,
    "recheck": CouncilRecheck,
    "synthesis": CouncilSynthesis,
}
INSTRUCTIONS = {
    **SCOPED_INSTRUCTIONS,
    "opening": "Answer the director independently in readable English Markdown. No peer replies are available in this opening. Give explicit assumptions and at most two material assertions within 240 words. When several approaches are requested, suggest up to two distinct mechanisms/strategies, each with its central assertion, rather than several labels for one idea. Follow the requested deliverable. Do not invent experiments, citations, measurements or supplied evidence. Speculative ideas are welcome when labelled as proposals. Use readable math.",
    "extraction": SCOPED_INSTRUCTIONS["extraction"]
    + " Also propose the actual task output_contract (deliverable/count/criteria), a bounded source-unit inventory with omitted material/overflow, distinct approach families with mechanism/boundary/resources/test criteria, and at most eight relevant typed audit descriptors. Audit inputs are model interpretations, not trusted evidence. Use C refs from this extraction for descriptors/families. Use no descriptor when inputs cannot be represented faithfully. A missing source is unverified; do not manufacture a source. Keep compact; do not copy original passages.",
    "repair": "Participate in the public council deliberation. Give a short readable explanation of what you retained or changed and why. Answer EVERY supplied finding for EACH of your assigned claims, with actual finding_ids and current claim_revision. Retain, rebut, narrow, revise or withdraw, preserving goal, scope and necessary conditions. ALWAYS include revised_text: for narrow/revise put the actual complete revised assertion there (never empty); use retain/rebut when no assertion changes. Do not put the revision only in response or explanation. You may raise at most two specific peer_challenges against OTHER authors' current assertions; cite their exact IDs/revisions and decision impact. Earlier responses are visible and ordered, not independent evidence. You cannot change another author's claim or invent observations. Late ideas remain unreviewed. Return the specified compact JSON.",
    "recheck": SCOPED_INSTRUCTIONS["recheck"]
    + " Include EVERY main and peer finding. An author who replied before a peer challenge has not answered it. Keep an unanswered late challenge open. Reassess family distinctness using exact current claim_ids/revisions when possible; omitted or changed groups remain stale. Respect scoped local checks and their input/derivation limits. Return short fields; no artificial consensus.",
    "synthesis": SCOPED_INSTRUCTIONS["synthesis"]
    + " Fulfil output_contract. For ranked approaches use ranked_approaches referencing ONLY current distinct assessed families, in criterion-based order; do not pad with duplicate variants. If fewer defensible families exist, state the shortfall in deliverable_limitations. Speculative alternatives must keep their actual conditional status. Describe what changed in deliberation. Never turn an arithmetic check, repeated claim or source title into external verification.",
}


def requested_count(question):
    match = re.search(
        r"\b(?:best|top|give(?:\s+me)?|compare)\s+(\d{1,2}|two|three|four|five|six|seven|eight|nine|ten)\b",
        question,
        re.IGNORECASE,
    )
    if not match:
        return None
    word = match.group(1).lower()
    number = (
        int(word)
        if word.isdigit()
        else {
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
        }[word]
    )
    return number if 1 <= number <= 20 else None


class UnifiedCouncil(ScopedReview):
    # Two claims per author is a prompting target, not a reason to discard valid work.
    # The current schema still bounds the full extraction to eight claims.
    claims_per_author_limit = 8

    def validate(self, record):
        super().validate(record)
        if record.get("execution_plan") and digest(
            record["execution_plan"]
        ) != record.get("plan_hash"):
            raise DomainError(
                "The saved council plan changed outside a governed transition", 422
            )

    @staticmethod
    def roles_for(members):
        preferred = {p.get("provider"): p["id"] for p in members}
        return {
            "extraction": preferred.get("gemini", members[0]["id"]),
            "scrutiny": preferred.get("nvidia_nim", members[1]["id"]),
            "recheck": preferred.get("zai", members[-1]["id"]),
            "synthesis": preferred.get("gemini", members[0]["id"]),
        }

    def contract(self, chat, question, options, revision):
        value = super().contract(chat, question, options, revision)
        value.update(
            protocol_version="reviewed_v3",
            prompt_version="unified-council-v3",
            policy_version=POLICY_VERSION,
            descriptor_version="council-descriptors-v3",
            claims_per_author=self.claims_per_author_limit,
            schema_hash=digest(
                {phase: schema.model_json_schema() for phase, schema in SCHEMAS.items()}
            ),
            prompt_hash=digest(INSTRUCTIONS),
            audit_capabilities=CAPABILITIES,
            focused_exchange_limit=1,
            focused_author_limit=2,
            recovery_attempt_limit=3,
            groq_output_ceiling=3072,
            phase_output_limits={
                "opening": 2048,
                "extraction": 6144,
                "scrutiny": 4096,
                "repair": 4096,
                "recheck": 6144,
                "synthesis": 4096,
            },
        )
        if chat["provider"] == "nebius_token_factory":
            value.pop("context_byte_limit", None)
            value["context_window_tokens"] = (
                self.chat.settings.token_factory_generation["context_tokens"]
            )
        return value

    def initialize(self, c, chat, options):
        super().initialize(c, chat, options)
        self.prepare(c, chat)

    def prepare(self, c, chat):
        record = self.record(c, chat)
        record.update(
            focused_authors=[],
            focus_decision=None,
            inventory_status="partial",
            inventory_limitations="Material inventory has not been assessed",
            output_contract={},
            route=chat.get(
                "council_route", {"kind": "full", "reason": "New or unbounded scope"}
            ),
        )
        self.save_plan(c, chat, record)

    def schedule(self, chat, record):
        turns = super().schedule(chat, record)
        route = record.get("route", {})
        if route.get("kind") in ("explain", "resynthesis"):
            return [t for t in turns if t["phase"] == "synthesis"]
        if route.get("kind") == "delta":
            turns = [
                t
                for t in turns
                if t["phase"] != "opening"
                and (t["phase"] != "repair" or t["author_id"] in route["authors"])
            ]
        for turn in turns:
            if turn["phase"] not in ("opening", "repair"):
                turn["key"] = f"review:{record['cycle']}:{turn['phase']}" + (
                    ":" + str(chat["generation"])
                    if turn["phase"] == "synthesis"
                    else ""
                )
        repairs = [t for t in turns if t["phase"] == "repair"]
        if repairs:
            offset = (record["cycle"] - 1) % len(repairs)
            repairs = repairs[offset:] + repairs[:offset]
        result = [
            t for t in turns if t["phase"] not in ("repair", "recheck", "synthesis")
        ]
        result += repairs
        result += [t for t in turns if t["phase"] == "recheck"]
        members = {p["id"]: p for p in chat["participants"]}
        for author in record.get("focused_authors", []):
            original = next(t for t in repairs if t["author_id"] == author)
            result.append(
                {**original, "key": original["key"] + ":focus", "focused": True}
            )
        if record.get("focused_authors"):
            original = next(t for t in turns if t["phase"] == "recheck")
            result.append(
                {**original, "key": original["key"] + ":focus", "focused": True}
            )
        result += [t for t in turns if t["phase"] == "synthesis"]
        for turn in result:
            if turn["participant"]["id"] not in members:
                raise DomainError(
                    "The role is outside the frozen selected participants", 422
                )
        return result

    def save_plan(self, c, chat, record):
        record["execution_plan"] = {
            "route": record.get("route", {"kind": "full"}),
            "baseline_calls": 1
            if record.get("route", {}).get("kind") in ("explain", "resynthesis")
            else len(record["route"]["authors"]) + 4
            if record.get("route", {}).get("kind") == "delta"
            else 2 * len(chat["participants"]) + 4,
            "recovery_reserve": 3,
            "attempt_ceiling": 20,
            "focused_exchange_calls": len(record.get("focused_authors", [])) + 1
            if record.get("focused_authors")
            else 0,
            "turns": [
                {k: t.get(k) for k in ("key", "phase", "author_id", "focused")}
                | {"participant_id": t["participant"]["id"]}
                for t in self.schedule(chat, record)
            ],
        }
        record["plan_hash"] = digest(record["execution_plan"])
        self.store.put(c, "chat_review", record)

    def snapshot(self, c, chat):
        value = super().snapshot(c, chat)
        record = self.record(c, chat)

        def items(kind):
            return [
                x
                for x in self.store.list(c, kind, chat["mission_id"])
                if x.get("review_cycle") == value["cycle"]
            ]

        for key in (
            "output_contract",
            "inventory",
            "inventory_status",
            "inventory_limitations",
            "execution_plan",
            "plan_hash",
            "focus_decision",
            "route",
            "admission_notes",
            "conversation_checkpoint",
            "conversation_checkpoint_hash",
            "delivery_degraded",
            "delivery_warnings",
        ):
            value[key] = record.get(key)
        value["families"] = items("review_family")
        value["admission_records"] = items("review_admission")
        value["audit_descriptors"] = items("review_audit")
        current = {x["claim_id"]: x for x in value["claims"]}
        # View is pure: current expected checks can be computed, but not persisted
        # merely by loading a page. Admission writes the same results durably.
        value["audit_results"] = [
            audit_result(a, current[a["claim_id"]], value["evidence"])
            for a in value["audit_descriptors"]
            if a["claim_id"] in current
        ]
        for family in value["families"]:
            family["stale"] = any(
                current.get(m["claim_id"], {}).get("revision") != m["revision"]
                for m in family["members"]
            )
        value["decisions"] = publication_decisions(value)
        value["decision_hash"] = digest(value["decisions"])
        return value

    def scan(self, c, chat, record, message):
        if getattr(self, "_defer_scan", False):
            return
        existing = [
            x
            for x in self.store.list(c, "review_observation", chat["mission_id"])
            if x.get("review_cycle") == record["cycle"]
        ]
        cues = observation_cues(message)
        available = max(0, 16 - len(existing))
        for cue in cues[:available]:
            self.put(c, chat, record, "review_observation", cue)
        if len(cues) > available:
            record.update(
                observation_status="overflow",
                observation_coverage="Local observation cues exceed this batch; full source remains saved",
            )
            self.store.put(c, "chat_review", record)

    def prompt(self, c, chat, messages, turn):
        if turn["phase"] == "synthesis" and self.record(c, chat).get("delivery_degraded"):
            from .review_delivery import synthesis_prompt
            return synthesis_prompt(self, c, chat, messages, turn)
        raw, ids = super().prompt(c, chat, messages, turn)
        p = json.loads(raw)
        phase = turn["phase"]
        p["instructions"] = INSTRUCTIONS[phase]
        checkpoint = self.record(c, chat).get("conversation_checkpoint")
        if checkpoint:
            p["conversation_checkpoint"] = checkpoint
        p["output_token_limit"] = self.chat.output_limit(chat, turn)
        p["brevity"] = (
            "Complete compact records. Prefer short fields (reasons <=100 characters). Omit optional descriptors when faithful typed inputs are unavailable; disclose incomplete inventory. Do not repeat source paragraphs. Never omit a required finding or author to fit."
        )
        prior_requests = [
            m
            for m in messages
            if m["role"] == "user"
            and m.get("phase") == "intervention"
            and m.get("review_cycle") != turn.get("cycle")
        ]
        p["prior_director_requests"] = [
            {"id": m["id"], "text": m["content"]} for m in prior_requests
        ]
        p["exposure_boundary"] = (
            "Shared prior director requests; no current-cycle peer answers in independent openings. Deliberation sees the declared public responses."
        )
        ids += [m["id"] for m in prior_requests]
        if phase != "opening":
            snap = self.snapshot(c, chat)
            p["transport_format_rules"] = FORMAT_RULES
            if snap.get("admission_notes"):
                p["admission_notes"] = snap["admission_notes"]
            p["response_schema"] = SCHEMAS[phase].model_json_schema()
            p["audits"] = snap["audit_results"]
            p["families"] = snap["families"]
            p["output_contract"] = snap["output_contract"]
            p["inventory_limitations"] = snap["inventory_limitations"]
            p["execution_plan_hash"] = snap["plan_hash"]
            if phase == "extraction":
                p["audit_capabilities"] = CAPABILITIES
            if phase == "extraction" and snap.get("route", {}).get("kind") == "delta":
                p["response_schema"] = CouncilDeltaScope.model_json_schema()
                p["claims"] = [
                    {
                        k: x.get(k)
                        for k in (
                            "claim_id",
                            "revision",
                            "text",
                            "scope",
                            "assumptions",
                            "dependencies",
                        )
                    }
                    for x in snap["claims"]
                ]
                p["instructions"] = (
                    "Scope this explicit challenge against ALL supplied current claims. Return their exact claim_ids. If the request changes material premises, introduces a new approach or cannot fit the existing scope, set within_claim_scope=false; a full independent cycle will be preflighted. Otherwise give the output contract and precise scope reason. This is a scoping step, not new evidence or a claim revision."
                )
            if snap.get("route", {}).get("kind") == "explain":
                p["instructions"] += (
                    " This request only EXPLAINS the frozen previous review. No new checks were performed. Do not introduce new factual assertions, change evidence labels or claim a fresh review. Cite the existing assertions and describe their recorded status."
                )
            if phase == "repair":
                responses = [
                    m
                    for m in messages
                    if m.get("review_cycle") == snap["cycle"] and m["phase"] == "repair"
                ]
                p["earlier_public_responses"] = [
                    {
                        "id": m["id"],
                        "author_id": m["participant_id"],
                        "text": m["content"][:1200],
                        "excerpted": len(m["content"]) > 1200,
                    }
                    for m in responses
                ]
                p["response_context_rule"] = (
                    "Earlier replies can be excerpts. All current peer assertions and required findings below are authoritative context records; the full transcript remains saved. An excerpt is not evidence."
                )
                p["peer_claims"] = [
                    {
                        k: x.get(k)
                        for k in (
                            "claim_id",
                            "revision",
                            "author_id",
                            "text",
                            "scope",
                            "assumptions",
                        )
                    }
                    for x in snap["claims"]
                    if x["author_id"] != turn["author_id"]
                ]
                p["peer_findings"] = [
                    {
                        "finding_id": f["id"],
                        **{
                            k: f.get(k)
                            for k in (
                                "claim_id",
                                "claim_revision",
                                "objection",
                                "minimum_resolution",
                            )
                        },
                    }
                    for f in snap["findings"]
                    if f["claim_id"] not in {x["claim_id"] for x in p["claims"]}
                ]
                p["focused_exchange"] = bool(turn.get("focused"))
                ids += [m["id"] for m in responses]
            if phase == "recheck":
                p["author_response_finding_ids"] = [
                    r["finding_ids"] for r in snap["repairs"]
                ]
            if phase == "synthesis":
                p["decisions"] = snap["decisions"]
                p["coverage"] = snap["coverage"]
                p["current_distinct_families"] = [
                    f["id"]
                    for f in snap["families"]
                    if not f["stale"] and f.get("distinct_as_assessed", True)
                ]
        # Remove transport/database metadata, not assertions or obligations.
        # Repeated full ledgers previously consumed free-provider context before
        # a model could give a useful response.
        p["contract"] = {
            k: p["contract"][k]
            for k in ("question", "options", "protocol_version", "policy_version")
        }
        p["context_representation"] = (
            "Phase-specific records; transport metadata omitted. Full sources and exact context hash remain saved."
        )
        if "source_units" in p:
            # The model cites stable unit IDs. Exact character offsets stay in
            # the server's source map; repeating them adds no source content.
            p["source_units"] = [
                {
                    key: value
                    for key, value in unit.items()
                    if key not in ("start", "end")
                }
                for unit in p["source_units"]
            ]
        if phase != "opening":

            def compact_schema(value):
                if isinstance(value, dict):
                    return {
                        k: compact_schema(v)
                        for k, v in value.items()
                        if k not in ("title", "description", "default")
                    }
                return (
                    [compact_schema(x) for x in value]
                    if isinstance(value, list)
                    else value
                )

            p["response_schema"] = compact_schema(p["response_schema"])
            p["audits"] = [
                {k: v for k, v in a.items() if k != "inputs"}
                | {
                    "declared_inputs": {
                        k: a["inputs"]["descriptor"].get(k)
                        for k in (
                            "expression",
                            "quantities",
                            "output_unit",
                            "output_kind",
                            "expected_value",
                            "boundary",
                            "denominator",
                            "resources",
                            "reference",
                            "claimed_support",
                        )
                    }
                }
                for a in p["audits"]
            ]
        encoded = json.dumps(p, ensure_ascii=False, separators=(",", ":"))
        context_bytes = len(encoded.encode())
        if chat["provider"] != "nebius_token_factory" and context_bytes > 90000:
            raise DomainError(
                f"The final review input is {context_bytes:,} UTF-8 bytes, above the application's 90,000-byte review-packing limit (not the model's token-context limit). No required source text, warning or objection was dropped; saved work remains here.",
                422,
            )
        return encoded, list(dict.fromkeys(ids))

    def extract(self, c, chat, record, output, message_id):
        # Original validators enforce source spans, authors, qualifiers and DAGs.
        adapted = {
            **output,
            "observation_status": "partial"
            if output["observation_status"] == "overflow"
            else output["observation_status"],
        }
        super().extract(c, chat, record, adapted, message_id)
        claims = [
            x
            for x in self.store.list(c, "review_claim", chat["mission_id"])
            if x.get("extraction_message_id") == message_id
        ]
        by_ref = dict(zip([x["ref"] for x in output["claims"]], claims, strict=True))
        originals = {
            m["id"]: m
            for m in self.chat.messages(c, chat)
            if m.get("review_cycle") == record["cycle"] and m["phase"] == "opening"
        }

        def spans(message, unit_ids):
            units = {u["id"]: u for u in self.source_units(message)}
            return [{**units[u], "hash": digest(units[u]["text"])} for u in unit_ids]

        inventory = []
        for item in output["inventory"]:
            source = originals[item["source_message_id"]]
            inventory.append(
                {
                    **item,
                    "source_spans": spans(source, item["source_unit_ids"]),
                    "claim_ids": [by_ref[r]["claim_id"] for r in item["claim_refs"]],
                }
            )
        conflicts = family_conflicts(
            [
                {
                    "key": index,
                    "members": set(family["refs"]),
                    "mechanism": family["mechanism"],
                }
                for index, family in enumerate(output["families"])
            ],
            [
                set(group["refs"])
                for group in output["groups"]
                if group["relation"] == "equivalent_as_assessed"
            ],
        )
        for index, family in enumerate(output["families"]):
            members = [
                {"claim_id": by_ref[r]["claim_id"], "revision": 1}
                for r in family["refs"]
            ]
            member_ids = frozenset(x["claim_id"] for x in members)
            if len(member_ids) != len(members):
                raise ValueError("A family cannot repeat a claim reference")
            warnings = conflicts.get(index, [])
            self.put(
                c,
                chat,
                record,
                "review_family",
                {
                    **family,
                    "members": members,
                    "original_members": members,
                    "assessment_history": [
                        {
                            "members": members,
                            "distinct_as_assessed": not warnings,
                            "model_distinct_as_assessed": True,
                            "admission_warnings": warnings,
                            "source_message_id": message_id,
                            "stage": "extraction",
                        }
                    ],
                    "origin": "model_assessment",
                    "distinct_as_assessed": not warnings,
                    "model_distinct_as_assessed": True,
                    "admission_policy": ADMISSION_VERSION,
                    "admission_warnings": warnings,
                    "source_message_id": message_id,
                },
            )
        for descriptor in output["audits"]:
            claim = by_ref[descriptor["claim_ref"]]
            source = originals[claim["source_message_id"]]
            self.put(
                c,
                chat,
                record,
                "review_audit",
                {
                    **descriptor,
                    "claim_id": claim["claim_id"],
                    "claim_revision": 1,
                    "source_spans": spans(source, descriptor["source_unit_ids"]),
                    "origin": "model_descriptor",
                    "source_message_id": message_id,
                },
            )
        contract = output["output_contract"]
        count = requested_count(record["contract"]["question"])
        if count:
            contract["requested_count"] = count
            if re.search(
                r"\b(?:best|top)\s+(?:\d|two|three|four|five|six|seven|eight|nine|ten)\b",
                record["contract"]["question"],
                re.IGNORECASE,
            ):
                contract["deliverable"] = "ranked_approaches"
        if contract["deliverable"] == "ranked_approaches" and not output["families"]:
            raise ValueError(
                "An approach-ranking task requires at least one source-bound family, with any shortfall disclosed"
            )
        record.update(
            output_contract=contract,
            inventory=inventory,
            inventory_status=output["inventory_status"],
            inventory_limitations=output["inventory_limitations"],
        )
        if conflicts:
            record.setdefault("admission_notes", []).append(
                "Overlapping or equivalent approach families are preserved as disputed candidates and excluded from distinct-approach counts until a consistent current recheck."
            )
        if not inventory:
            record.update(
                inventory_status="partial",
                inventory_limitations="No material inventory supplied; only the admitted atomic assertions were selected",
            )

    def persist_audits(self, c, chat):
        record = self.record(c, chat)
        snap = self.snapshot(c, chat)
        existing = {
            x["input_hash"]
            for x in self.store.list(c, "review_audit_result", chat["mission_id"])
        }
        for result in snap["audit_results"]:
            if result["input_hash"] not in existing:
                self.put(c, chat, record, "review_audit_result", result)

    @staticmethod
    def link_references(snapshot, text):
        """Readable public links; structured IDs and original sources stay intact."""
        for index, claim in enumerate(snapshot["claims"], 1):
            text = text.replace(
                claim["claim_id"], f"[Assertion {index}](#{claim['source_message_id']})"
            )
        for index, finding in enumerate(snapshot["findings"], 1):
            text = text.replace(
                finding["id"], f"[Challenge {index}](#{finding['source_message_id']})"
            )
        return text

    def _admit(self, c, chat, turn, content, message_id):
        phase = turn["phase"]
        if phase == "opening":
            return super()._admit(c, chat, turn, content, message_id)
        check_envelope(content)
        record = self.record(c, chat)
        snap = self.snapshot(c, chat)
        try:
            if phase == "extraction" and record.get("route", {}).get("kind") == "delta":
                parsed, changes = parse_review_json(content)
                parsed, transport_changes = normalize_transport(
                    parsed, CouncilDeltaScope.model_json_schema()
                )
                changes += transport_changes
                scoped = CouncilDeltaScope.model_validate(parsed).model_dump()
                if set(scoped["claim_ids"]) != {
                    x["claim_id"] for x in snap["claims"]
                } or len(scoped["claim_ids"]) != len(set(scoped["claim_ids"])):
                    raise ValueError(
                        "Delta scope must address the exact affected dependency closure"
                    )
                if changes:
                    self.put(
                        c,
                        chat,
                        record,
                        "review_admission",
                        {
                            "policy": ADMISSION_VERSION,
                            "source_message_id": message_id,
                            "raw_content_hash": digest(content),
                            "normalized_output_hash": digest(scoped),
                            "changes": changes,
                            "origin": "deterministic_transport_normalization",
                        },
                    )
                if not scoped["within_claim_scope"]:
                    if chat["provider"] == "direct_council":
                        with_remaining = self.chat.runtime.reserved_remaining(c, chat)
                        self.chat.runtime.expand(
                            c,
                            chat,
                            max(0, 2 * len(chat["participants"]) + 7 - with_remaining),
                        )
                    self.new_cycle(
                        c, chat, record["contract"]["question"], continue_window=True
                    )
                    return (
                        "## Scope expanded\n\n"
                        + scoped["reason"]
                        + "\n\nThe council will use a full independent cycle; the scoping call remains counted."
                        + commentary_text(changes)
                    )
                record.update(
                    output_contract=scoped["output_contract"],
                    inventory_status="partial",
                    inventory_limitations="Targeted review of the selected assertions and their dependency closure; other approaches are outside this batch.",
                )
                record["revision"] += 1
                self.store.put(c, "chat_review", record)
                return (
                    "## Challenge scope\n\n"
                    + scoped["reason"]
                    + commentary_text(changes)
                )
            parsed, changes = parse_review_json(content)
            if phase == "extraction":
                parsed, extraction_changes = normalize_extraction(parsed)
                changes += extraction_changes
            parsed, transport_changes = normalize_transport(
                parsed, SCHEMAS[phase].model_json_schema()
            )
            changes += transport_changes
            output = SCHEMAS[phase].model_validate(parsed).model_dump()
            if phase == "recheck":
                output, closure_changes = normalize_recheck(output, snap)
                changes += closure_changes
                if closure_changes:
                    record["delivery_degraded"] = True
                    record.setdefault("delivery_warnings", []).append({
                        "phase": "recheck", "source_message_id": message_id,
                        "reason": "Some recheck claims or approach assessments could not be confirmed. Unresolved points remain open.",
                    })
            if phase == "extraction":
                units = {message["id"]: {unit["id"] for unit in self.source_units(message)}
                         for message in self.chat.messages(c, chat)
                         if message.get("phase") == "opening" and message.get("review_cycle") == record["cycle"]}
                output, inventory_changes = normalize_inventory(output, units)
                changes += inventory_changes
            if changes:
                self.put(
                    c,
                    chat,
                    record,
                    "review_admission",
                    {
                        "policy": ADMISSION_VERSION,
                        "source_message_id": message_id,
                        "raw_content_hash": digest(content),
                        "normalized_output_hash": digest(output),
                        "changes": changes,
                        "origin": "deterministic_transport_normalization",
                    },
                )
            if phase == "scrutiny":
                current = {x["claim_id"]: x for x in snap["claims"]}
                evidence = {e["id"]: e for e in snap["evidence"]}
                if len(output["findings"]) != len(current) or {
                    f["claim_id"] for f in output["findings"]
                } != set(current):
                    raise ValueError(
                        "Challenges must cover every material assertion exactly once"
                    )
                for finding in output["findings"]:
                    if finding["claim_revision"] != current[finding["claim_id"]][
                        "revision"
                    ] or any(
                        e not in evidence
                        or evidence[e]["claim_id"] != finding["claim_id"]
                        or evidence[e]["claim_revision"] != finding["claim_revision"]
                        for e in finding["evidence_ids"]
                    ):
                        raise ValueError(
                            "A challenge references stale assertions or unrelated evidence"
                        )
                    self.put(
                        c,
                        chat,
                        record,
                        "review_finding",
                        {
                            **finding,
                            "reviewer": turn["participant"],
                            "source_message_id": message_id,
                        },
                    )
                record["scrutiny_limitations"] = output["limitations"]
            elif phase == "extraction":
                self.extract(c, chat, record, output, message_id)
                if changes:
                    record.setdefault("admission_notes", []).append(
                        "Transport adjustments and supplemental commentary are retained in the admission record. Nonstandard reasoning labels remain unclear; a null audit tolerance remains unknown."
                    )
                    if any(change.get("kind") == "missing_observation_rationale" for change in changes):
                        record["admission_notes"].append(
                            "Some observation classification rationales were not supplied by the extractor; those observations remain unverified and their assessment is incomplete."
                        )
                    if any(change.get("kind") == "unlinked_inventory_note" for change in changes):
                        record["admission_notes"].append(
                            "Unlinked auxiliary inventory entries remain saved as unverified notes; they are excluded from the linked inventory."
                        )
            elif phase == "repair":
                # The current DTO has already validated the reply. Reuse the
                # author/revision algorithm without re-parsing legacy DTOs.
                self.apply_current_repairs(
                    c, chat, record, snap, turn, output, message_id
                )
                record["revision"] += 1
                rendered = self.readable("repair", {"repairs": output["repairs"]})
                for peer in output["peer_challenges"]:
                    claim = next(
                        x for x in snap["claims"] if x["claim_id"] == peer["claim_id"]
                    )
                    if (
                        claim["author_id"] == turn["author_id"]
                        or claim["revision"] != peer["claim_revision"]
                    ):
                        raise ValueError(
                            "Peer objection must target another author's current assertion"
                        )
                    if len(snap["findings"]) + len(output["peer_challenges"]) > 24:
                        raise ValueError(
                            "Peer finding batch exceeds the bounded recheck capacity"
                        )
                    self.put(
                        c,
                        chat,
                        record,
                        "review_finding",
                        {
                            **peer,
                            "origin": "peer_challenge",
                            "reviewer": turn["participant"],
                            "source_message_id": message_id,
                            "steelman": claim["text"],
                            "minimum_resolution": peer["decision_impact"],
                            "checks": [],
                            "evidence_ids": [],
                            "target": claim["text"],
                            "in_scope_reason": peer["decision_impact"],
                            "concern_kind": "new_issue",
                            "test": {
                                "method": peer["candidate_test"],
                                "disconfirming_outcome": "Not yet specified",
                                "baseline": "Requires assessment",
                                "threshold_basis": "Unknown",
                                "limitations": "Unreviewed peer challenge",
                            },
                        },
                    )
                record["revision"] += 1
                final_text = (
                    "## Response and revision\n\n"
                    + output["explanation"]
                    + "\n\n"
                    + rendered
                    + self.peer_text(output)
                    + commentary_text(changes)
                )
                if turn["author_id"] != turn["participant"]["id"]:
                    original_author = next(
                        p["name"]
                        for p in chat["participants"]
                        if p["id"] == turn["author_id"]
                    )
                    final_text = (
                        "Response supplied by "
                        + turn["participant"]["name"]
                        + " for the unavailable original author "
                        + original_author
                        + ".\n\n"
                        + final_text
                    )
                final_text = self.link_references(self.snapshot(c, chat), final_text)
                self.scan(c, chat, record, {"id": message_id, "content": final_text})
                self.store.put(c, "chat_review", record)
                self.persist_audits(c, chat)
                return final_text
            elif phase == "recheck":
                self.recheck(c, chat, record, snap, output, message_id)
                if not turn.get("focused"):
                    self.choose_focus(c, chat, record)
            else:
                rendered = self.render_synthesis(snap, output)
                if any(
                    change.get("kind") == "supplementary_commentary"
                    for change in changes
                ):
                    rendered += "\n\nSupplementary model commentary was retained in the admission record and is outside the reviewed answer."
                return self.publish(
                    c,
                    chat,
                    record,
                    snap,
                    message_id,
                    rendered,
                    False,
                    output["answer_disposition"],
                )
        except (
            ValueError,
            ValidationError,
            KeyError,
            TypeError,
            StopIteration,
            RecursionError,
            DomainError,
        ) as exc:
            if isinstance(exc, DomainError) and not exc.__cause__:
                raise
            if phase == "synthesis":
                return self.publish(
                    c,
                    chat,
                    record,
                    snap,
                    message_id,
                    self.fallback(snap),
                    True,
                    "comparison_only",
                    str(exc),
                )
            raise DomainError(
                failure_message(phase, exc),
                422,
            ) from exc
        record["revision"] += 1
        self.store.put(c, "chat_review", record)
        self.persist_audits(c, chat)
        rendered = self.link_references(
            self.snapshot(c, chat),
            self.readable(phase, output) + commentary_text(changes),
        )
        if phase == "extraction" and record.get("admission_notes"):
            rendered += "\n\nReview input notes: " + " ".join(record["admission_notes"])
        return rendered

    def apply_current_repairs(
        self, c, chat, record, snapshot, turn, output, message_id
    ):
        for repair in output["repairs"]:
            if (
                repair["action"] in ("narrow", "revise")
                and not repair["revised_scope"].strip()
            ):
                raise ValueError("A scoped revision requires an explicit revised_scope")
        self.repair(c, chat, record, snapshot, turn, output, message_id)
        for item in self.store.list(c, "review_claim", chat["mission_id"]):
            if item.get("repair_message_id") != message_id:
                continue
            repair = next(
                value
                for value in output["repairs"]
                if value["claim_id"] == item["claim_id"]
            )
            item.update(
                assertion=item["text"],
                scope=repair["revised_scope"] or item["scope"],
                dependency_versions={
                    dep: next(
                        value["revision"]
                        for value in snapshot["claims"]
                        if value["claim_id"] == dep
                    )
                    for dep in item.get("dependencies", [])
                },
            )
            self.store.put(c, "review_claim", item)

    @staticmethod
    def peer_text(output):
        return "".join(
            "\n\n### Challenge to "
            + p["claim_id"]
            + "\n\n"
            + p["objection"]
            + "\n\nWhy it matters: "
            + p["decision_impact"]
            for p in output.get("peer_challenges", [])
        )

    def recheck(self, c, chat, record, snapshot, output, message_id):
        answered = {f for repair in snapshot["repairs"] for f in repair["finding_ids"]}
        peers = {
            f["id"]
            for f in snapshot["findings"]
            if f.get("origin") in ("peer_challenge", "recheck_concern")
        }
        for assessment in output["assessments"]:
            if assessment["finding_id"] in peers - answered and assessment[
                "resolution"
            ] not in ("withdrawn", "unresolved_as_assessed"):
                assessment.update(
                    resolution="unresolved_as_assessed",
                    closure_basis="no_effective_change",
                    comparison="The original author has not answered this late peer challenge. "
                    + assessment["comparison"],
                )
        super().recheck(c, chat, record, snapshot, output, message_id)
        current = {x["claim_id"]: x["revision"] for x in snapshot["claims"]}
        families = {x["id"]: x for x in snapshot.get("families", [])}
        supplied = {item["family_id"] for item in output.get("families", [])}
        for family in families.values():
            if family["id"] not in supplied:
                family["recheck_state"] = "not_reviewed"
                family["recheck_reason"] = "No valid current approach assessment was supplied."
        for assessment in output.get("families", []):
            family = families[assessment["family_id"]]
            ids, versions = assessment["claim_ids"], assessment["claim_revisions"]
            if (
                len(ids) != len(set(ids))
                or len(ids) != len(versions)
                or set(ids) != {x["claim_id"] for x in family["members"]}
                or any(current[cid] != v for cid, v in zip(ids, versions, strict=True))
            ):
                raise ValueError("Family assessment has unrelated or stale members")
            family.update(
                members=[
                    {"claim_id": cid, "revision": v}
                    for cid, v in zip(ids, versions, strict=True)
                ],
                distinct_as_assessed=assessment["still_distinct_as_assessed"],
                model_distinct_as_assessed=assessment["still_distinct_as_assessed"],
                recheck_reason=assessment["reason"],
                recheck_message_id=message_id,
                recheck_state="complete_as_assessed",
            )
            family.setdefault("assessment_history", []).append(
                {
                    "members": family["members"],
                    "distinct_as_assessed": family["distinct_as_assessed"],
                    "model_distinct_as_assessed": family["model_distinct_as_assessed"],
                    "reason": assessment["reason"],
                    "source_message_id": message_id,
                    "stage": "recheck",
                }
            )
            self.store.put(c, "review_family", family)
        # A model's boolean cannot make contradictory/duplicate current groups
        # count as distinct. Keep both proposals and the attributed assessment.
        conflicts = family_conflicts(
            [
                {
                    "key": family["id"],
                    "members": {m["claim_id"] for m in family["members"]},
                    "mechanism": family["mechanism"],
                }
                for family in families.values()
                if family["model_distinct_as_assessed"]
            ],
            [
                {m["claim_id"] for m in group["members"]}
                for group in snapshot.get("groups", [])
                if group["relation"] == "equivalent_as_assessed"
                and not group.get("stale")
            ],
        )
        for family in families.values():
            warnings = conflicts.get(family["id"], [])
            family["admission_warnings"] = warnings
            if warnings:
                family["distinct_as_assessed"] = False
                if family["assessment_history"][-1].get("source_message_id") == message_id:
                    family["assessment_history"][-1].update(
                        distinct_as_assessed=False,
                        model_distinct_as_assessed=family["model_distinct_as_assessed"],
                        admission_warnings=warnings,
                    )
            self.store.put(c, "review_family", family)

    def choose_focus(self, c, chat, record):
        if record.get("delivery_degraded"):
            record["focused_authors"] = []
            record["focus_decision"] = {
                "authors": [], "reason": "Review incomplete; preserve unresolved issues and synthesize without a format-repair round",
                "recorded_at": now(),
            }
            self.save_plan(c, chat, record)
            return
        findings = [
            x
            for x in self.store.list(c, "review_finding", chat["mission_id"])
            if x.get("review_cycle") == record["cycle"]
        ]
        claims = {x["claim_id"]: x for x in self.snapshot(c, chat)["claims"]}
        # Promote late material concerns to actual findings before scheduling.
        # They stay open even when the optional exchange cannot fit.
        for concern in self.store.list(c, "review_concern", chat["mission_id"]):
            if (
                concern.get("review_cycle") != record["cycle"]
                or concern["kind"] != "new_issue"
                or concern.get("review_state") != "not_reviewed"
                or len(findings) >= 24
            ):
                continue
            original = next(f for f in findings if f["id"] == concern["finding_id"])
            finding = self.put(
                c,
                chat,
                record,
                "review_finding",
                {
                    **{
                        k: v
                        for k, v in original.items()
                        if k
                        not in (
                            "id",
                            "mission_id",
                            "chat_id",
                            "review_cycle",
                            "schema_version",
                            "created_at",
                        )
                    },
                    "claim_revision": claims[concern["claim_id"]]["revision"],
                    "objection": concern["detail"],
                    "minimum_resolution": "Answer the new issue within "
                    + concern["affected_scope"],
                    "origin": "recheck_concern",
                    "materiality": concern["materiality"],
                    "source_message_id": concern["source_message_id"],
                    "concern_id": concern["id"],
                },
            )
            concern.update(
                review_state="promoted_to_finding", promoted_finding_id=finding["id"]
            )
            self.store.put(c, "review_concern", concern)
            findings.append(finding)
        assessments = {x["finding_id"]: x for x in record["rechecks"]}
        authors = []
        for f in findings:
            a = assessments.get(f["id"], {})
            material = (
                f.get("origin") == "peer_challenge"
                or (
                    f.get("origin") == "recheck_concern"
                    and f.get("materiality") == "decision_changing"
                )
                or any(
                    x["materiality"] == "decision_changing"
                    for x in a.get("concerns", [])
                )
            )
            claim = claims[f["claim_id"]]
            if (
                material
                and a.get("resolution", "unresolved_as_assessed")
                == "unresolved_as_assessed"
                and claim["lifecycle"] != "withdrawn"
                and claim["author_id"] not in chat.get("unavailable_members", {})
                and claim["author_id"] not in authors
            ):
                authors.append(claim["author_id"])
        authors = authors[:2]
        reason = "No bounded decision-changing issue requires another author response"
        if authors:
            extra = len(authors) + 1
            try:
                self.chat.runtime.expand(c, chat, extra)
                record["focused_authors"] = authors
                reason = (
                    "One focused exchange addresses recorded decision-changing findings"
                )
            except DomainError as exc:
                reason = "Focused exchange omitted: " + exc.message
        record["focus_decision"] = {
            "authors": record.get("focused_authors", []),
            "reason": reason,
            "recorded_at": now(),
        }
        self.save_plan(c, chat, record)

    def render_synthesis(self, snapshot, output):
        for block in output["blocks"]:
            cues = observation_cues({"id": "generated-final", "content": block["text"]})
            if any(
                cue["classification"] == "unsupported_self_report"
                and re.search(
                    r"\b(?:I|we)\s+(?:tested|measured|ran)\b|\b(?:test|run|copy|restore) took\b",
                    cue["text"],
                    re.IGNORECASE,
                )
                for cue in cues
            ):
                raise ValueError(
                    "The final introduces an unlinked self-reported execution result"
                )
        families = {
            x["id"]: x
            for x in snapshot.get("families", [])
            if not x["stale"] and x.get("distinct_as_assessed", True)
        }
        ranked = output.get("ranked_approaches", [])
        refs = [x["family_id"] for x in ranked]
        if len(refs) != len(set(refs)) or not set(refs) <= set(families):
            raise ValueError(
                "Ranked approaches must use current distinct families exactly once"
            )
        target = snapshot.get("output_contract") or {}
        if target.get("deliverable") == "ranked_approaches" and not ranked and families:
            raise ValueError("The requested ranked deliverable was omitted")
        count = target.get("requested_count")
        if (
            target.get("deliverable") == "ranked_approaches"
            and count
            and len(ranked) < count
            and not output.get("deliverable_limitations")
        ):
            raise ValueError("A shortfall in distinct approaches must be explained")
        for item in ranked:
            member_ids = {m["claim_id"] for m in families[item["family_id"]]["members"]}
            if not any(member_ids & set(b["claim_ids"]) for b in output["blocks"]):
                raise ValueError(
                    "Ranked family has no current claim-linked answer block"
                )
            decisions = {d["claim_id"]: d for d in snapshot["decisions"]}
            if any(decisions[cid]["permission"] == "withdrawn" for cid in member_ids):
                raise ValueError(
                    "Withdrawn assertions cannot appear as a positively ranked approach"
                )
            if output["answer_disposition"] in (
                "recommendation",
                "conditional_choice",
            ) and any(
                not decisions[cid]["decision_suitability"].startswith(
                    "recommendation_eligible"
                )
                for cid in member_ids
            ):
                raise ValueError(
                    "A ranked recommendation includes an ineligible assertion"
                )
        rendered = super().render_synthesis(snapshot, output)
        if ranked:
            lines = ["## Ranked approaches", ""]
            for i, item in enumerate(ranked, 1):
                family = families[item["family_id"]]
                lines += [f"{i}. **{family['name']}** — {item['reason']}"]
                member_ids = {m["claim_id"] for m in family["members"]}
                lines += [
                    "   Review status: "
                    + "; ".join(
                        dict.fromkeys(
                            d["label"]
                            for d in snapshot["decisions"]
                            if d["claim_id"] in member_ids
                        )
                    )
                ]
            rendered = "\n".join(lines) + "\n\n" + rendered
        if output.get("deliverable_limitations"):
            rendered += "\n\nDeliverable limits: " + output["deliverable_limitations"]
        if snapshot.get("route", {}).get("kind") == "explain":
            rendered = (
                "Explanation of the saved review. No new checks were performed.\n\n"
                + rendered
            )
        return self.link_references(
            snapshot,
            rendered
            + "\n\nReview coverage: "
            + (snapshot.get("inventory_limitations") or "Not assessed"),
        )

    def fallback(self, snapshot):
        return self.link_references(
            snapshot,
            super().fallback(snapshot)
            + "\n\nReview coverage: "
            + (snapshot.get("inventory_limitations") or "Not assessed"),
        )

    def readable(self, phase, output):
        if phase == "scrutiny":
            rendered = super().readable(phase, output)
            notes = [
                f"**{finding['claim_id']}**: {finding['evidence_obligation']}"
                for finding in output["findings"]
                if finding.get("evidence_obligation")
            ]
            if notes:
                rendered += "\n\nEvidence notes (model commentary):\n\n" + "\n\n".join(
                    notes
                )
            return rendered
        if phase == "repair" and output.get("explanation"):
            return (
                output["explanation"]
                + "\n\n"
                + super().readable(phase, output)
                + self.peer_text(output)
            )
        return super().readable(phase, output)

    def demo(self, c, chat, messages, turn):
        phase = turn["phase"]
        record = self.record(c, chat)
        if phase == "extraction" and record.get("route", {}).get("kind") == "delta":
            return json.dumps(
                {
                    "claim_ids": [
                        x["claim_id"] for x in self.snapshot(c, chat)["claims"]
                    ],
                    "within_claim_scope": True,
                    "reason": "This explicit challenge targets the existing declared scope.",
                    "output_contract": {"deliverable": "answer"},
                }
            )
        demo_chat = {**chat, "original_prompt": record["contract"]["question"]} if chat.get("context_branch_id") else chat
        raw = super().demo(c, demo_chat, messages, turn)
        if phase == "opening":
            return raw
        out = json.loads(raw)
        snap = self.snapshot(c, chat)
        if phase == "extraction":
            out.update(
                output_contract={
                    "deliverable": "answer",
                    "requested_count": requested_count(snap["contract"]["question"]),
                    "criteria": [],
                    "assumptions": [],
                },
                inventory=[
                    {
                        "source_message_id": x["source_message_id"],
                        "source_unit_ids": x["source_unit_ids"],
                        "category": "other",
                        "description": "Illustrative workflow assertion, not a quality finding",
                        "claim_refs": [x["ref"]],
                    }
                    for x in out["claims"]
                ],
                inventory_status="partial",
                inventory_limitations="Synthetic workflow example only; source selection is incomplete",
                audits=[],
                families=[
                    {
                        "name": "Scripted workflow demonstration",
                        "mechanism": "A scripted demonstration of the same generic workflow",
                        "refs": [x["ref"] for x in out["claims"]],
                        "assumptions": "Scripted inputs, no independent semantic validation",
                        "resources": "Local fixture, no inference",
                        "distinguishing_test": "Independent real-task evaluation is needed",
                    }
                ],
            )
        elif phase == "repair":
            out.update(
                explanation="I retain the bounded workflow proposal and its stated uncertainty. This scripted reply is not quality evidence.",
                peer_challenges=[],
            )
        elif phase == "recheck":
            # The legacy demo creates one assessment per finding, including any
            # deliberately injected peer finding in workflow tests.
            versions = {x["claim_id"]: x["revision"] for x in snap["claims"]}
            out["families"] = [
                {
                    "family_id": f["id"],
                    "claim_ids": [m["claim_id"] for m in f["members"]],
                    "claim_revisions": [versions[m["claim_id"]] for m in f["members"]],
                    "still_distinct_as_assessed": True,
                    "reason": "One illustrative scripted family; not independent scientific evidence",
                }
                for f in snap.get("families", [])
            ]
        elif phase == "synthesis":
            out.update(
                ranked_approaches=[
                    {
                        "family_id": f["id"],
                        "reason": "A bounded scripted example, conditional on independent evaluation",
                    }
                    for f in snap.get("families", [])
                    if not f["stale"]
                ]
                if (snap.get("output_contract") or {}).get("deliverable")
                == "ranked_approaches"
                else [],
                deliverable_limitations="This synthetic example does not establish independent approach quality.",
            )
        return json.dumps(out)

    def followup(self, c, chat, body):
        if chat["status"] != "completed" or chat.get("active_turn"):
            raise DomainError(
                "Finish or pause the current request before asking for a targeted follow-up",
                409,
            )
        if body.action == "explain":
            record = self.record(c, chat)
            self.chat.runtime.begin_window(c, chat, 4, "explicit_explanation")
            record.update(
                route={
                    "kind": "explain",
                    "reason": "Explicit explanation of the saved review",
                },
                synthesis_stale=True,
                revision=record["revision"] + 1,
            )
            chat.update(
                generation=chat["generation"] + 1,
                status="running",
                final_message_id=None,
                accepted=False,
                error=None,
                requested_finish=False,
                revision=chat["revision"] + 1,
            )
            self.save_plan(c, chat, record)
            self.chat.message(
                c,
                chat,
                role="user",
                phase="intervention",
                content=body.text,
                review_cycle=record["cycle"],
            )
            self.store.put(c, "chat", chat)
            self.research.enqueue(c, "chat", chat)
            return self.chat.view(c, chat["id"])
        snap = self.snapshot(c, chat)
        claims = {x["claim_id"]: x for x in snap["claims"]}
        if not body.claim_ids or not set(body.claim_ids) <= set(claims):
            raise DomainError(
                "Choose actual current assertions for a targeted challenge, or send a normal message for a full review",
                422,
            )
        selected = set(body.claim_ids)
        while True:
            expanded = selected | {
                dep for cid in selected for dep in claims[cid].get("dependencies", [])
            }
            expanded |= {
                cid
                for cid, x in claims.items()
                if set(x.get("dependencies", [])) & selected
            }
            if expanded == selected:
                break
            selected = expanded
        authors = list(
            dict.fromkeys(claims[cid]["author_id"] for cid in claims if cid in selected)
        )
        route = {
            "kind": "delta",
            "reason": "Explicit selected-assertion challenge including dependency closure",
            "claim_ids": sorted(selected),
            "authors": authors,
        }
        return self.new_cycle(c, chat, body.text, route=route, carry=snap)

    def new_cycle(
        self,
        c,
        chat,
        question,
        options=None,
        expected=None,
        *,
        route=None,
        carry=None,
        continue_window=False,
        context_override=None,
        message_metadata=None,
    ):
        record = self.record(c, chat)
        if expected is not None:
            self.store.check(record, expected)
        if not continue_window and (
            chat.get("active_turn") or chat["status"] in ("running", "waiting")
        ):
            raise DomainError(
                "Pause and wait for the active request before changing the council scope",
                409,
            )
        route = route or {
            "kind": "full",
            "reason": "New or unbounded free-form request",
        }
        required = (
            (len(route["authors"]) + 7)
            if route["kind"] == "delta"
            else 2 * len(chat["participants"]) + 7
        )
        if not continue_window:
            self.chat.runtime.begin_window(
                c, chat, required, "explicit_council_followup"
            )
        previous = self.snapshot(c, chat)
        previous_messages = self.chat.messages(c, chat)
        prior_answer = next(
            (m for m in previous_messages if m["id"] == chat.get("final_message_id")),
            None,
        )
        checkpoint = {
            "version": "conversation-checkpoint/1",
            "source_cycle": record["cycle"],
            "source_generation": chat["generation"],
            "completed": chat["status"] == "completed",
            "stale": bool(record.get("synthesis_stale") or record.get("stale")),
            "prior_question": record["contract"]["question"],
            "prior_answer": {
                "message_id": prior_answer["id"],
                "text": prior_answer["content"],
            }
            if prior_answer
            else None,
            "prior_assertions": [
                {
                    "historical_claim_id": x["claim_id"],
                    **{
                        k: x.get(k)
                        for k in (
                            "revision",
                            "text",
                            "scope",
                            "assumptions",
                            "lifecycle",
                            "dependencies",
                            "dependency_versions",
                            "author_id",
                        )
                    },
                }
                for x in previous["claims"]
            ],
            "prior_concerns": [
                {
                    "historical_finding_id": x["id"],
                    **{
                        k: x.get(k)
                        for k in (
                            "claim_id",
                            "claim_revision",
                            "objection",
                            "minimum_resolution",
                            "candidate_test",
                        )
                    },
                }
                for x in previous["findings"]
            ],
            "prior_assessments": previous["rechecks"],
            "rule": "Historical public context for continuity, not new evidence or current-cycle authority. Preserve its qualifiers and unresolved concerns. Re-evaluate prior recommendations under the new request. Historical IDs cannot substitute for current source, assertion or finding IDs. Current-cycle independent replies are not shared during openings. The original transcript remains saved.",
        }
        record.setdefault("history", []).append(
            {
                "cycle": record["cycle"],
                "contract": record["contract"],
                "contract_hash": record["contract_hash"],
                "decision_hash": previous["decision_hash"],
            }
        )
        cycle = record["cycle"] + 1
        text = self.research.artifacts.redact(question.strip())
        from .council_message_edits import root_question
        root = root_question(self.chat, c, chat)
        combined = (
            root + "\n\nCurrent director request:\n" + text
            if text != root
            else text
        )
        if context_override is not None:
            combined = context_override["question"]
            checkpoint = context_override["checkpoint"]
        record.update(
            cycle=cycle,
            revision=record["revision"] + 1,
            coverage=[],
            rechecks=[],
            reassignments=[],
            skipped_keys=[],
            partial_reasons=[],
            stale=False,
            synthesis_stale=True,
            focused_authors=[],
            focus_decision=None,
            inventory=[],
            inventory_status="partial",
            inventory_limitations="Material inventory has not been assessed",
            output_contract={},
            delivery_degraded=False,
            delivery_warnings=[],
            route=route,
            conversation_checkpoint=checkpoint,
            conversation_checkpoint_hash=digest(checkpoint),
        )
        record["contract"] = self.contract(
            chat, combined, options or record["contract"]["options"], cycle
        )
        record["contract_hash"] = digest(record["contract"])
        chat.update(
            review_cycle=cycle,
            generation=chat["generation"] + 1,
            final_message_id=None,
            requested_finish=False,
            accepted=False,
            status="running",
            error=None,
            retry_wait=None,
            unavailable_members={
                key: value
                for key, value in chat.get("unavailable_members", {}).items()
                if value.get("kind") == "director_excluded"
            },
            revision=chat["revision"] + 1,
        )
        self.store.put(c, "chat_review", record)
        if carry:
            selected = set(route["claim_ids"])
            for claim in carry["claims"]:
                if claim["claim_id"] in selected:
                    values = {
                        k: v
                        for k, v in claim.items()
                        if k
                        not in (
                            "id",
                            "mission_id",
                            "chat_id",
                            "review_cycle",
                            "created_at",
                            "schema_version",
                        )
                    }
                    self.put(
                        c,
                        chat,
                        record,
                        "review_claim",
                        {**values, "inherited_from_cycle": carry["cycle"]},
                    )
            for kind, key in (
                ("review_evidence", "evidence"),
                ("review_audit", "audit_descriptors"),
            ):
                for value in carry.get(key, []):
                    if value["claim_id"] in selected:
                        data = {
                            k: v
                            for k, v in value.items()
                            if k
                            not in (
                                "id",
                                "mission_id",
                                "chat_id",
                                "review_cycle",
                                "created_at",
                                "schema_version",
                            )
                        }
                        self.put(
                            c,
                            chat,
                            record,
                            kind,
                            {**data, "inherited_from_id": value["id"]},
                        )
        self.save_plan(c, chat, record)
        step = self.store.get(c, chat["step_id"], "step")
        step.update(paused=False, status="committing")
        self.store.put(c, "step", step)
        self.store.put(c, "chat", chat)
        c.execute(
            "UPDATE jobs SET state='cancelled' WHERE target_id=? AND state='queued'",
            (chat["id"],),
        )
        if not continue_window:
            self.chat.message(
                c,
                chat,
                role="user",
                content=text,
                review_cycle=cycle,
                **{"phase": "intervention", **(message_metadata or {})},
            )
        self.research.enqueue(c, "chat", chat)
        self.store.event(
            c,
            chat["mission_id"],
            "council.scope_revised",
            {
                "chat_id": chat["id"],
                "cycle": cycle,
                "route": route,
                "contract_hash": record["contract_hash"],
                "continued_window": continue_window,
            },
        )
        return self.chat.view(c, chat["id"])
