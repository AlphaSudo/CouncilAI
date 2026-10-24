"""Conservative transport normalization; provenance and coverage stay strict."""

from copy import deepcopy
import json
import math
import re

from pydantic import ValidationError

from .db import DomainError

VERSION = "council-admission/5"
MAX_REVIEW_REPLY_BYTES = 4 * 1024 * 1024
COMMENTARY_FIELDS = {
    "note",
    "notes",
    "rationale",
    "commentary",
    "summary",
    "explanation",
    "limitations",
    "evidence_obligation",
}
AUTHORITY_FIELDS = {
    "origin", "trusted", "verified", "human_verified", "trusted_verification",
    "permission", "permissions", "assessment_actor", "tool_capability",
    "execution_result", "financial_authorization", "budget_override",
}
EDITORIAL_FALLBACKS = {
    "reason": "No explanation supplied by the model; this remains an unverified assessment.",
    "limitations": "Limitations were not supplied by the model.",
    "explanation": "No overview supplied; see the individual responses below.",
    "inventory_limitations": "Inventory limitations were not supplied by the model.",
    "observation_coverage": "Observation coverage was not explained by the model.",
    "remaining_uncertainty": "Remaining uncertainty was not described by the model.",
    "assumptions": "Assumptions were not supplied by the model.",
    "resources": "Resource details were not supplied by the model.",
}
NUMERIC_TEXT_FIELDS = {"value", "uncertainty", "expected_value", "absolute_tolerance"}
# These fields contain public prose, never identifiers, executable expressions,
# quantity units, numeric operands, enums or provider/financial controls.
PROSE_FIELDS = {
    "assumptions", "resources", "reason", "rationale", "explanation", "limitations",
    "scope", "assertion", "materiality", "evidence_obligation", "boundary",
    "description", "mechanism", "distinguishing_test", "steelman", "objection",
    "candidate_test", "decision_impact", "minimum_resolution", "target",
    "in_scope_reason", "method", "disconfirming_outcome", "baseline", "threshold_basis",
    "comparison", "test_reason", "detail", "affected_scope", "text", "response",
    "revised_text", "revised_scope", "remaining_uncertainty", "omitted_material",
    "observation_coverage", "inventory_limitations", "deliverable_limitations",
    "trace_reference", "reference", "claimed_support",
}
FORMAT_RULES = (
    "Use the exact response_schema enums and field types. reasoning_kind must be "
    "definition, deduction, empirical, proposal, evaluation or unclear; calculation "
    "and quantitative are not reasoning_kind values. Use unclear when no listed "
    "kind applies. Quantitative belongs in properties. An unspecified audit "
    "absolute_tolerance is the string unknown, not null or an invented zero. "
    "Do not count equivalent grouped claims as distinct approach families. "
    "Every observation needs a reason explaining its classification; if no rationale "
    "is available, say it was not supplied and keep observation_status partial. "
    "Audit numerator and denominator are text descriptions: use empty strings "
    "when unspecified or not applicable, never null. Do not invent ratio terms. "
    "Approach-family assumptions and resources are readable prose; lists of notes "
    "are also retained and rendered locally without changing their content. "
    "Keep all required source, coverage and current-revision references exact."
)
MISSING_OBSERVATION_REASON = (
    "Classification rationale not supplied by the extractor; observation remains unverified."
)


def check_envelope(content):
    if len(content.encode("utf-8")) > MAX_REVIEW_REPLY_BYTES:
        raise DomainError(
            "The structured review reply exceeds the 4 MiB response safety envelope. Raw output and charges are saved; no automatic retry was made.",
            422,
        )


