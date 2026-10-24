"""Offline source and price replay, independent of generation credentials/network."""

import base64
import hashlib
import json

from .db import DomainError, canonical
from .pricing import calculate

KINDS = (
    "source_dependency_notice",
    "source",
    "source_version",
    "source_chunk",
    "library_snapshot",
    "source_read",
    "citation_binding",
    "research_gap",
    "research_note",
    "tool_invocation",
    "tool_receipt",
    "research_checkpoint",
    "research_plan",
    "context_pack",
    "context_compaction",
    "resource_reservation",
    "search_credit",
    "usage_record",
)


def export_values(research, c, chat, include_content=True):
    records = {kind: research.store.list(c, kind, chat["mission_id"]) for kind in KINDS}
    omitted_versions = {
        v["id"]
        for v in records["source_version"]
        if not include_content or v.get("export_policy") == "reference_only"
    }
    records["source_chunk"] = [
        {k: v for k, v in chunk.items() if k != "text"} | {"text_omitted": True}
        if chunk["version_id"] in omitted_versions
        else chunk
        for chunk in records["source_chunk"]
    ]
    accounting = research.accounting.projection(c, chat)
    values = {
        "accounting.json": canonical(accounting),
        "research-records.json": canonical(records),
    }
    inventory = []
    for version in records["source_version"]:
        item = {
            "version_id": version["id"],
            "policy": version.get("export_policy", "include"),
            "included": [],
            "missing": [],
        }
        for key in ("raw_sha256", "text_sha256"):
            sha = version[key]
            if not include_content or version.get("export_policy") == "reference_only":
                item["missing"].append(sha)
                continue
            try:
                raw = research.library.read_blob(sha)
                values["source-blobs/" + sha + ".json"] = canonical(
                    {
                        "sha256": sha,
                        "encoding": "base64",
                        "data": base64.b64encode(raw).decode(),
                    }
                )
                item["included"].append(sha)
            except DomainError:
                item["missing"].append(sha)
        inventory.append(item)
    values["source-inventory.json"] = canonical(
        {
            "version": "sources/1",
            "sources": inventory,
            "offline_replay_complete": all(not v["missing"] for v in inventory),
            "reference_only_policy": "Full source blobs and index text omitted; excerpts already in messages or recorded provider exchanges may remain.",
        }
    )
    return values


def verify_extension(pack):
    if "accounting.json" not in pack.namelist():
        return {
            "accounting": "historical_not_present",
            "sources": "historical_not_present",
        }
    accounting = json.loads(pack.read("accounting.json"))
    for attempt in accounting["attempts"]:
        expected = calculate(
            attempt["usage"],
            attempt["price_card"],
            attempt["cost"]["provider_reported_amount_usd"],
            algorithm_version=attempt["cost"]["version"],
        )
        if expected != attempt["cost"]:
            raise ValueError("Frozen accounting estimate did not reproduce")
    inventory = json.loads(pack.read("source-inventory.json"))
    for version in inventory["sources"]:
        for sha in version["included"]:
            item = json.loads(pack.read("source-blobs/" + sha + ".json"))
            if (
                hashlib.sha256(
                    base64.b64decode(item["data"], validate=True)
                ).hexdigest()
                != sha
            ):
                raise ValueError("Source blob hash did not reproduce")
    return {
        "accounting": "reproduced",
        "sources": "reproduced"
        if inventory["offline_replay_complete"]
        else "reference_only_or_missing",
        "offline_replay_complete": inventory["offline_replay_complete"],
    }
