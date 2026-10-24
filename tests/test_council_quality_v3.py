import json
from copy import deepcopy
from pathlib import Path

import pytest

from zerowall.db import digest
from zerowall.quality import summarize_quality
from zerowall.quality_v3 import CouncilQualityStudy

ROOT = Path(__file__).resolve().parents[1]


def template():
    return json.loads(
        (ROOT / "benchmark/council_103_quality_template.json").read_text()
    )


def run(protocol):
    return {
        "protocol": protocol,
        "policy_version": "generic-publication-v" + protocol[-1],
        "prompt_version": "frozen-test-version",
        "selected_models": ["model/a", "model/b"],
        "chat_id": "fixture-" + protocol,
        "status": "failed",
        "planned_calls": 8,
        "actual_calls": 3,
    }


def test_new_quality_template_has_no_invented_human_score():
    result = summarize_quality(template())
    assert result["quality_status"] == "independent_quality_pending"
    assert result["human_label_records"] == 0
    assert result["arms"]["council"]["defect_recall"]["rate"] is None


def test_failed_unlabelled_runs_and_unknown_cost_remain_visible():
    value = template()
    value.update(
        frozen_models=["model/a", "model/b"],
        baseline_prompt_version="frozen-test-version",
        council_prompt_version="frozen-test-version",
    )
    value["pairs"] = [
        {
            "task_id": "sample",
            "question_hash": "a" * 64,
            "evidence_hash": "b" * 64,
            "baseline": run("reviewed_v2"),
            "council": run("reviewed_v3"),
        }
    ]
    result = summarize_quality(value)
    assert result["arms"]["council"]["failed"] == 1
    assert result["arms"]["council"]["unlabeled_runs"] == 1
    assert result["arms"]["council"]["unknown_cost_runs"] == 1
    unequal = deepcopy(value)
    unequal["pairs"][0]["council"]["selected_models"] = ["model/a", "model/c"]
    with pytest.raises(ValueError):
        CouncilQualityStudy.model_validate(unequal)
    extra = deepcopy(value)
    extra["pairs"][0]["council"].update(focused_exchange_calls=2, planned_calls=10)
    with pytest.raises(ValueError, match="separate treatment"):
        CouncilQualityStudy.model_validate(extra)


def test_heldout_tasks_remain_frozen_and_distinct_from_the_smoke():
    manifest = json.loads(
        (ROOT / "benchmark/council_103_heldout_tasks.json").read_text()
    )
    assert (
        manifest["task_set_hash"]
        == digest(manifest["tasks"])
        == template()["task_set_hash"]
    )
    assert len(manifest["tasks"]) == 4
    for task in manifest["tasks"]:
        assert task["question_hash"] == digest(task["question"])
        assert task["evidence_hash"] == digest(task["evidence"])
    assert not manifest["independent_labels"]
