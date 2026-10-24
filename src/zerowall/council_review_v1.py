"""Generic, versioned claim scrutiny built on the existing chat/store/executor."""

import json
import re

from pydantic import ValidationError

from .contracts import (
    ClaimExtraction,
    RecheckOutput,
    RepairOutput,
    ReviewOptions,
    ScrutinyOutput,
    SynthesisDraft,
)
from .db import DomainError, digest, now, uid
from .provider import parse_json
from .review_policy_v1 import POLICY_VERSION, ledger_markdown, publication_decisions

SCHEMAS = {
    "extraction": ClaimExtraction,
    "scrutiny": ScrutinyOutput,
    "repair": RepairOutput,
    "recheck": RecheckOutput,
    "synthesis": SynthesisDraft,
}
INSTRUCTIONS = {
    "opening": "Answer the question independently without peer replies. Give a useful concise public answer, its material claims, explicit assumptions, rationale, limitations and a test where appropriate. Do not invent source IDs or claim experiments ran. Use at most four central claims. Return readable Markdown, not JSON.",
    "extraction": "Select one to four material source passages per opening from supplied source_units. Set source_unit_id to an actual unit ID and source_message_id to its actual message. Leave quote empty: the server supplies verbatim text, so do not copy or paraphrase it. Preserve qualifiers by selecting complete assertions; mark coverage partial when context or fragments omit material. Use distinct refs C1, C2 etc. Record coverage for EVERY opening, including omitted material and limits. complete_as_assessed is your opinion, not a completeness guarantee. Do not judge claims or invent dependencies. Return the specified JSON object.",
    "scrutiny": "Act as a falsification critic, not a competing proposer or final judge. For EVERY supplied claim, steelman it, target the strongest technically valid objection, and give an in-scope candidate counterexample/test or explain why one cannot be constructed. Apply relevant reasoning, explicit constraints, resources, evidence, feasibility and calibration checks; mark irrelevant checks not_applicable with reasons. Do not impose physics on unrelated tasks. Unknown evidence is unknown, not false. Novelty alone is not an objection. Minimum resolution may specify a repair condition, not a replacement solution. Your verdicts are model opinions. Return the specified JSON object.",
    "repair": "Respond ONLY for your assigned original author's claims to every actual finding. Retain, rebut, narrow, revise or withdraw each claim. A replacement responder must disclose that attribution. Preserve the original goal; make changed assumptions explicit. New ideas outside scope remain unreviewed. Set revised_text for narrow/revise, preserving limitations, at most 1600 characters and preferably below 400. Cite actual finding IDs. State remaining uncertainty. Return the specified JSON object.",
    "recheck": "Assess EVERY supplied finding against the actual author replies and CURRENT claim revisions. A critic can be wrong: evaluate both sides fairly. A fluent reply is not evidence. Report only proposed dispositions, concrete reasons and remaining limitations. You cannot approve execution, certify truth or grant trusted verification. Return the specified JSON object.",
    "synthesis": "Answer the director directly using only current supplied claims. Each substantive block must reference claim IDs. Respect server-computed permission: supported section only for supported claims; contradicted/withdrawn claims only in withdrawn or next_tests. Unresolved proposals may appear as conditional recommendations in direct_answer or conditional; the application will explicitly label their unresolved objections. Do not present them as established. Preserve minority views, coverage limits and unknowns. Evidence IDs must be supplied links, never invented. Do not claim consensus proves truth or that a candidate test was executed. You are writing generated text, not server labels. Return the specified JSON object.",
}


