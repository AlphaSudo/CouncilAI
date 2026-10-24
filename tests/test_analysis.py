import pytest
from zerowall.analysis import compare_trials, calculate_bound
from zerowall.benchmark import tasks, pack_sources, prompt, validate, ROOT
import json


def observations():
    return [
        {
            "task_id": f"T{i}",
            "cell": cell,
            "cost_usd": cost,
            "latency_ms": 100,
            "valid": True,
            "split": "exploration",
            "repeat": 0,
        }
        for i in range(8)
        for cell, cost in [
            ("C00", 0.01),
            ("C10", 0.009),
            ("C01", 0.008),
            ("C11", 0.006),
        ]
    ]


def test_paired_effects_interaction_and_uncertainty():
    result = compare_trials(
        {
            "observations": observations(),
            "material_saving": 0.1,
            "latency_limit_ms": 1000,
        }
    )
    assert result["integrity_gate"] == "pass"
    assert result["comparisons"]["C11"]["saving_fraction"] == pytest.approx(0.4)
    assert result["log_cost_interaction"] < 0
    assert result["comparisons"]["C11"]["bootstrap_95_cost_difference"] is not None
    assert result["comparisons"]["C11"]["cost_confirmation_gate"] == "pass"
    assert result["comparisons"]["C11"]["bootstrap_95_saving_fraction"][
        0
    ] == pytest.approx(0.4)
    assert result["pareto_candidates"] == ["C11"]


def test_new_failure_rejects_candidate_even_if_cheaper():
    rows = observations()
    rows[3]["valid"] = False
    result = compare_trials(
        {"observations": rows, "material_saving": 0.1, "latency_limit_ms": 1000}
    )
    assert result["comparisons"]["C11"]["quality_gate"] == "fail"
    assert result["comparisons"]["C11"]["new_required_failures"] == ["T0"]


def test_no_valid_result_is_undefined_and_incomplete_is_invalid():
    rows = [{**r, "valid": False} for r in observations()][:-1]
    result = compare_trials(
        {"observations": rows, "material_saving": 0.1, "latency_limit_ms": 1000}
    )
    assert result["cells"]["C11"]["cost_per_valid_task"] is None
    assert result["integrity_gate"] == "invalid"
    assert result["log_cost_interaction"] is None


def test_duplicate_observations_rejected():
    with pytest.raises(ValueError):
        compare_trials(
            {
                "observations": observations() + observations(),
                "material_saving": 0.1,
                "latency_limit_ms": 1000,
            }
        )


def test_packing_preserves_source_facts_and_hides_answers():
    keys = json.loads((ROOT / "benchmark/evaluators/hidden.json").read_text())
    for split in ("exploration", "confirmation"):
        for t in tasks(split):
            packed = pack_sources(t["sources"])
            assert {s["id"] for s in packed} == {s["id"] for s in t["sources"]}
            assert set(packed[0]["facts"]) == set(t["sources"][0]["facts"])
            assert len(prompt(t, True)) < len(prompt(t, False))
            assert "finding_terms" not in prompt(t, True) and "tolerance" not in prompt(
                t, True
            )
            k = keys[t["id"]]
            answer = {
                "answer": k["answer"],
                "unit": k["unit"],
                "source_ids": k["required_sources"],
                "finding": " ".join(k["finding_terms"]),
                "next_test": "Run an independently controlled next experiment.",
                "hardware_measured": False,
            }
            assert validate(t, answer, k)["valid"]


def test_decimal_units_bound():
    assert (
        calculate_bound(
            {"bytes_moved": 2e9, "bandwidth_gbps": 100, "assumptions": ["hypothetical"]}
        )["minimum_seconds"]
        == 0.02
    )
