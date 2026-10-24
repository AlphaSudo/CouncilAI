"""Scoped review on the legacy durable schedule, with no additional model calls."""

import json

from pydantic import ValidationError

from .contracts import (
    AtomicExtraction,
    ScopedRecheck,
    ScopedRepair,
    ScopedScrutiny,
    ScopedSynthesis,
)
from .council_review_v1 import CouncilReview as LegacyReview
from .db import DomainError, digest
from .provider import parse_json
from .review_policy_v2 import POLICY_VERSION, ledger_markdown, publication_decisions
from .review_provenance import observation_cues

SCHEMAS = {
    "extraction": AtomicExtraction,
    "scrutiny": ScopedScrutiny,
    "repair": ScopedRepair,
    "recheck": ScopedRecheck,
    "synthesis": ScopedSynthesis,
}
INSTRUCTIONS = {
    "opening": "Answer independently in readable English Markdown, at most 220 words and two material assertions. Preserve necessary conditions. Give a direct answer, rationale and limits. Do not claim personal testing, observed measurements or executed experiments unless actual supplied evidence establishes them. A proposed test is not a result.",
    "extraction": "Extract one or two material ATOMIC assertions per opening. Keep each author separately; splitting consumes the two-claim budget. Use actual source_unit_ids (one to three), but write a short assertion separately from verbatim source text. Preserve qualifiers, quantifiers and scope; mark remaining compounds or uncertain fidelity. Prefer decision-changing claims, absolutes and reported measurements. Classify reasoning kind/properties descriptively, not as verification. Record evidence obligation and materiality. Record coverage for EVERY opening. Group only assessed equivalent claims with matching scope, conditions and criterion; related/conflicting groups remain distinguishable, with no evidence transfer. Audit ALL opening text for apparent observations, including omitted passages. List source-unit-bound unsupported self-reports, attributed reports, quotations and hypothetical examples. A trace-looking string is not execution evidence. observation_coverage must disclose omissions or overflow. Return compact complete JSON.",
    "scrutiny": "For EVERY current claim exactly once, steelman and target the actual disputed assertion/aspect. Explain why an objection applies within its scope. Distinguish contradiction, missing evidence, condition and ordinary risk. Unknown is not false. A definition/deduction can need a source or logical check rather than an experiment; empirical/quantitative/causal claims need appropriate support. Audit full openings for unsupported observed-result anecdotes, even outside extracted claims. Propose a discriminating test or justified non-empirical check; give a fair baseline, disconfirming outcome, threshold basis and proxy/completeness, reproducibility and uncertainty limits. Do not invent an arbitrary numerical target. Candidate tests are NOT executed results. Your checks are model opinions, not authority. Return compact complete JSON.",
    "repair": "Reply ONLY for every assigned original author's claim and actual finding IDs. Retain, rebut, narrow, revise or withdraw. Preserve goal and necessary qualifiers; make changed assumptions explicit. Narrowing must remove the actual failure mechanism, not add a vague caveat. Preserve the source/history. Do not invent measured results or tool traces. State remaining uncertainty; keep revised_text concise. Return complete JSON.",
    "recheck": "You assess the exact ORIGINAL objection against the CURRENT revision and actual author reply, not whether zero risk exists. For EVERY original finding: reference its original_revision and current_revision. Compare disputed content and failure mechanism. Did the author remove it, validly narrow scope, make a necessary condition explicit, rebut the critic, or leave the defect? Return resolution as an attributed model assessment. A narrower claim may answer an old objection while required evidence is still missing. Separate contradiction, missing_evidence, condition, operational_limitation, ordinary residual_risk and new_issue. Do not call an unmet hard requirement ordinary risk. Record at most ONE material new_issue per finding, separately; it has not received author review. Assess candidate test alignment, fair baseline, threshold basis, proxy/completeness, repeatability and uncertainty; unknown/not_applicable needs a reason. Do not certify truth, empirical support or execution. Return compact complete JSON.",
    "synthesis": "Answer the director directly in English. Choose recommendation, conditional_choice, comparison_only or no_justified_decision based on server decision_suitability. Lead with the useful answer, criterion and conditions, then decision-changing issues and a discriminating next check. Ordinary residual risk is not automatically a refutation. Never force a winner or hide real blockers. Each block cites actual claim_ids with corresponding current claim_revisions. Supported sections require scoped support; positive recommendations require eligible claims. issue_ids and evidence_ids must exist. Unsupported model-reported timings are not observed facts. Do not invent preferences, evidence, measurements, tests or external verification. The server adds authoritative labels and caveats; your prose remains fallible. Return complete JSON.",
}


