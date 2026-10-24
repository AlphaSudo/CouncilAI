"""Current Council policy: preserve scoped semantics and add bounded audit issues."""

from . import review_policy_v2
from .db import digest

POLICY_VERSION = "generic-publication-v3"


def publication_decisions(snapshot):
    decisions = review_policy_v2.publication_decisions(snapshot)
    for decision in decisions:
        cid, revision = decision["claim_id"], decision["claim_revision"]
        checks = [
            a
            for a in snapshot.get("audit_results", [])
            if a["claim_id"] == cid and a["claim_revision"] == revision
        ]
        for check in checks:
            detail = check["reason"] + " (declared-input check only)"
            if check["state"] == "fail" and decision["permission"] != "withdrawn":
                decision["blockers"].append(detail)
                decision.update(
                    permission="unresolved",
                    review_state="open_issue",
                    decision_suitability="not_eligible_unresolved_issue",
                    label="A declared-input check failed; resolve or narrow the assertion",
                )
            elif check["state"] in ("unknown", "incomplete"):
                decision["required_caveats"].append(detail)
        if snapshot.get("inventory_status") in ("partial", "overflow"):
            decision["required_caveats"].append(
                "Material outside the admitted claim batch remains unreviewed"
            )
        pending = [
            x
            for x in snapshot.get("concerns", [])
            if x["claim_id"] == cid
            and x["kind"] == "new_issue"
            and x.get("review_state") == "not_reviewed"
        ]
        if pending and decision["permission"] != "withdrawn":
            decision["blockers"].extend(
                "New issue awaits author review: " + x["detail"] for x in pending
            )
            decision.update(
                permission="unresolved",
                review_state="open_issue",
                decision_suitability="not_eligible_unresolved_issue",
                label="New issue awaits author review",
            )
        decision["policy_version"] = POLICY_VERSION
        decision["basis_hash"] = digest(
            {
                "scoped_basis": decision["basis_hash"],
                "audits": checks,
                "pending_concerns": pending,
                "inventory": snapshot.get("inventory_status"),
                "plan_hash": snapshot.get("plan_hash"),
            }
        )
    by_id = {d["claim_id"]: d for d in decisions}
    claims = {c["claim_id"]: c for c in snapshot["claims"]}
    # A new local-check blocker must propagate after the inherited policy has
    # computed its decisions; otherwise a formerly supported prerequisite could
    # leave a dependent recommendation eligible.
    changed = True
    while changed:
        changed = False
        for cid, decision in by_id.items():
            if decision["permission"] == "withdrawn":
                continue
            for dependency in claims[cid].get("dependencies", []):
                if dependency not in by_id:
                    continue
                prior = by_id[dependency]
                reason = (
                    "Dependency "
                    + dependency
                    + " has an unresolved current check or withdrawn assertion"
                )
                if (
                    prior["blockers"] or prior["permission"] == "withdrawn"
                ) and reason not in decision["blockers"]:
                    decision["blockers"].append(reason)
                    decision.update(
                        permission="unresolved",
                        review_state="open_issue",
                        decision_suitability="not_eligible_unresolved_issue",
                        label="A current dependency requires recheck",
                    )
                    changed = True
    for decision in decisions:
        decision["basis_hash"] = digest(
            {
                "local_basis": decision["basis_hash"],
                "current_dependency_states": {
                    dep: {
                        "permission": by_id[dep]["permission"],
                        "blockers": by_id[dep]["blockers"],
                    }
                    if dep in by_id
                    else None
                    for dep in claims[decision["claim_id"]].get("dependencies", [])
                },
            }
        )
    return decisions


def ledger_markdown(snapshot):
    text = review_policy_v2.ledger_markdown(snapshot)
    lines = [text, "", "## Scoped checks", ""]
    for result in snapshot.get("audit_results", []):
        lines.append(
            "- "
            + result["claim_id"]
            + ": "
            + result["state"]
            + " — "
            + result["reason"]
        )
    if not snapshot.get("audit_results"):
        lines.append(
            "No typed local checks were admitted. This is not a complete equation or source audit."
        )
    lines += ["", "Coverage: " + snapshot.get("inventory_limitations", "Not assessed")]
    return "\n".join(lines)
