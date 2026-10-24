"""Protocol invariants, not independent labels of live model reasoning quality."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_council_chat import drain
from test_workflow import post

from zerowall.db import digest
from zerowall.review_policy import publication_decisions
from zerowall.review_provenance import observation_cues


def create(client, models=None):
    return post(
        client,
        "/chats",
        {
            "prompt": "Compare two designs under a zero-spend constraint, preserving necessary conditions.",
            "provider": "fixture",
            "models": models or ["demo/analyst", "demo/critic", "demo/builder"],
            "mode": "reviewed",
            "review_protocol": "reviewed_v2",
            "max_rounds": 1,
        },
    )


def completed(client, app):
    v = create(client)
    drain(app)
    v = client.get("/api/chats/" + v["chat"]["id"]).json()
    assert v["chat"]["status"] == "completed", v["chat"].get("error")
    return v


def test_frozen_legacy_publications_keep_exact_decision_hashes():
    baseline = json.loads(
        (
            Path(__file__).resolve().parents[1] / "benchmark/review_v1_baseline.json"
        ).read_text()
    )
    assert len(baseline["publications"]) == 2
    for p in baseline["publications"]:
        assert digest(publication_decisions(p["snapshot"])) == p["decision_hash"]


def test_scoped_cycle_closes_narrowed_objections_without_creating_evidence(client, app):
    v = completed(client, app)
    r = v["review"]
    assert r["contract"]["protocol_version"] == "reviewed_v2"
    assert len([m for m in v["messages"] if m["phase"] != "prompt"]) == 10
    assert all(d["permission"] == "conditional" for d in r["decisions"])
    assert all(d["review_state"] == "complete_as_assessed" for d in r["decisions"])
    assert all(d["evidence_state"] == "model_reasoning_only" for d in r["decisions"])
    assert all(d["residual_risks"] for d in r["decisions"])
    assert all(c["source_spans"] and c["revision"] == 2 for c in r["claims"])
    assert r["groups"][0][
        "stale"
    ]  # grouping never follows a changed claim automatically
    assert not r["synthesis_fallback"]
    assert not v["chat"]["accepted"]


def test_preview_and_creation_share_profile_and_budget(client, app):
    preview = client.get(
        "/api/chats/preview",
        params={
            "provider": "fixture",
            "mode": "reviewed",
            "review_protocol": "reviewed_v2",
            "models": "demo/analyst,demo/critic",
            "max_rounds": 1,
        },
    ).json()
    v = create(client, ["demo/analyst", "demo/critic"])
    assert preview["planned_calls"] == v["remaining_planned_calls"] == 8
    assert preview["required_start"] == 11
    assert (
        preview["claims_per_author"]
        == v["review"]["contract"]["claims_per_author"]
        == 2
    )


@pytest.mark.parametrize(
    "change",
    [
        "unresolved",
        "partial",
        "new_issue",
        "material_risk",
        "unknown_revision",
        "empirical",
    ],
)
def test_real_blockers_and_evidence_gaps_survive_model_closure(client, app, change):
    s = deepcopy(completed(client, app)["review"])
    a = s["rechecks"][0]
    if change == "unresolved":
        a["resolution"] = "unresolved_as_assessed"
    elif change == "partial":
        a["resolution"] = "partly_resolved_as_assessed"
        a["concerns"] = [
            {
                "kind": "missing_evidence",
                "detail": "A material disputed mechanism still lacks support",
                "affected_scope": "Current assertion",
                "materiality": "decision_changing",
            }
        ]
    elif change in {"new_issue", "material_risk"}:
        a["concerns"] = [
            {
                "kind": "new_issue" if change == "new_issue" else "residual_risk",
                "detail": "A hard requirement may remain unmet",
                "affected_scope": "The requested decision",
                "materiality": "decision_changing",
            }
        ]
    elif change == "unknown_revision":
        a["claim_revision"] = 99
    else:
        s["claims"][0]["reasoning_kind"] = "empirical"
    d = publication_decisions(s)[0]
    assert not d["decision_suitability"].startswith("recommendation_eligible")
    assert d["permission"] != "supported"


def test_cue_scan_keeps_exact_source_and_distinguishes_hypothetical_context():
    text = "#### Observed Results (personal testing)\nManual copy took 30 s.\nIf a restore took 3 s, that would be hypothetical."
    warnings = observation_cues({"id": "opening1", "content": text})
    assert len(warnings) == 3
    assert warnings[1]["classification"] == "unsupported_self_report"
    assert warnings[2]["classification"] == "context_requires_assessment"
    for w in warnings:
        span = w["source_span"]
        assert text[span["start"] : span["end"]] == w["text"]
        assert digest(w["text"]) == span["hash"]


def test_partial_repair_can_support_only_current_conditional_scope_with_ordinary_concerns(
    client, app
):
    s = deepcopy(completed(client, app)["review"])
    s["rechecks"][0]["resolution"] = "partly_resolved_as_assessed"
    s["rechecks"][0]["closure_basis"] = "scope_narrowed"
    d = publication_decisions(s)[0]
    assert d["permission"] == "conditional" and d["review_state"] == "partly_addressed"
    assert d["evidence_state"] == "model_reasoning_only"
    assert "narrowed assertion" in " ".join(d["required_caveats"])


@pytest.mark.parametrize(
    "phase", ["extraction", "scrutiny", "repair", "recheck", "synthesis"]
)
def test_bad_scoped_output_retains_sources_and_never_partially_admits(
    client, app, monkeypatch, phase
):
    review = app.state.research.chat.review
    original = review.demo

    def bad(c, chat, messages, turn):
        raw = original(c, chat, messages, turn)
        if turn["phase"] == phase:
            if phase == "extraction":
                value = json.loads(raw)
                value["claims"][-1]["source_unit_ids"] = ["invented"]
                return json.dumps(value)
            return '{"authority":"verified"}'
        return raw

    monkeypatch.setattr(review, "demo", bad)
    v = create(client)
    drain(app)
    v = client.get("/api/chats/" + v["chat"]["id"]).json()
    assert len([m for m in v["messages"] if m["phase"] == "opening"]) == 3
    if phase == "synthesis":
        assert v["chat"]["status"] == "completed" and v["review"]["synthesis_fallback"]
    else:
        assert v["chat"]["status"] == "failed"
    if phase == "extraction":
        assert not v["review"]["claims"] and not v["review"]["groups"]


def test_unknown_or_mismatched_policy_cannot_reinterpret_snapshots(client, app):
    s = completed(client, app)["review"]
    s["contract"]["policy_version"] = "generic-publication-v1"
    with pytest.raises(ValueError):
        publication_decisions(s)