class ScopedReview(LegacyReview):
    claims_per_author_limit = 2

    def contract(self, chat, question, options, revision):
        value = super().contract(chat, question, options, revision)
        value.update(
            protocol_version="reviewed_v2",
            prompt_version="scoped-review-v2",
            policy_version=POLICY_VERSION,
            claims_per_author=2,
            claims_per_cycle=8,
            observation_limit=16,
            descriptor_version="claim-descriptors-v2",
            output_token_limit=4096,
            context_byte_limit=90000,
        )
        return value

    def snapshot(self, c, chat):
        value = super().snapshot(c, chat)

        def items(kind):
            return [
                r
                for r in self.store.list(c, kind, chat["mission_id"])
                if r.get("review_cycle") == value["cycle"]
            ]

        value["groups"] = items("review_group")
        value["observations"] = items("review_observation")
        value["concerns"] = items("review_concern")
        current = {x["claim_id"]: x["revision"] for x in value["claims"]}
        for group in value["groups"]:
            group["stale"] = any(
                current.get(m["claim_id"]) != m["revision"] for m in group["members"]
            )
        value["decisions"] = publication_decisions(value)
        value["decision_hash"] = digest(value["decisions"])
        return value

    def prompt(self, c, chat, messages, turn):
        raw, ids = super().prompt(c, chat, messages, turn)
        p = json.loads(raw)
        phase = turn["phase"]
        p["instructions"] = INSTRUCTIONS[phase]
        p["brevity"] = (
            "At most two atomic claims per author, eight total. Use compact fields: assertion <=180 preferred; objection <=100; checks <=2/claim; reasons <=80; comparison <=150. Do not repeat input prose. All required records must fit one complete 4096-token response; disclose coverage limits, never silently omit required records."
        )
        if phase != "opening":
            snap = self.snapshot(c, chat)
            p["response_schema"] = SCHEMAS[phase].model_json_schema()
            p["observations"] = snap["observations"]
            p["groups"] = snap["groups"]
            p["new_concerns"] = snap["concerns"]
            originals = [
                m
                for m in messages
                if m.get("review_cycle") == snap["cycle"] and m["phase"] == "opening"
            ]
            if phase in ("extraction", "scrutiny"):
                p["openings"] = [
                    {
                        "id": m["id"],
                        "author_id": m["participant_id"],
                        **({"text": m["content"]} if phase == "scrutiny" else {}),
                    }
                    for m in originals
                ]
                if phase == "extraction":
                    p["source_units"] = [
                        u for m in originals for u in self.source_units(m)
                    ]
            if phase == "extraction":
                p["source_coverage_rule"] = (
                    "One or two atomic claims from EVERY required opening; preserve authors separately. Any omitted assertions, reported observations or compound remainder must be disclosed. Groups never merge source records."
                )
            else:
                allowed = {x["claim_id"] for x in p.get("claims", [])}
                if phase == "repair":
                    dependency_ids = {
                        dep
                        for x in snap["claims"]
                        if x["claim_id"] in allowed
                        for dep in x.get("dependencies", [])
                    }
                    p["dependency_claims"] = [
                        {
                            k: x[k]
                            for k in (
                                "claim_id",
                                "revision",
                                "text",
                                "scope",
                                "assumptions",
                            )
                        }
                        for x in snap["claims"]
                        if x["claim_id"] in dependency_ids
                    ]
                p["claims"] = [
                    {
                        k: v
                        for k, v in x.items()
                        if k
                        in {
                            "claim_id",
                            "revision",
                            "author_id",
                            "text",
                            "scope",
                            "assumptions",
                            "dependencies",
                            "reasoning_kind",
                            "properties",
                            "fidelity",
                            "evidence_obligation",
                            "source_message_id",
                            "lifecycle",
                            "dependency_versions",
                        }
                    }
                    for x in snap["claims"]
                    if x["claim_id"] in allowed
                ]
                p["findings"] = [
                    {
                        "finding_id": f["id"],
                        **{
                            k: v
                            for k, v in f.items()
                            if k
                            not in {
                                "id",
                                "mission_id",
                                "chat_id",
                                "created_at",
                                "schema_version",
                            }
                        },
                    }
                    for f in snap["findings"]
                    if f["claim_id"] in allowed
                ]
            if phase == "recheck":
                p["original_claim_revisions"] = [
                    {
                        k: x[k]
                        for k in (
                            "claim_id",
                            "revision",
                            "text",
                            "scope",
                            "assumptions",
                            "source_message_id",
                        )
                    }
                    for x in snap["claim_history"]
                ]
            if phase == "synthesis":
                p["decisions"] = snap["decisions"]
                supported = [
                    d["claim_id"]
                    for d in snap["decisions"]
                    if d["permission"] == "supported"
                ]
                p["publication_reference_guide"] = {
                    "current_revisions": {
                        x["claim_id"]: x["revision"] for x in snap["claims"]
                    },
                    "supported_section_claim_ids": supported,
                    "positive_recommendation_claim_ids": [
                        d["claim_id"]
                        for d in snap["decisions"]
                        if d["decision_suitability"].startswith(
                            "recommendation_eligible"
                        )
                    ],
                    "rule": "A model-assessed definition or resolved objection is NOT externally supported. If supported_section_claim_ids is empty, do not emit any supported section. Other claims may be compared with their stated limitations; positive recommendations require the eligible list.",
                }
                if not supported:
                    p["response_schema"]["$defs"]["ScopedAnswerBlock"]["properties"][
                        "section"
                    ]["enum"].remove("supported")
        encoded = json.dumps(p, ensure_ascii=False, separators=(",", ":"))
        if chat.get("protocol", {}).get("version") != "reviewed_v3" and chat.get("provider") != "nebius_token_factory" and len(encoded.encode()) > 90000:
            raise DomainError(
                "Required scoped review context exceeds 90000 bytes; no mandatory warning or objection was dropped",
                422,
            )
        return encoded, ids

    def scan(self, c, chat, record, message):
        existing = [
            x
            for x in self.store.list(c, "review_observation", chat["mission_id"])
            if x.get("review_cycle") == record["cycle"]
        ]
        cues = observation_cues(message)
        if len(cues) + len(existing) > 16:
            raise DomainError(
                "Reported-observation coverage exceeds sixteen alerts; source is retained, narrow the cycle before continuing",
                422,
            )
        for cue in cues:
            self.put(c, chat, record, "review_observation", cue)

    def _admit(self, c, chat, turn, content, message_id):
        record = self.record(c, chat)
        phase = turn["phase"]
        if phase == "opening":
            self.scan(c, chat, record, {"id": message_id, "content": content})
            return content
        snapshot = self.snapshot(c, chat)
        try:
            output = SCHEMAS[phase].model_validate(parse_json(content)).model_dump()
            if phase == "extraction":
                self.extract(c, chat, record, output, message_id)
            elif phase == "scrutiny":
                current = {x["claim_id"]: x for x in snapshot["claims"]}
                if len(output["findings"]) != len(current) or {
                    f["claim_id"] for f in output["findings"]
                } != set(current):
                    raise ValueError(
                        "Scrutiny must cover every atomic claim exactly once"
                    )
                evidence_ids = {e["id"] for e in snapshot["evidence"]}
                for f in output["findings"]:
                    if (
                        current[f["claim_id"]]["revision"] != f["claim_revision"]
                        or not set(f["evidence_ids"]) <= evidence_ids
                    ):
                        raise ValueError("Stale claim or unknown evidence")
                    self.put(
                        c,
                        chat,
                        record,
                        "review_finding",
                        {
                            **f,
                            "reviewer": turn["participant"],
                            "source_message_id": message_id,
                        },
                    )
                record["scrutiny_limitations"] = output["limitations"]
            elif phase == "repair":
                for repair in output["repairs"]:
                    if (
                        repair["action"] in ("narrow", "revise")
                        and not repair["revised_scope"].strip()
                    ):
                        raise ValueError(
                            "A scoped revision requires an explicit revised_scope"
                        )
                super().repair(c, chat, record, snapshot, turn, output, message_id)
                for item in self.store.list(c, "review_claim", chat["mission_id"]):
                    if item.get("repair_message_id") == message_id:
                        repair = next(
                            r
                            for r in output["repairs"]
                            if r["claim_id"] == item["claim_id"]
                        )
                        item.update(
                            assertion=item["text"],
                            scope=repair["revised_scope"] or item["scope"],
                            dependency_versions={
                                dep: next(
                                    x["revision"]
                                    for x in snapshot["claims"]
                                    if x["claim_id"] == dep
                                )
                                for dep in item.get("dependencies", [])
                            },
                        )
                        self.store.put(c, "review_claim", item)
                self.scan(
                    c,
                    chat,
                    record,
                    {"id": message_id, "content": self.readable(phase, output)},
                )
            elif phase == "recheck":
                self.recheck(c, chat, record, snapshot, output, message_id)
            else:
                rendered = self.render_synthesis(snapshot, output)
                return self.publish(
                    c,
                    chat,
                    record,
                    snapshot,
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
            RecursionError,
            StopIteration,
        ) as exc:
            if phase == "synthesis":
                return self.publish(
                    c,
                    chat,
                    record,
                    snapshot,
                    message_id,
                    self.fallback(snapshot),
                    True,
                    "comparison_only",
                    str(exc),
                )
            raise DomainError(
                "Scoped review output was not admitted: schema, coverage, provenance or revision validation failed. Raw output is retained; no hidden repair call was made.",
                422,
            ) from exc
        record["revision"] += 1
        self.store.put(c, "chat_review", record)
        return self.readable(phase, output)

    def extract(self, c, chat, record, output, message_id):
        if output["observation_status"] == "overflow":
            raise ValueError("Required observation audit overflow; narrow the cycle")
        originals = {
            m["id"]: m
            for m in self.chat.messages(c, chat)
            if m.get("phase") == "opening" and m.get("review_cycle") == record["cycle"]
        }
        adapted = []
        for claim in output["claims"]:
            original = originals[claim["source_message_id"]]
            units = {u["id"]: u for u in self.source_units(original)}
            selected = [units[u] for u in claim["source_unit_ids"]]
            if len(set(claim["source_unit_ids"])) != len(selected):
                raise ValueError("Duplicate source units")
            adapted.append(
                {
                    "ref": claim["ref"],
                    "source_message_id": original["id"],
                    "source_unit_id": selected[0]["id"],
                    "quote": "",
                    "kind": "proposal",
                    "scope": claim["scope"],
                    "assumptions": claim["assumptions"],
                    "dependencies": claim["dependencies"],
                }
            )
        # Reuse exact-source, author coverage and DAG validation under the admission savepoint.
        super().extract(
            c,
            chat,
            record,
            {"claims": adapted, "coverage": output["coverage"]},
            message_id,
        )
        stored = [
            x
            for x in self.store.list(c, "review_claim", chat["mission_id"])
            if x.get("extraction_message_id") == message_id
        ]
        by_ref = dict(zip([x["ref"] for x in output["claims"]], stored, strict=True))
        authors = {}
        for claim, item in zip(output["claims"], stored, strict=True):
            authors[item["author_id"]] = authors.get(item["author_id"], 0) + 1
            if authors[item["author_id"]] > self.claims_per_author_limit:
                raise ValueError("The profile's atomic-claim limit per author was exceeded")
            units = {
                u["id"]: u
                for u in self.source_units(originals[claim["source_message_id"]])
            }
            item.update(
                text=claim["assertion"],
                assertion=claim["assertion"],
                source_spans=[
                    {**units[u], "hash": digest(units[u]["text"])}
                    for u in claim["source_unit_ids"]
                ],
                reasoning_kind=claim["reasoning_kind"],
                properties=claim["properties"],
                fidelity=claim["fidelity"],
                materiality=claim["materiality"],
                evidence_obligation=claim["evidence_obligation"],
                dependency_versions={dep: 1 for dep in item.get("dependencies", [])},
            )
            self.store.put(c, "review_claim", item)
        for group in output["groups"]:
            if len(set(group["refs"])) != len(group["refs"]):
                raise ValueError("Duplicate group member")
            members = [
                {"claim_id": by_ref[r]["claim_id"], "revision": 1}
                for r in group["refs"]
            ]
            self.put(
                c,
                chat,
                record,
                "review_group",
                {
                    "members": members,
                    "relation": group["relation"],
                    "reason": group["reason"],
                    "origin": "model_assessment",
                    "source_message_id": message_id,
                },
            )
        existing = [
            o
            for o in self.store.list(c, "review_observation", chat["mission_id"])
            if o.get("review_cycle") == record["cycle"]
        ]
        for observation in output["observations"]:
            source = originals[observation["source_message_id"]]
            unit = next(
                u
                for u in self.source_units(source)
                if u["id"] == observation["source_unit_id"]
            )
            matching = next(
                (
                    x
                    for x in existing
                    if x["source_message_id"] == source["id"]
                    and x["source_span"]["start"] < unit["end"]
                    and x["source_span"]["end"] > unit["start"]
                ),
                None,
            )
            if matching:
                matching["model_assessment"] = observation
                self.store.put(c, "review_observation", matching)
                continue
            if len(existing) >= 16:
                raise ValueError("Observation audit overflow; narrow the cycle")
            # A model's reinterpretation cannot erase a local warning or create execution authority.
            item = self.put(
                c,
                chat,
                record,
                "review_observation",
                {
                    **observation,
                    "text": unit["text"],
                    "source_span": {
                        "start": unit["start"],
                        "end": unit["end"],
                        "hash": digest(unit["text"]),
                    },
                    "origin": "model_assessment",
                    "status": "unverified_report",
                },
            )
            existing.append(item)
        record["observation_coverage"] = output["observation_coverage"]
        record["observation_status"] = output["observation_status"]

    def recheck(self, c, chat, record, snapshot, output, message_id):
        findings = {f["id"]: f for f in snapshot["findings"]}
        claims = {x["claim_id"]: x for x in snapshot["claims"]}
        if len(output["assessments"]) != len(findings) or {
            a["finding_id"] for a in output["assessments"]
        } != set(findings):
            raise ValueError("Recheck must assess every original finding exactly once")
        admitted = []
        for a in output["assessments"]:
            finding = findings[a["finding_id"]]
            claim = claims[finding["claim_id"]]
            if (
                a["original_revision"] != finding["claim_revision"]
                or a["current_revision"] != claim["revision"]
            ):
                raise ValueError(
                    "Recheck comparison references stale or unrelated revisions"
                )
            if sum(x["kind"] == "new_issue" for x in a["concerns"]) > 1:
                raise ValueError(
                    "Only one new material issue per finding fits this profile"
                )
            if a["resolution"] == "withdrawn" and claim["lifecycle"] != "withdrawn":
                raise ValueError("An assessor cannot withdraw the author's claim")
            if (
                a["closure_basis"]
                in {
                    "content_removed",
                    "scope_narrowed",
                    "condition_explicit",
                    "actual_correction",
                }
                and claim["revision"] <= finding["claim_revision"]
            ):
                raise ValueError("Claimed repair has no actual author revision")
            if (
                a["resolution"] == "resolved_as_assessed"
                and a["closure_basis"] == "no_effective_change"
            ):
                raise ValueError("Resolution needs an explicit effective basis")
            for concern in a["concerns"]:
                self.put(
                    c,
                    chat,
                    record,
                    "review_concern",
                    {
                        **concern,
                        "claim_id": claim["claim_id"],
                        "claim_revision": claim["revision"],
                        "finding_id": finding["id"],
                        "review_state": "not_reviewed"
                        if concern["kind"] == "new_issue"
                        else "model_assessment",
                        "origin": "model_assessment",
                        "source_message_id": message_id,
                    },
                )
            admitted.append(
                {
                    **a,
                    "claim_revision": claim["revision"],
                    "proposed_disposition": a["resolution"],
                    "reason": a["comparison"],
                    "origin": "model_assessment",
                    "source_message_id": message_id,
                }
            )
        record["rechecks"] = admitted
        record["recheck_limitations"] = output["limitations"]
        record["stale"] = False

    def publish(
        self,
        c,
        chat,
        record,
        snapshot,
        message_id,
        rendered,
        fallback,
        disposition,
        fallback_reason=None,
    ):
        item = self.put(
            c,
            chat,
            record,
            "review_publication",
            {
                "source_message_id": message_id,
                "snapshot": snapshot,
                "decision_hash": snapshot["decision_hash"],
                "fallback": fallback,
                "answer_disposition": disposition,
                "fallback_reason": self.research.artifacts.redact(fallback_reason)
                if fallback_reason
                else None,
            },
        )
        record.update(
            publication_id=item["id"],
            synthesis_fallback=fallback,
            synthesis_stale=False,
            published_decision_hash=snapshot["decision_hash"],
            answer_disposition=disposition,
            synthesis_fallback_reason=self.research.artifacts.redact(fallback_reason)
            if fallback_reason
            else None,
            revision=record["revision"] + 1,
        )
        self.store.put(c, "chat_review", record)
        return rendered

    def render_synthesis(self, snapshot, output):
        if output["blocks"][0]["section"] != "direct_answer":
            raise ValueError("Scoped synthesis must lead with a direct answer")
        decisions = {d["claim_id"]: d for d in snapshot["decisions"]}
        claims = {x["claim_id"]: x for x in snapshot["claims"]}
        evidence = {e["id"]: e for e in snapshot["evidence"]}
        issues = {x["id"] for x in snapshot.get("concerns", [])} | {
            f["id"] for f in snapshot["findings"]
        }
        issue_records = {
            x["id"]: x for x in snapshot.get("concerns", []) + snapshot["findings"]
        }
        lines = []
        for index, block in enumerate(output["blocks"]):
            refs = block["claim_ids"]
            if (
                len(refs) != len(set(refs))
                or len(refs) != len(block["claim_revisions"])
                or not set(refs) <= set(claims)
                or not set(block["evidence_ids"]) <= set(evidence)
                or not set(block["issue_ids"]) <= issues
            ):
                raise ValueError("Unknown, duplicate or inconsistent final reference")
            if any(
                claims[cid]["revision"] != revision
                for cid, revision in zip(refs, block["claim_revisions"], strict=True)
            ):
                raise ValueError("Final cites an old revision")
            if any(
                issue_records[i]["claim_id"] not in refs for i in block["issue_ids"]
            ):
                raise ValueError("Final issue reference belongs to another claim")
            if any(
                evidence[e]["claim_id"] not in refs
                or evidence[e]["claim_revision"]
                != claims[evidence[e]["claim_id"]]["revision"]
                for e in block["evidence_ids"]
            ):
                raise ValueError("Evidence reference is unrelated or stale")
            section = block["section"]
            positive = section in {
                "supported",
                "direct_answer",
                "conditional",
            } and output["answer_disposition"] in {
                "recommendation",
                "conditional_choice",
            }
            if any(
                decisions[cid]["permission"] == "withdrawn" for cid in refs
            ) and section not in {"withdrawn", "next_tests"}:
                raise ValueError("Withdrawn claim used positively")
            if section == "supported" and any(
                decisions[cid]["permission"] != "supported" for cid in refs
            ):
                raise ValueError("Unsupported claim in supported section")
            if positive and any(
                not decisions[cid]["decision_suitability"].startswith(
                    "recommendation_eligible"
                )
                for cid in refs
            ):
                raise ValueError("Recommendation relies on an ineligible claim")
            if (
                positive
                and output["answer_disposition"] == "recommendation"
                and any(decisions[cid]["permission"] != "supported" for cid in refs)
            ):
                raise ValueError("Unqualified recommendation lacks scoped support")
            title = (
                "Direct answer"
                if index == 0
                else section.replace("_", " ").capitalize()
            )
            lines += ["## " + title, "", block["text"], ""]
        referenced = {cid for b in output["blocks"] for cid in b["claim_ids"]}
        lines += [
            "## Scope and evidence",
            "",
            "Answer disposition: "
            + output["answer_disposition"].replace("_", " ")
            + ". Model review does not establish external verification.",
            "",
        ]
        for cid in sorted(referenced):
            d = decisions[cid]
            lines += ["- " + cid + ": " + d["label"]]
        caveats = [
            s
            for cid in sorted(referenced)
            for s in decisions[cid]["required_caveats"] + decisions[cid]["blockers"]
        ]
        caveats += [
            "Condition (assumed, not verified): " + a["text"]
            for cid in sorted(referenced)
            for a in decisions[cid]["conditions"]
        ]
        caveats += [
            "Ordinary residual risk: " + a["detail"]
            for cid in sorted(referenced)
            for a in decisions[cid]["residual_risks"]
        ]
        lines += ["- " + x for x in dict.fromkeys(caveats)]
        if snapshot.get("observations"):
            lines += [
                "",
                "Reported-observation warnings remain in Claims & evidence. No unlinked reported timing is a measured council result.",
            ]
        lines += [
            "",
            "## Claim and evidence ledger",
            "",
            "Inspect Claims & evidence for original passages, individual author revisions, group assessments, tests and the complete evidence ledger.",
        ]
        return "\n".join(lines)

    def fallback(self, snapshot):
        lines = [
            "## Direct answer",
            "",
            "The generated answer did not satisfy the scoped reference rules. These are the current conditional options and decision limits; no extra model call was made.",
            "",
        ]
        for eligible, title in (
            (True, "Conditional options within current scope"),
            (False, "Unresolved or withdrawn assertions"),
        ):
            rows = [
                (c, d)
                for c, d in zip(snapshot["claims"], snapshot["decisions"], strict=True)
                if d["decision_suitability"].startswith("recommendation_eligible")
                == eligible
            ]
            if rows:
                lines += ["## " + title, ""]
                lines += ["- " + c["text"] + " — " + d["label"] for c, d in rows]
        if not snapshot["claims"]:
            lines += [
                "No atomic claim was admitted; no justified decision can be published."
            ]
        lines += [
            "",
            "Next check: address the recorded decision-changing issues or supply scoped evidence before upgrading the recommendation.",
            "",
            ledger_markdown(snapshot),
        ]
        return "\n".join(lines)

    def readable(self, phase, output):
        if phase == "extraction":
            return (
                "## Atomic claims\n\n"
                + "\n\n".join(
                    "**" + x["ref"] + "** — " + x["assertion"] for x in output["claims"]
                )
                + "\n\nAssertions, grouping and coverage are model assessments; inspect the original source passages."
            )
        if phase == "recheck":
            return (
                "## Scoped recheck\n\n"
                + "\n\n".join(
                    "**"
                    + x["finding_id"]
                    + " — "
                    + x["resolution"]
                    + "**\n\n"
                    + x["comparison"]
                    + "\n\n"
                    + "; ".join(y["kind"] + ": " + y["detail"] for y in x["concerns"])
                    for x in output["assessments"]
                )
                + "\n\nLimits: "
                + output["limitations"]
            )
        return super().readable(phase, output)

    def evidence(self, c, cid, body):
        view = super().evidence(c, cid, body)
        chat = view["chat"]
        evidence = self.store.list(c, "review_evidence", chat["mission_id"])[-1]
        evidence.update(
            supported_scope=self.research.artifacts.redact(body.supported_scope),
            scope_coverage=body.scope_coverage,
            directness=body.directness,
            reproduction=self.research.artifacts.redact(body.reproduction),
        )
        self.store.put(c, "review_evidence", evidence)
        return self.chat.view(c, cid)

    def demo(self, c, chat, messages, turn):
        phase = turn["phase"]
        if phase == "opening":
            return self.chat.demo_answer(chat, messages, turn)
        snapshot = self.snapshot(c, chat)
        if phase == "extraction":
            originals = [
                m
                for m in messages
                if m.get("phase") == "opening"
                and m.get("review_cycle") == snapshot["cycle"]
            ]
            out = {
                "claims": [
                    {
                        "ref": f"C{i + 1}",
                        "source_message_id": m["id"],
                        "source_unit_ids": [self.source_units(m)[-1]["id"]],
                        "assertion": "This scripted example demonstrates a review workflow only.",
                        "scope": "Synthetic workflow fixture only",
                        "assumptions": ["Scripted participants"],
                        "dependencies": [],
                        "reasoning_kind": "proposal",
                        "properties": [],
                        "fidelity": "faithful_as_assessed",
                        "materiality": "Distinguishes a demo from actual answer quality",
                        "evidence_obligation": "Independent evaluation needed for answer quality",
                    }
                    for i, m in enumerate(originals)
                ],
                "coverage": [
                    {
                        "message_id": m["id"],
                        "assessment": "partial",
                        "omitted_material": "Only one illustrative assertion selected; not an exhaustive review",
                    }
                    for m in originals
                ],
                "groups": [
                    {
                        "refs": [f"C{i + 1}" for i in range(len(originals))],
                        "relation": "equivalent_as_assessed",
                        "reason": "Same synthetic workflow-only scope and conditions",
                    }
                ],
                "observations": [],
                "observation_coverage": "Scripted fixture inspected; detection is not exhaustive semantic validation",
            }
        elif phase == "scrutiny":
            out = json.loads(super().demo(c, chat, messages, turn))
            for f in out["findings"]:
                f.update(
                    target="Whether a demo establishes answer quality",
                    in_scope_reason="Quality claim must be distinguished from workflow behavior",
                    concern_kind="missing_evidence",
                    test={
                        "method": "Review held-out tasks with qualified human labels",
                        "disconfirming_outcome": "No usefulness gain or material false closure",
                        "baseline": "Same models and tasks under v1",
                        "threshold_basis": "Predeclared task criteria, not an arbitrary percentage",
                        "limitations": "Small pilot, no population guarantee",
                    },
                )
        elif phase == "repair":
            out = json.loads(super().demo(c, chat, messages, turn))
            for repair in out["repairs"]:
                repair["revised_scope"] = "Synthetic workflow demonstration only"
        elif phase == "recheck":
            claims = {x["claim_id"]: x for x in snapshot["claims"]}
            out = {
                "assessments": [
                    {
                        "finding_id": f["id"],
                        "original_revision": f["claim_revision"],
                        "current_revision": claims[f["claim_id"]]["revision"],
                        "resolution": "resolved_as_assessed",
                        "closure_basis": "scope_narrowed",
                        "comparison": "The revised assertion is only a workflow demonstration; the criticism of unproved answer quality no longer contradicts it.",
                        "concerns": [
                            {
                                "kind": "residual_risk",
                                "detail": "Actual answer quality remains unevaluated",
                                "affected_scope": "Future real-world use",
                                "materiality": "ordinary",
                            }
                        ],
                        "test_assessment": "suitable_as_assessed",
                        "test_reason": "Paired tasks can compare the intended quality outcome",
                    }
                    for f in snapshot["findings"]
                ],
                "limitations": "Scripted assessments; not independent quality evidence",
            }
        else:
            out = {
                "answer_disposition": "conditional_choice",
                "blocks": [
                    {
                        "section": "direct_answer",
                        "text": "This scripted council demonstrates the scoped review workflow. Use a real, bounded evaluation before relying on its answer quality. No factual result is verified by this demo.",
                        "claim_ids": [x["claim_id"] for x in snapshot["claims"]],
                        "claim_revisions": [x["revision"] for x in snapshot["claims"]],
                        "issue_ids": [],
                        "evidence_ids": [],
                    }
                ],
            }
        return json.dumps(out)
