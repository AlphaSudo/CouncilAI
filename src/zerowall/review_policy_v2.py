"""Scoped publication decisions, with opinions, support and risk kept distinct."""

from .db import digest

POLICY_VERSION = "generic-publication-v2"
TOOL_CAPABILITIES = {
    "analysis.calculate_bound",
    "analysis.compare_trials",
    "inference.run_benchmark",
}


def publication_decisions(snapshot):
    claims = {c["claim_id"]: c for c in snapshot["claims"]}
    assessments = {a["finding_id"]: a for a in snapshot.get("rechecks", [])}
    humans = {a["finding_id"]: a for a in snapshot.get("dispositions", [])}
    decisions = {}

    def decide(cid, visiting):
        if cid in decisions:
            return decisions[cid]
        claim = claims[cid]
        revision = claim["revision"]
        findings = [f for f in snapshot["findings"] if f["claim_id"] == cid]
        evidence = [
            e
            for e in snapshot["evidence"]
            if e["claim_id"] == cid and e["claim_revision"] == revision
        ]
        assessed = [
            e
            for e in evidence
            if e.get("integrity") == "pass"
            and e.get("assessment_actor") == "human_director"
            and e.get("assessment_reason")
            and e.get("origin") not in {"fixture", "synthetic", "synthetic_fixture"}
        ]
        supporting = [
            e
            for e in assessed
            if e["relation"] == "supports"
            and e.get("supported_scope")
            and e.get("scope_coverage") == "whole_claim_as_assessed"
        ]
        conflicting = [e for e in assessed if e["relation"] == "challenges"]
        issues, risks, reasons, caveats = [], [], [], []
        conditions = [
            {"text": a, "fulfillment": "assumed_not_verified"}
            for a in claim.get("assumptions", [])
        ]
        review_state = "complete_as_assessed"
        if not findings:
            issues.append("No scrutiny finding for this claim")
            review_state = "not_reviewed"
        for f in findings:
            a = assessments.get(f["id"], {})
            h = humans.get(f["id"], {})
            if h.get("claim_revision") != revision:
                h = {}
            current = a.get("claim_revision") == revision
            if not current:
                issues.append(f["id"] + ": current revision has not been rechecked")
                review_state = "stale" if a else "not_reviewed"
            elif h.get("status") == "rebutted":
                reasons.append(
                    "Original objection rebutted within the recorded human assessment"
                )
            elif a.get("resolution") == "resolved_as_assessed":
                reasons.append(f["id"] + ": objection answered as assessed by a model")
            elif (
                a.get("resolution") == "partly_resolved_as_assessed"
                and revision > f["claim_revision"]
                and a.get("closure_basis")
                in {"scope_narrowed", "condition_explicit", "content_removed"}
                and a.get("concerns")
                and all(
                    x["kind"]
                    in {"condition", "operational_limitation", "residual_risk"}
                    and x["materiality"] == "ordinary"
                    for x in a["concerns"]
                )
            ):
                review_state = "partly_addressed"
                caveats.append(
                    "Only the current narrowed assertion is conditionally usable; the original broader claim was not fully resolved"
                )
            elif a.get("resolution") != "withdrawn":
                issues.append(
                    f["id"] + ": " + a.get("resolution", "unresolved_as_assessed")
                )
                review_state = (
                    "partly_addressed"
                    if a.get("resolution") == "partly_resolved_as_assessed"
                    else "open_issue"
                )
            if current:
                for concern in a.get("concerns", []):
                    item = {
                        **concern,
                        "finding_id": f["id"],
                        "origin": "model_assessment",
                    }
                    if (
                        concern["kind"] == "residual_risk"
                        and concern["materiality"] == "ordinary"
                    ):
                        risks.append(item)
                    elif (
                        concern["kind"] in ("condition", "operational_limitation")
                        and concern["materiality"] == "ordinary"
                    ):
                        caveats.append(concern["detail"])
                    else:
                        issues.append(
                            f["id"] + ": " + concern["kind"] + " - " + concern["detail"]
                        )
                if a.get("test_assessment") in ("needs_revision", "unknown"):
                    caveats.append(
                        "Candidate test "
                        + a["test_assessment"]
                        + ": "
                        + a.get("test_reason", "Unknown")
                    )
            if h.get("status") == "accepted_risk":
                reasons.append(
                    "Director accepted a bounded risk; evidence strength is unchanged"
                )

        evidence_state = "model_reasoning_only" if findings else "no_assessed_support"
        if evidence:
            evidence_state = "supplied_unassessed"
        if supporting:
            evidence_state = "support_within_recorded_assessment"
        if assessed and not supporting and not conflicting:
            evidence_state = "partially_assessed_scope"
        if conflicting:
            evidence_state = "conflicting_assessed_evidence"
            issues.append("Conflicting evidence within a recorded human assessment")
        # Whole-opening alerts stay visible, including passages extraction omitted.
        alerts = [
            o
            for o in snapshot.get("observations", [])
            if o.get("source_message_id")
            in {claim.get("source_message_id"), claim.get("repair_message_id")}
            and o.get("classification") == "unsupported_self_report"
        ]
        if alerts:
            caveats.append(
                "Unsupported model-reported observations occur in this author's source; no linked execution is established"
            )
        if claim.get("fidelity") in ("uncertain", "compound_remaining"):
            caveats.append(
                "Atomic extraction fidelity or completeness requires inspection"
            )
        external_required = (
            snapshot["contract"]["options"]["evidence_requirement"] != "model_review"
        )
        if external_required and not supporting:
            issues.append(
                "Required external evidence has not been assessed for this scope"
            )
        if snapshot["contract"]["options"][
            "evidence_requirement"
        ] == "scoped_tool_result" and not any(
            e.get("origin") in {"calculated", "measured_api"}
            and e.get("tool_capability") in TOOL_CAPABILITIES
            for e in supporting
        ):
            issues.append("The required scoped tool result is missing")
        if snapshot.get("stale"):
            issues.append("Review context changed; recheck is stale")
            review_state = "stale"
        for dependency in claim.get("dependencies", []):
            if (
                dependency in claims
                and claim.get("dependency_versions", {}).get(dependency)
                != claims[dependency]["revision"]
            ):
                issues.append(
                    "Dependency revision changed; reassessment required: " + dependency
                )
            if dependency not in claims or dependency in visiting or dependency == cid:
                issues.append("Missing or cyclic dependency " + dependency)
            else:
                prior = decide(dependency, visiting | {cid})
                if prior["permission"] != "supported":
                    issues.append("Dependency lacks scoped support: " + dependency)
        confirmed = any(
            humans.get(f["id"], {}).get("claim_revision") == revision
            and humans.get(f["id"], {}).get("status") == "confirmed_defect"
            and humans.get(f["id"], {}).get("evidence_ids")
            for f in findings
        )
        withdrawn = claim.get("lifecycle") == "withdrawn" or confirmed
        if withdrawn:
            permission, label, suitability, review_state = (
                "withdrawn",
                "Withdrawn or contradicted within recorded human assessment",
                "decision_blocked",
                "withdrawn",
            )
        elif issues:
            permission, label, suitability = (
                "unresolved",
                "Open issue or incomplete review",
                "comparison_only",
            )
        elif supporting:
            permission, label, suitability = (
                "supported",
                "Supported within the recorded scope assessment",
                "recommendation_eligible_within_scope",
            )
        else:
            permission, label, suitability = (
                "conditional",
                "Conditional; objection answered as assessed, external support unverified",
                "recommendation_eligible_within_conditions",
            )
            if review_state == "partly_addressed":
                label = "Conditional scoped use; partly addressed as assessed, external support unverified"
        # An empirical assertion cannot acquire observed-result status through a closed objection.
        if not supporting and (
            claim.get("reasoning_kind") == "empirical"
            or "quantitative" in claim.get("properties", [])
        ):
            caveats.append(
                "No scoped assessed observation supports this empirical or quantitative assertion"
            )
            if suitability.startswith("recommendation_eligible"):
                suitability = "comparison_only"
        basis = {
            "claim": claim,
            "findings": findings,
            "evidence": evidence,
            "rechecks": snapshot.get("rechecks", []),
            "dispositions": snapshot.get("dispositions", []),
            "observations": snapshot.get("observations", []),
            "contract_hash": snapshot["contract_hash"],
            "stale": snapshot.get("stale", False),
        }
        decisions[cid] = {
            "claim_id": cid,
            "claim_revision": revision,
            "label": label,
            "permission": permission,
            "review_state": review_state,
            "evidence_state": evidence_state,
            "conditions": conditions,
            "residual_risks": risks,
            "blockers": issues,
            "reasons": reasons,
            "required_caveats": list(dict.fromkeys(caveats)),
            "decision_suitability": suitability,
            "evidence_ids": [e["id"] for e in evidence],
            "policy_version": POLICY_VERSION,
            "basis_hash": digest(basis),
        }
        return decisions[cid]

    return [decide(c["claim_id"], set()) for c in snapshot["claims"]]