class CouncilReview:
    claims_per_author_limit = 4

    def __init__(self, chat_service):
        self.chat = chat_service
        self.research = chat_service.research
        self.store = self.research.store

    def record(self, c, chat):
        return self.store.get(c, chat["review_id"], "chat_review")

    def source_units(self, message):
        units = []
        text = message["content"]
        for line in re.finditer(r"[^\n]+", text):
            start, end = line.span()
            while start < end:
                stop = min(end, start + 400)
                if stop < end:
                    boundary = text.rfind(" ", start + 150, stop)
                    if boundary > start:
                        stop = boundary
                value = text[start:stop]
                if len(value.strip()) >= 3:
                    units.append(
                        {
                            "id": message["id"] + ":u" + str(len(units) + 1),
                            "message_id": message["id"],
                            "start": start,
                            "end": stop,
                            "text": value,
                            "fragment": start != line.start() or stop != end,
                        }
                    )
                start = stop
        return units

    @staticmethod
    def roles_for(members):
        preferred = {p.get("provider"): p["id"] for p in members}
        return {
            "extraction": preferred.get("gemini", members[0]["id"]),
            "scrutiny": preferred.get("groq", members[1]["id"]),
            "recheck": preferred.get("nvidia_nim", members[-1]["id"]),
            "synthesis": preferred.get("gemini", members[0]["id"]),
        }

    def initialize(self, c, chat, options):
        roles = self.roles_for(chat["participants"])
        record = {
            "id": uid("review"),
            "mission_id": chat["mission_id"],
            "chat_id": chat["id"],
            "revision": 1,
            "cycle": 1,
            "stale": False,
            "synthesis_stale": False,
            "roles": roles,
            "reassignments": [],
            "coverage": [],
            "rechecks": [],
            "partial_reasons": [],
            "contract": self.contract(chat, chat["original_prompt"], options, 1),
            "history": [],
        }
        record["contract_hash"] = digest(record["contract"])
        record["roles_hash"] = digest(roles)
        self.store.put(c, "chat_review", record)
        chat["review_id"] = record["id"]
        chat["review_cycle"] = 1
        self.store.put(c, "chat", chat)

    def contract(self, chat, question, options, revision):
        return self.research.artifacts.redact(
            {
                "protocol_version": "reviewed_v1",
                "prompt_version": "generic-review-v1",
                "policy_version": POLICY_VERSION,
                "question": question,
                "options": options.model_dump()
                if isinstance(options, ReviewOptions)
                else options,
                "participants": chat["participants"],
                "revision": revision,
                "claims_per_author": 4,
                "planned_calls": 2 * len(chat["participants"]) + 4,
                "retry_allowance": 3,
                "provider": chat["provider"],
                "additional_payments_usd": 0,
            }
        )

    def validate(self, record):
        if (
            digest(record["contract"]) != record["contract_hash"]
            or digest(record["roles"]) != record["roles_hash"]
        ):
            raise DomainError(
                "Review contract or role assignment changed outside a governed transition",
                422,
            )

    def schedule(self, chat, record):
        cycle = record["cycle"]
        members = {p["id"]: p for p in chat["participants"]}
        steps = [("opening", p["id"], None) for p in chat["participants"]]
        steps += [
            (phase, record["roles"][phase], None)
            for phase in ("extraction", "scrutiny")
        ]
        replacements = {
            x["original_author_id"]: x["participant_id"]
            for x in record["reassignments"]
            if x["phase"] == "repair"
        }
        steps += [
            ("repair", replacements.get(p["id"], p["id"]), p["id"])
            for p in chat["participants"]
        ]
        steps += [
            ("recheck", record["roles"]["recheck"], None),
            ("synthesis", record["roles"]["synthesis"], None),
        ]
        turns = []
        for phase, member, author in steps:
            key = f"review:{cycle}:{phase}:" + (author or member)
            if phase == "synthesis":
                key += ":" + str(chat["generation"])
            turns.append(
                {
                    "phase": phase,
                    "round": cycle,
                    "participant": members[member],
                    "author_id": author,
                    "key": key,
                    "cycle": cycle,
                }
            )
        return turns

    def next_turn(self, c, chat, messages):
        record = self.record(c, chat)
        self.validate(record)
        done = {m.get("turn_key") for m in messages}
        skipped = set(record.get("skipped_keys", []))
        for turn in self.schedule(chat, record):
            if turn["phase"] in ("opening", "repair") and turn["participant"][
                "id"
            ] in chat.get("unavailable_members", {}):
                continue
            if chat.get("requested_finish") and turn["phase"] != "synthesis":
                continue
            if turn["key"] not in done and turn["key"] not in skipped:
                return turn
        return None

    def remaining(self, c, chat, messages):
        record = self.record(c, chat)
        done = {m.get("turn_key") for m in messages} | set(
            record.get("skipped_keys", [])
        )
        return sum(
            t["key"] not in done
            and (not chat.get("requested_finish") or t["phase"] == "synthesis")
            and not (
                t["phase"] in ("opening", "repair")
                and t["participant"]["id"] in chat.get("unavailable_members", {})
            )
            for t in self.schedule(chat, record)
        )

    def snapshot(self, c, chat):
        record = self.record(c, chat)
        self.validate(record)

        def items(kind):
            return [
                x
                for x in self.store.list(c, kind, chat["mission_id"])
                if x.get("review_cycle") == record["cycle"]
            ]

        versions = items("review_claim")
        current = {}
        for claim in versions:
            if claim["revision"] > current.get(claim["claim_id"], {}).get(
                "revision", 0
            ):
                current[claim["claim_id"]] = claim
        evidence = items("review_evidence")
        for e in evidence:
            try:
                self.research.artifacts.read(
                    self.store.get(c, e["artifact_id"], "artifact")
                )
                e["integrity"] = "pass"
            except (DomainError, OSError):
                e["integrity"] = "invalid"
        result = {
            **record,
            "claims": list(current.values()),
            "claim_history": versions,
            "findings": items("review_finding"),
            "repairs": items("review_repair"),
            "dispositions": items("review_disposition"),
            "evidence": evidence,
            "assessment_origin": "model assessments are fallible; human/tool records keep their own origin",
        }
        result["decisions"] = publication_decisions(result)
        result["decision_hash"] = digest(result["decisions"])
        return result

    def prompt(self, c, chat, messages, turn):
        record = self.record(c, chat)
        self.validate(record)
        payload = {
            "phase": turn["phase"],
            "cycle": record["cycle"],
            "you": turn["participant"],
            "contract": record["contract"],
            "contract_hash": record["contract_hash"],
            "instructions": INSTRUCTIONS[turn["phase"]],
            "output_token_limit": self.chat.output_limit(chat, turn),
        }
        payload["brevity"] = (
            "Openings: at most 250 words and four central claims. Structured phases: short fields, at most two essential checks per claim; steelman <=80 characters, objection <=160, candidate test <=120, minimum resolution <=100, check reason <=100. Finish the complete JSON object within the output budget."
        )
        ids = [m["id"] for m in messages if m["phase"] == "prompt"]
        if turn["phase"] != "opening":
            cycle_messages = [
                m for m in messages if m.get("review_cycle") == record["cycle"]
            ]
            openings = [m for m in cycle_messages if m["phase"] == "opening"]
            ids += [m["id"] for m in openings]
            snapshot = self.snapshot(c, chat)
            if turn["phase"] == "extraction":
                payload["openings"] = [
                    {
                        "id": m["id"],
                        "author_id": m["participant_id"],
                        "text": m["content"],
                    }
                    for m in openings
                ]
                payload["source_units"] = [
                    u for m in openings for u in self.source_units(m)
                ]
                payload["required_source_message_ids"] = [m["id"] for m in openings]
                payload["source_coverage_rule"] = (
                    "Return at least ONE claim from EACH required source message, even when authors repeat similar ideas. Do not merge or deduplicate across authors. Include all required message IDs in coverage. Selecting only some authors is invalid."
                )
            elif turn["phase"] == "scrutiny":
                payload["claims"] = snapshot["claims"]
                payload["coverage"] = record["coverage"]
            elif turn["phase"] == "repair":
                payload["original_author_id"] = turn["author_id"]
                payload["replacement_responder"] = (
                    turn["author_id"] != turn["participant"]["id"]
                )
                payload["claims"] = [
                    x for x in snapshot["claims"] if x["author_id"] == turn["author_id"]
                ]
                cids = {x["claim_id"] for x in payload["claims"]}
                payload["findings"] = [
                    f for f in snapshot["findings"] if f["claim_id"] in cids
                ]
            else:
                for key in (
                    "claims",
                    "findings",
                    "repairs",
                    "rechecks",
                    "decisions",
                    "coverage",
                    "partial_reasons",
                ):
                    payload[key] = snapshot[key]
            if turn["phase"] not in ("extraction",):
                payload["evidence"] = [
                    {
                        k: e.get(k)
                        for k in (
                            "id",
                            "claim_id",
                            "claim_revision",
                            "origin",
                            "relation",
                            "provenance",
                            "content",
                            "integrity",
                            "assessment_reason",
                        )
                    }
                    for e in snapshot["evidence"]
                ]
            notes = [
                m
                for m in messages
                if m["role"] == "user"
                and m["phase"] == "intervention"
                and m.get("review_cycle") == record["cycle"]
            ]
            payload["director_notes"] = [
                {"id": m["id"], "text": m["content"]} for m in notes
            ]
            ids += [m["id"] for m in notes]
            payload["missing_members"] = chat.get("unavailable_members", {})
            payload["response_schema"] = SCHEMAS[turn["phase"]].model_json_schema()
            if turn["phase"] == "extraction":
                payload["response_schema"]["properties"]["claims"]["minItems"] = len(
                    openings
                )
            # Present only protocol references, not database revision IDs with a competing meaning.
            if "claims" in payload:
                payload["claims"] = [
                    {
                        k: x[k]
                        for k in (
                            "claim_id",
                            "revision",
                            "author_id",
                            "text",
                            "kind",
                            "scope",
                            "assumptions",
                            "dependencies",
                            "lifecycle",
                            "source_message_id",
                        )
                    }
                    for x in payload["claims"]
                ]
            if "findings" in payload:
                payload["findings"] = [
                    {
                        "finding_id": x["id"],
                        **{
                            k: x[k]
                            for k in (
                                "claim_id",
                                "claim_revision",
                                "steelman",
                                "objection",
                                "candidate_test",
                                "minimum_resolution",
                                "checks",
                                "evidence_ids",
                            )
                        },
                    }
                    for x in payload["findings"]
                ]
            payload["reference_rule"] = (
                "Target claim_id exactly as supplied, never a storage or revision ID. claim_revision is the supplied revision number. finding_ids/finding_id must refer to supplied finding_id values."
            )
        text = json.dumps(payload, ensure_ascii=False)
        # Current review subclasses still replace schemas and compact metadata.
        # Admit their final payload, not this duplicated intermediate form.
        if chat.get("protocol", {}).get("version") != "reviewed_v3" and chat.get("provider") != "nebius_token_factory" and len(text.encode()) > 90000:
            raise DomainError(
                "Required review context exceeds the input limit. Narrow the cycle; no mandatory objection was dropped.",
                422,
            )
        return text, list(dict.fromkeys(ids))

    def admit(self, c, chat, turn, content, message_id):
        c.execute("SAVEPOINT review_admission")
        try:
            result = self._admit(c, chat, turn, content, message_id)
        except BaseException:
            c.execute("ROLLBACK TO SAVEPOINT review_admission")
            c.execute("RELEASE SAVEPOINT review_admission")
            raise
        c.execute("RELEASE SAVEPOINT review_admission")
        return result

    def _admit(self, c, chat, turn, content, message_id):
        if turn["phase"] == "opening":
            return content
        record = self.record(c, chat)
        snapshot = self.snapshot(c, chat)
        phase = turn["phase"]
        try:
            output = SCHEMAS[phase].model_validate(parse_json(content)).model_dump()
            if phase == "extraction":
                self.extract(c, chat, record, output, message_id)
            elif phase == "scrutiny":
                current = {x["claim_id"]: x for x in snapshot["claims"]}
                if len({f["claim_id"] for f in output["findings"]}) != len(
                    output["findings"]
                ) or {f["claim_id"] for f in output["findings"]} != set(current):
                    raise ValueError(
                        "Scrutiny must cover every admitted claim exactly once"
                    )
                evidence_ids = {e["id"] for e in snapshot["evidence"]}
                for finding in output["findings"]:
                    if (
                        current[finding["claim_id"]]["revision"]
                        != finding["claim_revision"]
                        or not set(finding["evidence_ids"]) <= evidence_ids
                    ):
                        raise ValueError("Stale claim or invented evidence reference")
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
            elif phase == "repair":
                self.repair(c, chat, record, snapshot, turn, output, message_id)
            elif phase == "recheck":
                ids = {f["id"] for f in snapshot["findings"]}
                if (
                    len(output["assessments"]) != len(ids)
                    or {a["finding_id"] for a in output["assessments"]} != ids
                ):
                    raise ValueError("Recheck must assess every finding exactly once")
                claims = {x["claim_id"]: x for x in snapshot["claims"]}
                findings = {x["id"]: x for x in snapshot["findings"]}
                record["rechecks"] = [
                    {
                        **a,
                        "claim_revision": claims[findings[a["finding_id"]]["claim_id"]][
                            "revision"
                        ],
                        "source_message_id": message_id,
                        "origin": "model_assessment",
                    }
                    for a in output["assessments"]
                ]
                record["recheck_limitations"] = output["limitations"]
                record["stale"] = False
            else:
                rendered = self.render_synthesis(snapshot, output)
                publication = self.put(
                    c,
                    chat,
                    record,
                    "review_publication",
                    {
                        "source_message_id": message_id,
                        "snapshot": snapshot,
                        "decision_hash": snapshot["decision_hash"],
                        "fallback": False,
                    },
                )
                record["publication_id"] = publication["id"]
                record["synthesis_fallback"] = False
                record["synthesis_stale"] = False
                record["published_decision_hash"] = snapshot["decision_hash"]
                record["revision"] += 1
                self.store.put(c, "chat_review", record)
                return rendered
        except (
            ValueError,
            ValidationError,
            KeyError,
            TypeError,
            RecursionError,
        ) as exc:
            if phase == "synthesis":
                publication = self.put(
                    c,
                    chat,
                    record,
                    "review_publication",
                    {
                        "source_message_id": message_id,
                        "snapshot": snapshot,
                        "decision_hash": snapshot["decision_hash"],
                        "fallback": True,
                    },
                )
                record["publication_id"] = publication["id"]
                record["synthesis_stale"] = False
                record["synthesis_fallback"] = True
                record["published_decision_hash"] = snapshot["decision_hash"]
                record["revision"] += 1
                self.store.put(c, "chat_review", record)
                return (
                    "## Review summary\n\nThe generated synthesis did not satisfy its schema or reference rules. This local summary preserves the admitted claims and their limits.\n\n"
                    + ledger_markdown(snapshot)
                )
            raise DomainError(
                "Review output was not admitted: schema, coverage, source span, or revision validation failed. Raw provider output is saved; no hidden repair call was made.",
                422,
            ) from exc
        record["revision"] += 1
        self.store.put(c, "chat_review", record)
        return self.readable(phase, output)

    def put(self, c, chat, record, kind, values):
        item = {
            "id": uid(kind),
            "mission_id": chat["mission_id"],
            "chat_id": chat["id"],
            "review_cycle": record["cycle"],
            **values,
        }
        self.store.put(c, kind, item)
        return item

    def extract(self, c, chat, record, output, message_id):
        originals = {
            m["id"]: m
            for m in self.chat.messages(c, chat)
            if m.get("phase") == "opening" and m.get("review_cycle") == record["cycle"]
        }
        refs = [x["ref"] for x in output["claims"]]
        if len(set(refs)) != len(refs):
            raise ValueError("Duplicate claim reference")
        if {x["message_id"] for x in output["coverage"]} != set(originals) or len(
            output["coverage"]
        ) != len(originals):
            raise ValueError("Coverage must include all opening messages")
        mapping = {ref: uid("claim") for ref in refs}
        counts = {}
        graph = {x["ref"]: x["dependencies"] for x in output["claims"]}

        def visit(ref, path):
            if ref in path or ref not in graph:
                raise ValueError("Cyclic or missing claim dependency")
            for dep in graph[ref]:
                visit(dep, path | {ref})

        for extracted in output["claims"]:
            visit(extracted["ref"], set())
            original = originals[extracted["source_message_id"]]
            if extracted.get("source_unit_id"):
                unit = next(
                    (
                        u
                        for u in self.source_units(original)
                        if u["id"] == extracted["source_unit_id"]
                    ),
                    None,
                )
                if unit is None:
                    raise ValueError(
                        "Selected source unit does not belong to the source message"
                    )
                extracted["quote"] = unit["text"]
            if len(extracted["quote"].strip()) < 3:
                raise ValueError(
                    "A verbatim source unit or exact quotation is required"
                )
            start = (
                unit["start"]
                if extracted.get("source_unit_id")
                else original["content"].find(extracted["quote"])
            )
            if start < 0:
                raise ValueError("Claim quotation is not in its source")
            if extracted.get("source_unit_id") and unit["fragment"]:
                coverage = next(
                    x for x in output["coverage"] if x["message_id"] == original["id"]
                )
                coverage["assessment"] = "partial"
                coverage["omitted_material"] = (
                    coverage["omitted_material"]
                    + " A selected passage is a bounded fragment; surrounding qualifiers require inspection."
                )[:1500]
            author = original["participant_id"]
            counts[author] = counts.get(author, 0) + 1
            if counts[author] > self.claims_per_author_limit:
                raise ValueError("Too many claims for one author")
            self.put(
                c,
                chat,
                record,
                "review_claim",
                {
                    "claim_id": mapping[extracted["ref"]],
                    "revision": 1,
                    "author_id": author,
                    "text": extracted["quote"],
                    "source_message_id": original["id"],
                    "source_span": {
                        "start": start,
                        "end": start + len(extracted["quote"]),
                        "hash": digest(extracted["quote"]),
                    },
                    "kind": extracted["kind"],
                    "scope": extracted["scope"],
                    "assumptions": extracted["assumptions"],
                    "dependencies": [mapping[x] for x in extracted["dependencies"]],
                    "lifecycle": "current",
                    "parent_revision": None,
                    "extraction_message_id": message_id,
                    "change_reason": "Extracted by model; scope fidelity is not automatically proven",
                },
            )
        if set(counts) != {m["participant_id"] for m in originals.values()}:
            raise ValueError("At least one claim is required from every saved opening")
        record["coverage"] = output["coverage"]

    def repair(self, c, chat, record, snapshot, turn, output, message_id):
        claims = {
            x["claim_id"]: x
            for x in snapshot["claims"]
            if x["author_id"] == turn["author_id"]
        }
        if len(output["repairs"]) != len(claims) or {
            r["claim_id"] for r in output["repairs"]
        } != set(claims):
            raise ValueError("Repair must address every assigned claim")
        for repair in output["repairs"]:
            claim = claims[repair["claim_id"]]
            targets = {
                f["id"]
                for f in snapshot["findings"]
                if f["claim_id"] == claim["claim_id"]
            }
            if (
                repair["claim_revision"] != claim["revision"]
                or set(repair["finding_ids"]) != targets
            ):
                raise ValueError("Repair references stale or unrelated findings")
            self.put(
                c,
                chat,
                record,
                "review_repair",
                {
                    **repair,
                    "source_message_id": message_id,
                    "responder": turn["participant"],
                    "original_author_id": turn["author_id"],
                    "replacement_response": turn["author_id"]
                    != turn["participant"]["id"],
                },
            )
            if repair["action"] in ("narrow", "revise", "withdraw"):
                if (
                    repair["action"] != "withdraw"
                    and len(repair["revised_text"].strip()) < 3
                ):
                    raise ValueError("Revision requires explicit revised text")
                values = {
                    k: v
                    for k, v in claim.items()
                    if k
                    not in (
                        "id",
                        "schema_version",
                        "created_at",
                        "mission_id",
                        "chat_id",
                        "review_cycle",
                    )
                }
                values.update(
                    revision=claim["revision"] + 1,
                    parent_revision=claim["revision"],
                    text=repair["revised_text"] or claim["text"],
                    assumptions=repair["revised_assumptions"],
                    lifecycle="withdrawn"
                    if repair["action"] == "withdraw"
                    else "current",
                    change_reason=repair["response"],
                    repair_message_id=message_id,
                )
                self.put(c, chat, record, "review_claim", values)

    def render_synthesis(self, snapshot, output):
        decisions = {d["claim_id"]: d for d in snapshot["decisions"]}
        evidence = {e["id"] for e in snapshot["evidence"]}
        headings = {
            "direct_answer": "Direct answer",
            "supported": "Supported within recorded scope",
            "conditional": "Conditional proposals",
            "unresolved": "Unresolved",
            "withdrawn": "Withdrawn or contradicted",
            "next_tests": "Next tests",
        }
        lines = []
        for block in output["blocks"]:
            if (
                not set(block["claim_ids"]) <= set(decisions)
                or not set(block["evidence_ids"]) <= evidence
            ):
                raise ValueError("Unknown synthesis reference")
            for cid in block["claim_ids"]:
                permission = decisions[cid]["permission"]
                allowed = {
                    "supported": {
                        "supported",
                        "direct_answer",
                        "conditional",
                        "next_tests",
                    },
                    "conditional": {
                        "direct_answer",
                        "conditional",
                        "unresolved",
                        "next_tests",
                    },
                    "unresolved": {
                        "direct_answer",
                        "conditional",
                        "unresolved",
                        "next_tests",
                    },
                    "withdrawn": {"withdrawn", "next_tests"},
                }[permission]
                if block["section"] not in allowed:
                    raise ValueError("Claim cannot appear in this section")
            unresolved_recommendation = block["section"] in (
                "direct_answer",
                "conditional",
            ) and any(
                decisions[cid]["permission"] == "unresolved"
                for cid in block["claim_ids"]
            )
            heading = (
                "Conditional answer — unresolved objections"
                if unresolved_recommendation
                else headings[block["section"]]
            )
            lines += [
                "## " + heading,
                "",
                *(
                    [
                        "This generated recommendation has unresolved checks; it is not a verified result.",
                        "",
                    ]
                    if unresolved_recommendation
                    else []
                ),
                block["text"],
                "",
                "Claim basis: "
                + "; ".join(
                    cid + " — " + decisions[cid]["label"] for cid in block["claim_ids"]
                ),
                "",
            ]
        return "\n".join(lines) + "\n\n" + ledger_markdown(snapshot)

    def readable(self, phase, output):
        if phase == "extraction":
            return (
                "## Material claims\n\n"
                + "\n\n".join(
                    f"**{c['ref']}** — {c['quote']}\n\nScope: {c['scope']}"
                    for c in output["claims"]
                )
                + "\n\nExtraction is a model assessment; inspect source coverage in the claim drawer."
            )
        if phase == "scrutiny":
            return (
                "## Scrutiny\n\n"
                + "\n\n".join(
                    f"**{f['claim_id']}**\n\n{f['objection']}\n\nCandidate test: {f['candidate_test']}\n\nResolution needed: {f['minimum_resolution']}"
                    for f in output["findings"]
                )
                + "\n\nLimits: "
                + output["limitations"]
            )
        if phase == "repair":
            return "## Author replies and repairs\n\n" + "\n\n".join(
                f"**{r['claim_id']} — {r['action']}**\n\n{r['response']}\n\n{r['revised_text']}\n\nRemaining uncertainty: {r['remaining_uncertainty']}"
                for r in output["repairs"]
            )
        return (
            "## Recheck\n\n"
            + "\n\n".join(
                f"**{a['finding_id']} — {a['proposed_disposition']}**\n\n{a['reason']}"
                for a in output["assessments"]
            )
            + "\n\nLimits: "
            + output["limitations"]
        )

    def demo(self, c, chat, messages, turn):
        if turn["phase"] == "opening":
            return self.chat.demo_answer(chat, messages, turn)
        snapshot = self.snapshot(c, chat)
        if turn["phase"] == "extraction":
            openings = [
                m
                for m in messages
                if m.get("review_cycle") == snapshot["cycle"]
                and m["phase"] == "opening"
            ]
            output = {
                "claims": [
                    {
                        "ref": f"C{i + 1}",
                        "source_message_id": m["id"],
                        "quote": m["content"].split("\n\n")[-1],
                        "kind": "proposal",
                        "scope": "Synthetic workflow demonstration only",
                        "assumptions": ["Scripted fixture"],
                        "dependencies": [],
                    }
                    for i, m in enumerate(openings)
                ],
                "coverage": [
                    {
                        "message_id": m["id"],
                        "assessment": "partial",
                        "omitted_material": "Only one illustrative claim extracted; the original answer remains available.",
                    }
                    for m in openings
                ],
            }
        elif turn["phase"] == "scrutiny":
            output = {
                "findings": [
                    {
                        "claim_id": x["claim_id"],
                        "claim_revision": x["revision"],
                        "steelman": x["text"],
                        "objection": "No live reasoning or external validation has been demonstrated.",
                        "candidate_test": "Run a permitted, scoped evaluation with retained artifacts.",
                        "minimum_resolution": "Provide actual evidence or keep this as a conditional proposal.",
                        "checks": [
                            {
                                "category": "evidence",
                                "status": "unknown",
                                "reason": "Synthetic examples are not real-world validation.",
                            }
                        ],
                        "evidence_ids": [],
                    }
                    for x in snapshot["claims"]
                ],
                "limitations": "Scripted review; no factual validation occurred.",
            }
        elif turn["phase"] == "repair":
            output = {
                "repairs": [
                    {
                        "claim_id": x["claim_id"],
                        "claim_revision": x["revision"],
                        "finding_ids": [
                            f["id"]
                            for f in snapshot["findings"]
                            if f["claim_id"] == x["claim_id"]
                        ],
                        "action": "narrow",
                        "response": "I accept the limitation and narrow this to a workflow demonstration.",
                        "revised_text": "This scripted council demonstrates the review workflow only.",
                        "revised_assumptions": ["No live model or domain validation"],
                        "remaining_uncertainty": "Actual answer quality has not been evaluated.",
                    }
                    for x in snapshot["claims"]
                    if x["author_id"] == turn["author_id"]
                ]
            }
        elif turn["phase"] == "recheck":
            output = {
                "assessments": [
                    {
                        "finding_id": f["id"],
                        "proposed_disposition": "narrowed",
                        "reason": "The author narrowed its claim; external answer quality remains unverified.",
                    }
                    for f in snapshot["findings"]
                ],
                "limitations": "Scripted fixture, not independent evidence.",
            }
        else:
            output = (
                {
                    "blocks": [
                        {
                            "section": "unresolved",
                            "text": "The review workflow is demonstrated. Your original question remains unverified because these participants are scripted fixtures.",
                            "claim_ids": [x["claim_id"] for x in snapshot["claims"]],
                            "evidence_ids": [],
                        }
                    ]
                }
                if snapshot["claims"]
                else {"blocks": []}
            )
        return json.dumps(output)

    def governed(self, c, cid, expected):
        chat = self.store.get(c, cid, "chat")
        if chat.get("mode") != "reviewed":
            raise DomainError(
                "This conversation uses the original discussion protocol", 422
            )
        record = self.record(c, chat)
        self.store.check(record, expected)
        self.validate(record)
        return chat, record

    def changed(self, c, chat, record, event):
        record.update(
            revision=record["revision"] + 1,
            synthesis_stale=bool(chat.get("final_message_id")),
        )
        chat.update(revision=chat["revision"] + 1, accepted=False)
        self.store.put(c, "chat_review", record)
        self.store.put(c, "chat", chat)
        self.store.event(
            c,
            chat["mission_id"],
            event,
            {"chat_id": chat["id"], "review_revision": record["revision"]},
        )
        return self.chat.view(c, chat["id"])

    def evidence(self, c, cid, body):
        chat, record = self.governed(c, cid, body.expected_revision)
        snapshot = self.snapshot(c, chat)
        claim = next(
            (
                x
                for x in snapshot["claims"]
                if x["claim_id"] == body.claim_id
                and x["revision"] == body.claim_revision
            ),
            None,
        )
        if not claim:
            raise DomainError(
                "Evidence must target a current claim in this review", 422
            )
        if len(snapshot["evidence"]) >= 30:
            raise DomainError(
                "This review reached its source limit; narrow a new cycle", 422
            )
        if body.assessment_reason and len(body.assessment_reason.strip()) < 10:
            raise DomainError(
                "A human relevance assessment needs an explicit reason", 422
            )
        capability = None
        if body.evidence_id:
            source = self.store.get(c, body.evidence_id, "evidence")
            if (
                source["mission_id"] != chat["mission_id"]
                or source["step_id"] != chat["step_id"]
            ):
                raise DomainError(
                    "Tool evidence belongs to another chat or research step", 422
                )
            artifact = self.store.get(c, source["artifact_id"], "artifact")
            data = self.research.artifacts.read(artifact)
            origin = source["evidence_class"]
            capability = source["capability"]
            content = json.dumps(data, ensure_ascii=False)
            if len(content) > 16000:
                raise DomainError(
                    "The evidence exceeds the review source bound; attach a scoped supplied excerpt with attribution",
                    422,
                )
        else:
            if len(body.content.strip()) < 3:
                raise DomainError(
                    "Provide source text or a valid existing evidence ID", 422
                )
            if re.fullmatch(r"https?://\S+", body.content.strip()):
                raise DomainError(
                    "Paste the relevant source excerpt. A URL alone is not checked evidence.",
                    422,
                )
            content = self.research.artifacts.redact(body.content)
            artifact = self.research.artifacts.write(
                chat["mission_id"],
                "review_supplied_source",
                {"content": content, "provenance": body.provenance},
            )
            self.store.put(c, "artifact", artifact)
            origin = "director_supplied_source"
        self.put(
            c,
            chat,
            record,
            "review_evidence",
            {
                "claim_id": body.claim_id,
                "claim_revision": body.claim_revision,
                "artifact_id": artifact["id"],
                "artifact_hash": artifact["sha256"],
                "content": content,
                "origin": origin,
                "tool_capability": capability,
                "relation": body.relation,
                "source_evidence_id": body.evidence_id,
                "provenance": self.research.artifacts.redact(body.provenance),
                "assessment_reason": self.research.artifacts.redact(
                    body.assessment_reason
                ),
                "assessment_actor": "human_director"
                if body.assessment_reason
                else None,
            },
        )
        return self.changed(c, chat, record, "review.evidence_attached")

    def disposition(self, c, cid, body):
        chat, record = self.governed(c, cid, body.expected_revision)
        snapshot = self.snapshot(c, chat)
        finding = next(
            (f for f in snapshot["findings"] if f["id"] == body.finding_id), None
        )
        if not finding:
            raise DomainError("Finding does not belong to this review", 422)
        evidence = {e["id"]: e for e in snapshot["evidence"]}
        claim = next(
            x for x in snapshot["claims"] if x["claim_id"] == finding["claim_id"]
        )
        for eid in body.evidence_ids:
            e = evidence.get(eid)
            if (
                not e
                or e["claim_id"] != claim["claim_id"]
                or e["claim_revision"] != claim["revision"]
                or e["integrity"] != "pass"
            ):
                raise DomainError(
                    "Disposition evidence must support the current targeted claim and pass integrity checks",
                    422,
                )
        if body.status == "confirmed_defect" and not body.evidence_ids:
            raise DomainError(
                "A confirmed defect needs attached evidence; use unresolved for an unverified allegation",
                422,
            )
        self.put(
            c,
            chat,
            record,
            "review_disposition",
            {
                "finding_id": body.finding_id,
                "claim_revision": claim["revision"],
                "status": body.status,
                "reason": self.research.artifacts.redact(body.reason),
                "evidence_ids": body.evidence_ids,
                "actor": "human_director",
            },
        )
        return self.changed(c, chat, record, "review.disposition_recorded")

    def reassign(self, c, cid, body):
        chat, record = self.governed(c, cid, body.expected_revision)
        if chat.get("active_turn") or chat["status"] not in (
            "paused",
            "unavailable",
            "failed",
            "interrupted",
        ):
            raise DomainError(
                "Pause and wait for the in-flight answer before reassigning the next phase"
            )
        members = {p["id"]: p for p in self.chat.active_members(chat)}
        if body.participant_id not in members:
            raise DomainError(
                "Choose an available, originally selected participant", 422
            )
        turn = self.next_turn(c, chat, self.chat.messages(c, chat))
        if not turn or turn["phase"] != body.phase:
            raise DomainError("Only the next incomplete phase can be reassigned", 422)
        if body.phase == "repair" and body.original_author_id != turn["author_id"]:
            raise DomainError("Replacement repair must name its original author", 422)
        if chat["provider"] == "direct_council":
            self.research.direct_provider.validate(
                c,
                [members[body.participant_id]["model"]],
                chat["mission_id"],
                required=self.remaining(c, chat, self.chat.messages(c, chat)),
            )
        if body.phase != "repair":
            record["roles"][body.phase] = body.participant_id
            record["roles_hash"] = digest(record["roles"])
        record["reassignments"].append(
            {
                **body.model_dump(exclude={"expected_revision"}),
                "at": now(),
                "actor": "human_director",
            }
        )
        chat["active_turn"] = None
        return self.changed(c, chat, record, "review.role_reassigned")

    def new_cycle(self, c, chat, question, options=None, expected=None):
        record = self.record(c, chat)
        if expected is not None:
            self.store.check(record, expected)
        if chat.get("active_turn") or chat["status"] in ("running", "waiting"):
            raise DomainError(
                "Pause and wait for the current request before changing the review contract"
            )
        if record["cycle"] >= 6 and chat["provider"] != "direct_council":
            raise DomainError(
                "This council reached its cycle limit; start another council"
            )
        required = 2 * len(chat["participants"]) + 7
        if chat["provider"] == "direct_council":
            self.research.direct_provider.validate(
                c,
                [p["model"] for p in chat["participants"]],
                chat["mission_id"],
                required=required,
            )
        elif chat["provider"] == "openrouter_free":
            self.research.free_provider.capacity(
                c, chat["mission_id"], required=required
            )
        record["history"].append(
            {
                "cycle": record["cycle"],
                "contract": record["contract"],
                "contract_hash": record["contract_hash"],
                "decision_hash": self.snapshot(c, chat)["decision_hash"],
            }
        )
        record.update(
            cycle=record["cycle"] + 1,
            revision=record["revision"] + 1,
            coverage=[],
            rechecks=[],
            reassignments=[],
            skipped_keys=[],
            partial_reasons=[],
            stale=False,
            synthesis_stale=True,
        )
        question = self.research.artifacts.redact(question)
        record["contract"] = self.contract(
            chat, question, options or record["contract"]["options"], record["cycle"]
        )
        record["contract_hash"] = digest(record["contract"])
        self.store.put(c, "chat_review", record)
        chat.update(
            review_cycle=record["cycle"],
            generation=chat["generation"] + 1,
            final_message_id=None,
            requested_finish=False,
            accepted=False,
            status="running",
            error=None,
            unavailable_members={},
            revision=chat["revision"] + 1,
        )
        c.execute(
            "UPDATE jobs SET state='cancelled' WHERE target_id=? AND state='queued'",
            (chat["id"],),
        )
        step = self.store.get(c, chat["step_id"], "step")
        step.update(paused=False, status="committing")
        self.store.put(c, "step", step)
        self.store.put(c, "chat", chat)
        self.chat.message(
            c,
            chat,
            role="user",
            content=question,
            phase="intervention",
            review_cycle=record["cycle"],
        )
        self.research.enqueue(c, "chat", chat)
        self.store.event(
            c,
            chat["mission_id"],
            "review.contract_revised",
            {
                "chat_id": chat["id"],
                "contract_hash": record["contract_hash"],
                "cycle": record["cycle"],
            },
        )
        return self.chat.view(c, chat["id"])

    def resynthesize(self, c, cid, expected):
        chat, record = self.governed(c, cid, expected)
        if chat["status"] != "completed":
            raise DomainError(
                "Finish the current cycle before requesting an updated final"
            )
        if chat["provider"] == "direct_council":
            member = next(
                p
                for p in chat["participants"]
                if p["id"] == record["roles"]["synthesis"]
            )
            self.research.direct_provider.validate(
                c, [member["model"]], chat["mission_id"], required=1
            )
        chat.update(
            generation=chat["generation"] + 1,
            final_message_id=None,
            accepted=False,
            status="running",
            revision=chat["revision"] + 1,
        )
        self.store.put(c, "chat", chat)
        self.research.enqueue(c, "chat", chat)
        return self.chat.view(c, cid)
