from copy import deepcopy
import pytest
from pydantic import ValidationError
from zerowall.quality import summarize_quality


def study():
    return {
        "protocol_version": "generic-quality-pilot-v1",
        "dataset_frozen_before_labels": True,
        "qualification_notes": "Synthetic evaluation labels used only to test arithmetic and missing-data handling.",
        "pairs": [],
    }


def test_missing_quality_data_stays_pending_and_unknown_not_zero():
    result = summarize_quality(study())
    assert result["label_status"] == "independent_quality_pending"
    assert result["modes"]["reviewed"]["unsupported_as_established"]["rate"] is None
    assert result["modes"]["reviewed"]["reported_cost_total_usd"] is None
    assert result["general_superiority"] == "not_established"


def labeled_pair():
    labels = {
        "reviewer": "Synthetic test reviewer",
        "origin": "synthetic_fixture",
        "material_claims": 5,
        "unsupported_as_established": 2,
        "cited_claims": 3,
        "relevant_citations": 2,
        "objections": 2,
        "invalid_objections": 1,
        "useful_repairs": 1,
        "goal_drift": False,
        "direct_usefulness": 3,
    }
    return {
        "task_id": "test-task",
        "question_hash": "a" * 64,
        "evidence_hash": "b" * 64,
        "selected_models": ["model-a", "model-b"],
        "discussion": {
            "mode": "discussion",
            "chat_id": "baseline",
            "status": "failed",
            "actual_calls": 4,
            "labels": deepcopy(labels),
        },
        "reviewed": {
            "mode": "reviewed",
            "chat_id": "review",
            "status": "partial",
            "actual_calls": 8,
            "labels": deepcopy(labels),
        },
    }


def test_quality_summary_retains_denominators_failed_runs_and_synthetic_origin():
    value = study()
    value["pairs"] = [labeled_pair()]
    result = summarize_quality(value)
    assert result["label_status"] == "synthetic_only"
    assert result["modes"]["discussion"]["failed"] == 1
    assert result["modes"]["reviewed"]["partial"] == 1
    assert result["modes"]["reviewed"]["unsupported_as_established"] == {
        "numerator": 2,
        "denominator": 5,
        "rate": 0.4,
    }
    assert result["modes"]["reviewed"]["unknown_cost_runs"] == 1


def test_impossible_label_counts_are_rejected():
    value = study()
    pair = labeled_pair()
    pair["reviewed"]["labels"]["unsupported_as_established"] = 9
    value["pairs"] = [pair]
    with pytest.raises(ValidationError):
        summarize_quality(value)


def test_wrong_mode_pair_is_rejected_and_human_authorship_is_not_certified():
    value = study()
    pair = labeled_pair()
    pair["reviewed"]["labels"]["origin"] = "human_reported"
    value["pairs"] = [pair]
    assert "not_independently_authenticated" in summarize_quality(value)["label_status"]
    pair["reviewed"]["mode"] = "discussion"
    with pytest.raises(ValidationError):
        summarize_quality(value)
