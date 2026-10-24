import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_council_review import mutate_review
from test_scoped_review import completed, create

from zerowall.contracts import ChatCreate
from zerowall.db import digest
from zerowall.quality import summarize_quality
from zerowall.quality_v2 import ScopedQualityLabels
from zerowall.review_exports import export_review, verify_review_pack
from zerowall.review_policy import publication_decisions


def test_partial_scope_risk_acceptance_and_groups_do_not_transfer_support(client, app):
    v = completed(client, app)
    claim = v["review"]["claims"][0]
    base = {
        "claim_id": claim["claim_id"],
        "claim_revision": claim["revision"],
        "content": "A scoped source supplied by a human; no experiment is asserted.",
        "provenance": "Director-authored narrow source",
        "relation": "supports",
        "assessment_reason": "This supports only the stated workflow demonstration scope.",
        "supported_scope": "Only one aspect, not the entire assertion",
        "scope_coverage": "partial",
    }
    v = mutate_review(client, v, "evidence", base)
    assert v["review"]["decisions"][0]["evidence_state"] == "partially_assessed_scope"
    assert all(d["permission"] != "supported" for d in v["review"]["decisions"])
    v = mutate_review(
        client,
        v,
        "evidence",
        {
            **base,
            "scope_coverage": "whole_claim_as_assessed",
            "supported_scope": claim["scope"],
        },
    )
    assert v["review"]["decisions"][0]["permission"] == "supported"
    assert all(d["permission"] != "supported" for d in v["review"]["decisions"][1:])
    changed = deepcopy(v["review"])
    changed["claims"][0]["revision"] += 1
    assert publication_decisions(changed)[0]["permission"] != "supported"


def test_whole_opening_observation_warning_survives_extraction_omission(
    client, app, monkeypatch, tmp_path
):
    review = app.state.research.chat.review
    demo = review.demo

    def anecdote(c, chat, messages, turn):
        raw = demo(c, chat, messages, turn)
        if turn["phase"] == "opening":
            return (
                "#### Observed Results (personal testing)\nManual copy took 30 s.\n\n"
                + raw
            )
        return raw

    monkeypatch.setattr(review, "demo", anecdote)
    v = completed(client, app)
    assert len(v["review"]["observations"]) == 6
    assert any(
        "Unsupported model-reported" in x
        for d in v["review"]["decisions"]
        for x in d["required_caveats"]
    )
    for o in v["review"]["observations"]:
        m = next(m for m in v["messages"] if m["id"] == o["source_message_id"])
        p = o["source_span"]
        assert m["content"][p["start"] : p["end"]] == o["text"]
    r = app.state.research
    with r.store.tx() as c:
        pack = export_review(r, c, v["chat"])
    path = tmp_path / "review.zip"
    path.write_bytes(pack)
    assert verify_review_pack(path)["format"] == "zerowall-review-v2"


@pytest.mark.parametrize(
    "corruption",
    [
        "duplicate_group",
        "invented_source",
        "spoofed_authority",
        "missing_coverage",
        "compound_over_budget",
    ],
)
def test_atomic_batches_rollback_all_record_kinds_when_invalid(
    client, app, monkeypatch, corruption
):
    review = app.state.research.chat.review
    demo = review.demo

    def bad(c, chat, messages, turn):
        raw = demo(c, chat, messages, turn)
        if turn["phase"] == "extraction":
            x = json.loads(raw)
            if corruption == "duplicate_group":
                x["groups"][0]["refs"] = ["C1", "C1"]
            elif corruption == "invented_source":
                x["claims"][-1]["source_unit_ids"] = ["other-author:fake"]
            elif corruption == "spoofed_authority":
                x["claims"][0]["permission"] = "supported"
            elif corruption == "missing_coverage":
                x["coverage"].pop()
            else:
                for i in range(2):
                    z = deepcopy(x["claims"][0])
                    z["ref"] = f"C{6 + i}"
                    x["claims"].append(z)
            return json.dumps(x)
        return raw

    monkeypatch.setattr(review, "demo", bad)
    v = create(client)
    from test_council_chat import drain

    drain(app)
    v = client.get("/api/chats/" + v["chat"]["id"]).json()
    assert v["chat"]["status"] == "failed"
    assert not v["review"]["claims"] and not v["review"]["groups"]


@pytest.mark.parametrize(
    "mutation",
    [
        "original_revision",
        "current_revision",
        "unearned_scope_narrowing",
        "critic_withdrawal",
        "too_many_new_issues",
    ],
)
def test_recheck_cannot_rewrite_history_or_grant_authority(
    client, app, monkeypatch, mutation
):
    review = app.state.research.chat.review
    demo = review.demo

    def bad(c, chat, messages, turn):
        raw = demo(c, chat, messages, turn)
        if turn["phase"] == "recheck":
            x = json.loads(raw)
            a = x["assessments"][0]
            if mutation in ("original_revision", "current_revision"):
                a[mutation] = 99
            elif mutation == "unearned_scope_narrowing":
                a["closure_basis"] = "no_effective_change"
            elif mutation == "critic_withdrawal":
                a["resolution"] = "withdrawn"
            else:
                a["concerns"] = [
                    {
                        "kind": "new_issue",
                        "detail": "A new concern not seen by its author",
                        "affected_scope": "Requested decision",
                        "materiality": "decision_changing",
                    }
                ] * 2
            return json.dumps(x)
        return raw

    monkeypatch.setattr(review, "demo", bad)
    v = create(client)
    from test_council_chat import drain

    drain(app)
    v = client.get("/api/chats/" + v["chat"]["id"]).json()
    assert v["chat"]["status"] == "failed"
    assert not v["review"]["rechecks"] and not v["review"]["concerns"]


