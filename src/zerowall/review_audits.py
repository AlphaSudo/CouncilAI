"""Scoped audit records. Model descriptors never acquire tool or human authority."""

from .db import digest
from .review_calculations import (
    CAPABILITY_VERSION,
    KIND_TYPES,
    LIMITS,
    UNITS,
    calculation,
)

AUDIT_VERSION = "council-audits-v1"
CAPABILITIES = {
    "version": AUDIT_VERSION,
    "calculations": CAPABILITY_VERSION,
    "units": list(UNITS),
    "quantity_kinds": list(KIND_TYPES),
    "limits": {**LIMITS, "descriptors_per_batch": 8},
    "sources": "Supplied evidence only; no automatic web retrieval",
    "derivations": "Not certified by numerical checks",
}


def evaluate_descriptor(descriptor, evidence):
    kind = descriptor["kind"]
    if kind == "calculation":
        return calculation(descriptor)
    if kind == "resource":
        missing = list(descriptor.get("missing_terms", []))
        terms = descriptor.get("resources", [])
        if not descriptor.get("boundary"):
            missing.append("No system boundary was declared")
        if not terms:
            missing.append("No resource terms were supplied")
        if descriptor.get("is_ratio") and (
            not descriptor.get("numerator") or not descriptor.get("denominator")
        ):
            missing.append("The ratio numerator or denominator is missing")
        missing += [
            term["name"] + " has unknown use"
            for term in terms
            if term.get("value") is None
        ]
        return {
            "origin": "local_record_check",
            "capability_version": AUDIT_VERSION,
            "state": "incomplete" if missing else "pass",
            "reason": "; ".join(missing)
            or "Declared boundary and resource fields are populated",
            "limitations": "Structural accounting only. Resource values, boundary completeness and physical feasibility remain assessments. Static requirements are not assigned continuous consumption.",
        }
    # A reference string is not retrieval. Only evidence actually attached to
    # this assertion/revision is available, and human assessment stays explicit.
    relevant = [
        e
        for e in evidence
        if e.get("claim_id") == descriptor["claim_id"]
        and e.get("claim_revision") == descriptor["claim_revision"]
        and e.get("integrity") == "pass"
        and e.get("content")
    ]
    assessed = [
        e
        for e in relevant
        if e.get("assessment_actor") == "human_director"
        and e.get("assessment_reason")
        and e.get("supported_scope")
    ]
    return {
        "origin": "local_record_check",
        "capability_version": AUDIT_VERSION,
        "state": "pass" if assessed else "unknown",
        "reason": "Supplied evidence has an explicit human scope assessment; see its actual relation and coverage"
        if assessed
        else "Source not checked"
        if not relevant
        else "Source supplied; claim support has not been assessed",
        "evidence_ids": [e["id"] for e in relevant],
        "limitations": "This checks recorded provenance, not source existence from its title/DOI, scientific truth, or support beyond the actual assessed scope.",
    }


def audit_result(descriptor, claim, evidence):
    inputs = {
        "descriptor": descriptor,
        "claim_revision": claim["revision"],
        "claim_hash": digest(
            {
                k: claim.get(k)
                for k in ("text", "scope", "assumptions", "dependency_versions")
            }
        ),
        "evidence": [
            {
                k: e.get(k)
                for k in (
                    "id",
                    "claim_revision",
                    "artifact_hash",
                    "integrity",
                    "assessment_reason",
                    "assessment_actor",
                    "origin",
                    "directness",
                    "supported_scope",
                    "relation",
                    "scope_coverage",
                )
            }
            for e in evidence
            if e.get("claim_id") == claim["claim_id"]
        ],
    }
    if descriptor["claim_revision"] != claim["revision"]:
        result = {
            "state": "unknown",
            "origin": "local_record_check",
            "capability_version": AUDIT_VERSION,
            "reason": "The assertion changed; the original descriptor does not certify this revision",
            "limitations": "Update or re-extract the typed inputs for the revised assertion.",
        }
    else:
        result = evaluate_descriptor(descriptor, evidence)
    return {
        **result,
        "audit_id": descriptor["id"],
        "claim_id": claim["claim_id"],
        "claim_revision": claim["revision"],
        "input_hash": digest(inputs),
        "inputs": inputs,
        "scope": descriptor["scope"],
    }
