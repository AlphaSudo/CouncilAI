"""Reproducible publication permissions. Model opinions never become trusted checks."""

from .db import digest

POLICY_VERSION = "generic-publication-v1"


def publication_decisions(snapshot):
    claims = snapshot["claims"]
    by_id = {x["claim_id"]: x for x in claims}
    results = {}
    rechecks = {a["finding_id"]: a for a in snapshot.get("rechecks", [])}
    dispositions = {a["finding_id"]: a for a in snapshot.get("dispositions", [])}
    contract = snapshot["contract"]

    def decide(cid, visiting):
        if cid in results:
            return results[cid]
        claim = by_id[cid]
        findings = [f for f in snapshot["findings"] if f["claim_id"] == cid]
        evidence = [
            e
            for e in snapshot["evidence"]
            if e["claim_id"] == cid and e["claim_revision"] == claim["revision"]
        ]
        checked = [
            e
            for e in evidence
            if e.get("integrity") == "pass"
            and e.get("assessment_reason")
            and e.get("origin") not in ("fixture", "synthetic", "synthetic_fixture")
        ]
        blockers, reasons = [], []
        label, permission = "Unverified proposal", "conditional"
        if claim.get("lifecycle") == "withdrawn":
            label, permission = "Withdrawn by author", "withdrawn"
        else:
            if not findings:
                blockers.append("No scrutiny finding for this claim")
            for finding in findings:
                assessment = rechecks.get(finding["id"], {})
                human = dispositions.get(finding["id"], {})
                # Only an explicit authenticated assessment tied to the current revision counts.
                if human.get("claim_revision") != claim["revision"]:
                    human = {}
                if human.get("status") == "confirmed_defect" and human.get(
                    "evidence_ids"
                ):
                    label, permission = (
                        "Contradicted within recorded human assessment",
                        "withdrawn",
                    )
                    reasons.append(human["reason"])
                checks = finding.get("checks", [])
                challenged = any(x["status"] in ("fail", "unknown") for x in checks)
                if challenged and human.get("status") not in (
                    "rebutted",
                    "confirmed_defect",
                ):
                    if assessment.get("claim_revision") == claim[
                        "revision"
                    ] and assessment.get("proposed_disposition") in (
                        "rebutted_as_assessment",
                        "no_issue_as_assessed",
                    ):
                        reasons.append(
                            "Recheck considers the objection answered; this is a model assessment"
                        )
                    else:
                        blockers.append(
                            finding["id"] + ": objection remains unresolved"
                        )
                if assessment.get("claim_revision") != claim["revision"]:
                    blockers.append(
                        finding["id"] + ": current claim has not been rechecked"
                    )
                if human.get("status") == "accepted_risk":
                    reasons.append(
                        "Director accepted a bounded risk; evidence strength is unchanged"
                    )
            for dep in claim.get("dependencies", []):
                if dep not in by_id or dep in visiting:
                    blockers.append("Missing or cyclic dependency " + dep)
                elif decide(dep, visiting | {cid})["permission"] != "supported":
                    blockers.append("Dependency is not supported within scope: " + dep)
            if snapshot.get("stale"):
                blockers.append("Review context changed; recheck is stale")
            if permission != "withdrawn":
                if checked and not blockers:
                    if any(e["relation"] == "challenges" for e in checked):
                        label, permission = (
                            "Disputed by attached evidence",
                            "unresolved",
                        )
                    else:
                        required = contract["options"]["evidence_requirement"]
                        has_tool = any(
                            e.get("origin") in ("calculated", "measured_api")
                            and e.get("tool_capability")
                            in (
                                "analysis.calculate_bound",
                                "analysis.compare_trials",
                                "inference.run_benchmark",
                            )
                            for e in checked
                        )
                        if required == "scoped_tool_result" and not has_tool:
                            blockers.append(
                                "The required scoped tool result is missing"
                            )
                        else:
                            label, permission = (
                                "Supported within recorded human assessment",
                                "supported",
                            )
                            reasons.append(
                                "Relevance and scope were explicitly assessed by the director; this is not formal proof"
                            )
                elif not blockers:
                    label = "Model-reviewed; external support unverified"
                    if contract["options"]["evidence_requirement"] != "model_review":
                        blockers.append(
                            "Required external evidence has not been assessed"
                        )
                if blockers:
                    label, permission = "Unresolved or incomplete review", "unresolved"
        decision = {
            "claim_id": cid,
            "claim_revision": claim["revision"],
            "label": label,
            "permission": permission,
            "blockers": blockers,
            "reasons": reasons,
            "evidence_ids": [e["id"] for e in evidence],
            "policy_version": POLICY_VERSION,
            "basis_hash": digest(
                {
                    "claim": claim,
                    "findings": findings,
                    "evidence": evidence,
                    "rechecks": snapshot.get("rechecks", []),
                    "dispositions": snapshot.get("dispositions", []),
                    "contract_hash": snapshot["contract_hash"],
                    "stale": snapshot.get("stale", False),
                }
            ),
        }
        results[cid] = decision
        return decision

    for claim in claims:
        decide(claim["claim_id"], set())
    return [results[c["claim_id"]] for c in claims]


def ledger_markdown(snapshot):
    decisions = {x["claim_id"]: x for x in snapshot["decisions"]}
    lines = [
        "## Claim and evidence ledger",
        "",
        "Labels below are computed from the saved review records. Model review is not external verification.",
        "",
    ]
    for claim in snapshot["claims"]:
        d = decisions[claim["claim_id"]]
        lines += [
            f"### {claim['claim_id']} v{claim['revision']}",
            "",
            claim["text"],
            "",
            f"Status: **{d['label']}**",
            f"Scope: {claim['scope']}",
        ]
        lines += ["- " + s for s in d["blockers"]]
        lines += ["- " + s for s in d["reasons"]]
        lines += [""]
    if not snapshot["claims"]:
        lines += [
            "No structured claims were admitted. Saved opening answers remain unverified.",
            "",
        ]
    lines += [
        "## Review coverage",
        "",
        "Coverage is assessed by a model and may omit material. Original answers remain available.",
    ]
    for coverage in snapshot.get("coverage", []):
        lines += [
            f"- {coverage['message_id']}: {coverage['assessment']}. {coverage['omitted_material']}"
        ]
    if snapshot.get("partial_reasons"):
        lines += ["", "Incomplete stages: " + "; ".join(snapshot["partial_reasons"])]
    if snapshot.get("findings"):
        lines += ["", "## Objections and candidate tests", ""]
        for finding in snapshot["findings"]:
            lines += [
                f"- {finding['claim_id']}: {finding['objection']} Candidate test (not an observed result): {finding['candidate_test']}"
            ]
    return "\n".join(lines)