def test_scoped_protocol_is_default_and_cannot_be_used_for_discussion():
    assert (
        ChatCreate(
            prompt="A useful prompt", models=["a", "b"], mode="reviewed", max_rounds=1
        ).review_protocol
        == "reviewed_v4"
    )
    with pytest.raises(ValidationError):
        ChatCreate(
            prompt="A useful prompt", models=["a", "b"], mode="discussion", review_protocol="reviewed_v2"
        )


def test_scoped_quality_pending_is_unknown_not_zero_accuracy():
    root = Path(__file__).resolve().parents[1]
    value = json.loads((root / "benchmark/review_quality_v2_template.json").read_text())
    out = summarize_quality(value)
    assert out["quality_status"] == "independent_quality_pending"
    assert out["arms"]["v2"]["false_closure"]["rate"] is None
    tasks = json.loads((root / "benchmark/review_102_tasks.json").read_text())
    assert digest(tasks["tasks"]) == value["task_set_hash"]
    assert len(tasks["tasks"]) == 8
    assert len({x["category"] for x in tasks["tasks"]}) == 4


def test_quality_rejects_counts_above_denominators():
    fields = ScopedQualityLabels.model_fields
    value = {
        k: 0
        for k in fields
        if k not in {"reviewer", "origin", "goal_drift", "critical_failures"}
    }
    value.update(
        reviewer="Synthetic reviewer",
        origin="synthetic_fixture",
        goal_drift=False,
        direct_usefulness=3,
        final_faithfulness=3,
        critical_failures=[],
        false_closures=1,
    )
    with pytest.raises(ValidationError):
        ScopedQualityLabels.model_validate(value)


def test_dependency_cannot_refresh_itself_when_a_new_premise_regains_support(
    client, app
):
    s = completed(client, app)["review"]
    premise, child = s["claims"][:2]
    child["dependencies"] = [premise["claim_id"]]
    child["dependency_versions"] = {premise["claim_id"]: premise["revision"] - 1}
    s["evidence"] = [
        {
            "id": "scoped-premise-evidence",
            "claim_id": premise["claim_id"],
            "claim_revision": premise["revision"],
            "integrity": "pass",
            "origin": "director_supplied_source",
            "assessment_actor": "human_director",
            "assessment_reason": "An explicit assessment of this revised premise within scope",
            "relation": "supports",
            "supported_scope": premise["scope"],
            "scope_coverage": "whole_claim_as_assessed",
        }
    ]
    decisions = publication_decisions(s)
    assert decisions[0]["permission"] == "supported"
    assert any("Dependency revision changed" in x for x in decisions[1]["blockers"])


def test_eight_claim_profile_keeps_all_authors_and_complete_structured_outputs(
    client, app, monkeypatch
):
    from test_council_chat import drain
    from test_review_resilience import scripted_transport
    from test_workflow import post

    r, seen = scripted_transport(app, monkeypatch)
    review = r.chat.review
    demo = review.demo
    sizes = {}

    def dense(c, chat, messages, turn):
        raw = demo(c, chat, messages, turn)
        if turn["phase"] == "extraction":
            x = json.loads(raw)
            for i, claim in enumerate(list(x["claims"])):
                extra = deepcopy(claim)
                extra["ref"] = f"C{i + 5}"
                extra["assertion"] = (
                    "A separate synthetic assertion preserves its own source and necessary conditions."
                )
                x["claims"].append(extra)
            raw = json.dumps(x, separators=(",", ":"))
        if turn["phase"] != "opening":
            sizes[turn["phase"]] = max(sizes.get(turn["phase"], 0), len(raw.encode()))
        return raw

    monkeypatch.setattr(review, "demo", dense)
    v = post(
        client,
        "/chats",
        {
            "prompt": "Compare scoped options; this is a maximum-density protocol fixture.",
            "provider": "direct_council",
            "models": list(r.direct_provider.entries()),
            "mode": "reviewed",
            "review_protocol": "reviewed_v2",
            "max_rounds": 1,
        },
    )
    drain(app)
    v = client.get("/api/chats/" + v["chat"]["id"]).json()
    assert v["chat"]["status"] == "completed", v["chat"].get("error")
    assert len(v["review"]["claims"]) == 8 and len(v["review"]["rechecks"]) == 8
    assert len(v["review"]["repairs"]) == 8
    assert v["budget"]["attempts"] == 12
    assert all(len(json.dumps(p).encode()) < 90000 for p in seen)
    assert all(
        size < 16000 for size in sizes.values()
    )  # byte envelope, not a claim of exact tokenizer equivalence
    assert all(p["output_token_limit"] == 4096 for p in seen)
    for p in seen:
        if p["phase"] == "scrutiny":
            assert "source_units" not in p
            assert all("source_spans" not in claim for claim in p["claims"])
            assert len(p["openings"]) == 4