def prose_text(value):
    """Render supplied JSON notes as readable text without dropping nested values."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join("- " + prose_text(item).replace("\n", "\n  ") for item in value)
    if isinstance(value, dict):
        return "\n".join(str(key) + ": " + prose_text(item).replace("\n", "\n  ")
                         for key, item in value.items())
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def normalize_transport(value, schema):
    """Normalize presentation without manufacturing sources, decisions or revisions."""
    value = deepcopy(value)
    changes = []
    definitions = schema.get("$defs", {})

    def resolve(rule):
        while "$ref" in rule:
            rule = definitions[rule["$ref"].split("/")[-1]]
        return rule

    def walk(node, rule, path):
        rule = resolve(rule)
        field = next((part for part in reversed(path) if isinstance(part, str)), "")
        if "anyOf" in rule:
            options = [resolve(option) for option in rule["anyOf"]]
            if node is None and any(option.get("type") == "null" for option in options):
                return None
            rule = next(
                (
                    option
                    for option in options
                    if option.get("type")
                    == (
                        "null"
                        if node is None
                        else "string"
                        if isinstance(node, str)
                        else "array"
                        if isinstance(node, list)
                        else "object"
                    )
                ),
                rule,
            )
            if type(node) in (int, float) and path and path[-1] in NUMERIC_TEXT_FIELDS:
                rule = next((option for option in options if option.get("type") == "string"), rule)
            if field in PROSE_FIELDS and isinstance(node, (list, dict)):
                rule = next((option for option in options if option.get("type") == "string"
                             and not option.get("enum") and not option.get("pattern")), rule)
        if rule.get("type") == "string" and type(node) in (int, float) and path and path[-1] in NUMERIC_TEXT_FIELDS:
            if isinstance(node, int) or math.isfinite(node):
                rendered = json.dumps(node, allow_nan=False)
                changes.append({"kind": "numeric_text", "path": path, "before": node,
                                "after": rendered, "reason": "Preserved supplied numeric data as schema text"})
                return rendered
        if (rule.get("type") == "string" and not rule.get("enum") and not rule.get("pattern")
            and field in PROSE_FIELDS and isinstance(node, (list, dict))):
            rendered = prose_text(node)
            if not node and field in EDITORIAL_FALLBACKS:
                rendered = EDITORIAL_FALLBACKS[field]
            changes.append({"kind": "structured_prose", "path": path,
                            "before": deepcopy(node), "after": rendered,
                            "reason": "Supplied descriptive notes rendered as readable prose; all original values remain saved"})
            return rendered
        if rule.get("type") == "array" and not isinstance(node, list) and node is not None:
            item = resolve(rule.get("items", {}))
            expected = item.get("type")
            if (expected == "string" and isinstance(node, str)
                or expected == "object" and isinstance(node, dict)
                or expected == "integer" and type(node) is int):
                changes.append({"kind": "singleton_list", "path": path, "before": deepcopy(node),
                                "after": [deepcopy(node)], "reason": "One supplied item represented as a list, without splitting or dropping content"})
                node = [node]
        if isinstance(node, str) and rule.get("enum"):
            canonical = lambda item: re.sub(r"[\s_-]+", "_", item.strip().casefold())
            matches = [
                item
                for item in rule["enum"]
                if isinstance(item, str) and canonical(item) == canonical(node)
            ]
            if len(matches) == 1 and matches[0] != node:
                changes.append(
                    {
                        "kind": "canonical_enum",
                        "path": path,
                        "before": node,
                        "after": matches[0],
                        "reason": "Exact enum words with case, whitespace and separators normalized",
                    }
                )
                return matches[0]
        if isinstance(node, dict) and "properties" in rule:
            fields = rule["properties"]
            required = rule.get("required", [])
            for key in required:
                if key not in EDITORIAL_FALLBACKS:
                    continue
                field_rule = resolve(fields[key])
                text = node.get(key)
                if field_rule.get("type") == "string" and (text is None or isinstance(text, str) and not text.strip()):
                    node[key] = EDITORIAL_FALLBACKS[key]
                    changes.append({"kind": "missing_editorial_note", "path": path + [key],
                                    "before": text, "after": node[key],
                                    "reason": "Disclosed missing commentary without inventing a model assessment"})
            for key in list(node):
                text = node[key]
                commentary = (
                    text is None
                    or isinstance(text, str)
                    or isinstance(text, list)
                    and all(isinstance(item, str) for item in text)
                )
                if key not in fields and key in COMMENTARY_FIELDS and commentary:
                    changes.append(
                        {
                            "kind": "supplementary_commentary",
                            "path": path + [key],
                            "before": node.pop(key),
                            "after": None,
                            "reason": "Preserved as unverified model commentary outside authoritative fields",
                        }
                    )
                elif key not in fields and key not in AUTHORITY_FIELDS:
                    changes.append({"kind": "supplementary_field", "path": path + [key],
                                    "before": node.pop(key), "after": None,
                                    "reason": "Extra model data retained outside authoritative schema fields; it grants no evidence or permissions"})
                elif key in fields:
                    field_rule = resolve(fields[key])
                    # Only absent optional collections and empty-text defaults are equivalent.
                    # Never infer numeric defaults, units, positive checks or permissions.
                    optional_empty = key not in required and (
                        field_rule.get("type") == "array" and not field_rule.get("minItems")
                        or field_rule.get("default") == ""
                    )
                    if text is None and optional_empty:
                        replacement = [] if field_rule.get("type") == "array" else ""
                        changes.append({"kind": "optional_empty", "path": path + [key],
                                        "before": None, "after": replacement,
                                        "reason": "Optional null represented as its empty collection or empty-text default"})
                        node[key] = replacement
                    node[key] = walk(node[key], fields[key], path + [key])
        elif isinstance(node, list) and "items" in rule:
            for index, item in enumerate(node):
                node[index] = walk(item, rule["items"], path + [index])
        return node

    return walk(value, schema, []), changes


def commentary_text(changes):
    notes = []
    for change in changes:
        if change.get("kind") != "supplementary_commentary" or change["before"] is None:
            continue
        value = change["before"]
        notes.append(
            "**"
            + ".".join(map(str, change["path"]))
            + "**: "
            + ("; ".join(value) if isinstance(value, list) else value)
        )
    return (
        "\n\nSupplementary model commentary (unverified):\n\n" + "\n\n".join(notes)
        if notes
        else ""
    )


def normalize_extraction(value):
    """Retain uncertain classifications as uncertain, never invent a deduction."""
    value = deepcopy(value)
    changes = []
    if not isinstance(value, dict):
        return value, changes
    claims = value.get("claims")
    for index, claim in enumerate(claims if isinstance(claims, list) else []):
        if isinstance(claim, dict) and claim.get("reasoning_kind") in (
            "calculation",
            "quantitative",
        ):
            changes.append(
                {
                    "path": ["claims", index, "reasoning_kind"],
                    "before": claim["reasoning_kind"],
                    "after": "unclear",
                    "reason": "Descriptive label preserved; reasoning category remains unclear",
                }
            )
            claim["reasoning_kind"] = "unclear"
    observations = value.get("observations")
    missing_reasons = False
    for index, observation in enumerate(observations if isinstance(observations, list) else []):
        if not isinstance(observation, dict):
            continue
        reason = observation.get("reason")
        if reason is None or isinstance(reason, str) and not reason.strip():
            missing_reasons = True
            observation["reason"] = MISSING_OBSERVATION_REASON
            changes.append({
                "kind": "missing_observation_rationale",
                "path": ["observations", index, "reason"],
                "before": reason,
                "after": MISSING_OBSERVATION_REASON,
                "reason": "Explicitly record a missing rationale; no model explanation or verification was inferred",
            })
    if missing_reasons:
        if value.get("observation_status", "partial") == "complete_as_assessed":
            changes.append({
                "kind": "incomplete_observation_assessment",
                "path": ["observation_status"],
                "before": "complete_as_assessed",
                "after": "partial",
                "reason": "Missing classification rationales prevent a complete assessment",
            })
            value["observation_status"] = "partial"
    audits = value.get("audits")
    for index, audit in enumerate(audits if isinstance(audits, list) else []):
        if not isinstance(audit, dict):
            continue
        for field in ("numerator", "denominator"):
            if field in audit and audit[field] is None:
                changes.append({
                    "kind": "unspecified_ratio_term",
                    "path": ["audits", index, field],
                    "before": None,
                    "after": "",
                    "reason": "Null ratio text stays unspecified; no numeric value or ratio term was inferred",
                })
                audit[field] = ""
        if (
            "absolute_tolerance" in audit
            and audit["absolute_tolerance"] is None
        ):
            changes.append(
                {
                    "path": ["audits", index, "absolute_tolerance"],
                    "before": None,
                    "after": "unknown",
                    "reason": "Missing tolerance stays unknown; no numeric tolerance was inferred",
                }
            )
            audit["absolute_tolerance"] = "unknown"
    return value, changes


def normalize_inventory(value, units_by_source):
    """An auxiliary index with bad links is a warning, never source evidence."""
    value = deepcopy(value)
    changes, linked = [], []
    refs = {claim["ref"] for claim in value["claims"]}
    for index, item in enumerate(value["inventory"]):
        units = units_by_source.get(item["source_message_id"], set())
        if set(item["source_unit_ids"]) <= units and set(item["claim_refs"]) <= refs:
            linked.append(item)
        else:
            changes.append({"kind": "unlinked_inventory_note", "path": ["inventory", index],
                            "before": item, "after": None,
                            "reason": "Auxiliary index entry has unresolved links; retained as an unverified note, excluded from linked inventory"})
    if changes or not linked:
        value["inventory"] = linked
        note = " Some auxiliary index entries are unlinked or unavailable; the linked inventory is incomplete."
        replacements = {
            "inventory_status": "overflow" if value["inventory_status"] == "overflow" else "partial",
            "inventory_limitations": value["inventory_limitations"] if value["inventory_limitations"].endswith(note)
            else value["inventory_limitations"] + note,
        }
        for key, replacement in replacements.items():
            if value[key] != replacement:
                changes.append({"kind": "incomplete_inventory", "path": [key],
                                "before": value[key], "after": replacement,
                                "reason": "Missing auxiliary links are disclosed as incomplete, never certified"})
                value[key] = replacement
    return value, changes


def normalize_recheck(value, snapshot):
    """Unsupported model closure becomes unresolved, without rewriting the author."""
    value = deepcopy(value)
    changes = []
    findings = {item["id"]: item for item in snapshot["findings"]}
    claims = {item["claim_id"]: item for item in snapshot["claims"]}
    answered = {finding_id for repair in snapshot.get("repairs", []) for finding_id in repair["finding_ids"]}
    revision_bases = {"content_removed", "scope_narrowed", "condition_explicit", "actual_correction"}
    for index, assessment in enumerate(value["assessments"]):
        finding = findings.get(assessment["finding_id"])
        claim = claims.get(finding["claim_id"]) if finding else None
        if not claim:
            continue  # Unknown links are never inferred; strict linking will reject them.
        if (finding.get("origin") in ("peer_challenge", "recheck_concern")
            and finding["id"] not in answered and assessment["resolution"] != "withdrawn"):
            continue  # Existing late-challenge handling leaves it open for a legitimate focused exchange.
        reason = None
        if assessment["resolution"] == "withdrawn" and claim["lifecycle"] != "withdrawn":
            reason = "The reviewer cannot withdraw a claim on the author's behalf."
        elif assessment["closure_basis"] in revision_bases and claim["revision"] <= finding["claim_revision"]:
            reason = "The claimed author correction has no corresponding saved revision."
        elif assessment["resolution"] == "resolved_as_assessed" and assessment["closure_basis"] == "no_effective_change":
            reason = "The reviewer supplied no effective basis for closing the objection."
        if reason:
            before = deepcopy(assessment)
            assessment.update(resolution="unresolved_as_assessed", closure_basis="no_effective_change",
                              comparison=reason + " The objection remains open. Reviewer note: " + assessment["comparison"])
            changes.append({"kind": "unsupported_recheck_closure", "path": ["assessments", index],
                            "before": before, "after": deepcopy(assessment), "reason": reason})
    families = {item["id"]: item for item in snapshot.get("families", [])}
    supplied = value.get("families", [])
    counts = {item["family_id"]: sum(other["family_id"] == item["family_id"] for other in supplied)
              for item in supplied}
    linked = []
    for index, assessment in enumerate(supplied):
        family = families.get(assessment["family_id"])
        ids, versions = assessment["claim_ids"], assessment["claim_revisions"]
        valid = (family is not None and counts[assessment["family_id"]] == 1
                 and len(ids) == len(set(ids)) == len(versions)
                 and set(ids) == {item["claim_id"] for item in family["members"]}
                 and all(claims.get(cid, {}).get("revision") == version for cid, version in zip(ids, versions)))
        if valid:
            linked.append(assessment)
        else:
            changes.append({"kind": "unlinked_family_recheck", "path": ["families", index],
                            "before": assessment, "after": None,
                            "reason": "Unknown, repeated or stale approach assessment remains unreviewed; no linkage was inferred"})
    missing = sorted(set(families) - {item["family_id"] for item in linked})
    if missing:
        changes.append({"kind": "incomplete_family_recheck", "path": ["families"],
                        "before": missing, "after": "not_reviewed",
                        "reason": "Missing approach assessments do not discard valid finding assessments"})
    value["families"] = linked
    return value, changes


def family_conflicts(families, equivalent_groups):
    """Return both sides of conflicts, without choosing a preferred mechanism."""
    conflicts = {}
    for index, left in enumerate(families):
        for right in families[index + 1 :]:
            reason = None
            if left["members"] == right["members"]:
                reason = "The families use the same claim membership"
            elif " ".join(left["mechanism"].casefold().split()) == " ".join(
                right["mechanism"].casefold().split()
            ):
                reason = "The families repeat the same mechanism"
            elif any(
                left["members"] & group and right["members"] & group
                for group in equivalent_groups
            ):
                reason = "Claims assessed equivalent are split across purportedly distinct families"
            if reason:
                for family in (left, right):
                    conflicts.setdefault(family["key"], set()).add(reason)
    return {key: sorted(reasons) for key, reasons in conflicts.items()}


def failure_message(phase, error):
    while error.__cause__:
        error = error.__cause__
    if isinstance(error, ValidationError):
        details = []
        for item in error.errors(
            include_input=False, include_context=False, include_url=False
        )[:4]:
            path = ".".join(map(str, item["loc"]))
            details.append(f"{path}: {item['msg']}")
        reason = "; ".join(details)
    elif isinstance(error, KeyError):
        reason = "An unknown source, claim, family or evidence reference was returned"
    elif isinstance(error, (StopIteration, TypeError, RecursionError)):
        reason = "Required references or structured fields could not be resolved"
    elif isinstance(error, DomainError):
        reason = error.message
    else:
        reason = str(error)[:500] or "Required output validation failed"
    return (
        f"Council {phase} reply was not admitted: {reason}. "
        "The raw reply and charges are saved. No automatic retry was made."
    )
