"""Portable review snapshots and pure, credential-free policy reconstruction."""

import io
import json
import zipfile
import hashlib
from .db import canonical, digest, DomainError
from .review_policy import publication_decisions, ledger_markdown


def export_review(research, c, chat, include_source_content=True):
    snapshot = research.chat.review.snapshot(c, chat)
    values = {
        "review.json": canonical(snapshot),
        "messages.json": canonical(research.chat.messages(c, chat)),
        "review.md": ledger_markdown(snapshot),
        "chat.json": canonical(chat),
    }
    from .source_exports import export_values
    values.update(export_values(research, c, chat, include_source_content))
    kinds = (
        "chat_review",
        "review_claim",
        "review_finding",
        "review_repair",
        "review_evidence",
        "review_disposition",
        "review_publication",
        "review_group",
        "review_observation",
        "review_concern",
        "call",
        "chat_allowance",
        "chat_capacity",
        "review_family",
        "review_audit",
        "review_audit_result",
        "review_admission", "answer_delivery", "stage_result", "review_warning", "review_quarantine",
        "public_stream", "chat_steering", "finishing_reserve", "review_check_note",
    )
    values["records.json"] = canonical(
        {kind: research.store.list(c, kind, chat["mission_id"]) for kind in kinds}
    )
    for artifact in research.store.list(c, "artifact", chat["mission_id"]):
        try:
            values["artifacts/" + artifact["id"] + ".json"] = canonical(
                research.artifacts.read(artifact)
            )
        except (DomainError, OSError):
            # Preserve an honest invalid integrity result rather than hiding a corrupt source.
            values["artifacts/" + artifact["id"] + ".invalid.json"] = canonical(
                {"integrity": "invalid", "expected_sha256": artifact["sha256"]}
            )
    values = {
        name: research.artifacts.redact(value).encode("utf-8")
        for name, value in values.items()
    }
    manifest = {
        "format": {"reviewed_v1": "zerowall-review-v1", "reviewed_v2": "zerowall-review-v2", "reviewed_v3": "zerowall-review-v3", "reviewed_v4": "zerowall-review-v4"}[snapshot["contract"]["protocol_version"]],
        "files": {
            name: hashlib.sha256(value).hexdigest() for name, value in values.items()
        },
    }
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as pack:
        for name, value in values.items():
            pack.writestr(name, value)
        pack.writestr("manifest.json", canonical(manifest))
    return target.getvalue()


def verify_review_pack(path):
    with zipfile.ZipFile(path) as pack:
        if sum(i.file_size for i in pack.infolist()) > 100_000_000:
            raise ValueError("Review pack exceeds the verification size bound")
        manifest = json.loads(pack.read("manifest.json"))
        if manifest.get("format") not in ("zerowall-review-v1", "zerowall-review-v2", "zerowall-review-v3", "zerowall-review-v4") or set(
            pack.namelist()
        ) != set(manifest["files"]) | {"manifest.json"}:
            raise ValueError("Invalid review pack manifest")
        for name, expected in manifest["files"].items():
            if hashlib.sha256(pack.read(name)).hexdigest() != expected:
                raise ValueError("Review pack integrity failed")
        snapshot = json.loads(pack.read("review.json"))
        expected_format = {"reviewed_v1": "zerowall-review-v1", "reviewed_v2": "zerowall-review-v2", "reviewed_v3": "zerowall-review-v3", "reviewed_v4": "zerowall-review-v4"}.get(snapshot["contract"].get("protocol_version"))
        if manifest["format"] != expected_format:
            raise ValueError("Pack format and frozen protocol do not match")
        if digest(snapshot["contract"]) != snapshot["contract_hash"]:
            raise ValueError("Review contract hash failed")
        if expected_format in ("zerowall-review-v2", "zerowall-review-v3", "zerowall-review-v4"):
            messages = {m["id"]: m for m in json.loads(pack.read("messages.json"))}
            for claim in snapshot["claim_history"]:
                for span in claim["source_spans"]:
                    source = messages[span["message_id"]]["content"]
                    if source[span["start"]:span["end"]] != span["text"] or digest(span["text"]) != span["hash"]:
                        raise ValueError("Atomic assertion source provenance failed")
            for observation in snapshot.get("observations", []):
                span = observation["source_span"]
                source = messages[observation["source_message_id"]]["content"]
                if source[span["start"]:span["end"]] != observation["text"] or digest(observation["text"]) != span["hash"]:
                    raise ValueError("Reported observation source provenance failed")
        for evidence in snapshot.get("evidence", []):
            name = "artifacts/" + evidence["artifact_id"] + ".json"
            evidence["integrity"] = (
                "pass"
                if name in manifest["files"]
                and hashlib.sha256(pack.read(name)).hexdigest()
                == evidence["artifact_hash"]
                else "invalid"
            )
        if expected_format in ("zerowall-review-v3", "zerowall-review-v4"):
            from .review_audits import audit_result
            if digest(snapshot["execution_plan"]) != snapshot["plan_hash"]:
                raise ValueError("Council execution plan hash failed")
            claims = {x["claim_id"]: x for x in snapshot["claims"]}
            checks = [audit_result(a, claims[a["claim_id"]], snapshot["evidence"]) for a in snapshot.get("audit_descriptors", [])]
            if checks != snapshot.get("audit_results", []):
                raise ValueError("Council local audit inputs/results did not reproduce")
            for descriptor in snapshot.get("audit_descriptors", []):
                for span in descriptor["source_spans"]:
                    source = messages[span["message_id"]]["content"]
                    if source[span["start"]:span["end"]] != span["text"] or digest(span["text"]) != span["hash"]:
                        raise ValueError("Audit source provenance failed")
        actual = publication_decisions(snapshot)
        if (
            actual != snapshot["decisions"]
            or digest(actual) != snapshot["decision_hash"]
        ):
            raise ValueError("Publication decisions did not reproduce")
        records = json.loads(pack.read("records.json"))
        for publication in records.get("review_publication", []):
            prior = publication["snapshot"]
            if digest(publication_decisions(prior)) != publication["decision_hash"]:
                raise ValueError("A previous publication decision did not reproduce")
        from .source_exports import verify_extension
        enrichment = verify_extension(pack)
        return {
            "research_replay": enrichment,
            "format": manifest["format"],
            "claims": len(actual),
            "decision_hash": digest(actual),
            "reproduced": True,
            "provider_key_required": False,
        }