def ledger_markdown(snapshot):
    lines = [
        "## Claim and evidence ledger",
        "",
        "Objection resolution is a model assessment. Conditions, evidence and ordinary risk remain separate.",
        "",
    ]
    by_id = {d["claim_id"]: d for d in snapshot["decisions"]}
    for c in snapshot["claims"]:
        d = by_id[c["claim_id"]]
        lines += [
            f"### {c['claim_id']} v{c['revision']}",
            "",
            c["text"],
            "",
            f"Status: **{d['label']}**",
            f"Review: {d['review_state']}; evidence: {d['evidence_state']}",
            f"Scope: {c['scope']}",
        ]
        lines += ["- Condition (assumed): " + x["text"] for x in d["conditions"]]
        lines += ["- " + x for x in d["blockers"] + d["required_caveats"]]
        lines += [
            "- Ordinary residual risk: " + x["detail"] for x in d["residual_risks"]
        ]
        lines += [""]
    lines += [
        "## Review coverage",
        "",
        "Extraction, grouping and source-cue detection are fallible assessments, not guarantees of coverage.",
    ]
    lines += [
        f"- {c['message_id']}: {c['assessment']}. {c['omitted_material']}"
        for c in snapshot.get("coverage", [])
    ]
    lines += ["", "## Reported observations", ""]
    lines += [
        "- " + o["source_message_id"] + ": " + o["classification"] + " - " + o["text"]
        for o in snapshot.get("observations", [])
    ]
    if snapshot.get("partial_reasons"):
        lines += ["", "Incomplete stages: " + "; ".join(snapshot["partial_reasons"])]
    return "\n".join(lines)
