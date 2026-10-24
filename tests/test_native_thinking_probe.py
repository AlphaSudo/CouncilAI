"""Diagnostic evidence must never mistake parameter acceptance for enforcement."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "thinking_probe", Path(__file__).resolve().parents[1] / "scripts/probe_glm_thinking_budget.py"
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.mark.parametrize(
    "reasoning,answer,finish,expected",
    [
        (400, "A public answer", "stop", "budget_not_enforced"),
        (64, "A public answer", "stop", "boundary_observed_with_complete_answer"),
        (20, "A public answer", "stop", "within_budget_but_enforcement_unproven"),
        (64, "", "stop", "no_complete_public_answer"),
        (64, "A partial answer", "length", "no_complete_public_answer"),
        (None, "A public answer", "stop", "usage_inconclusive"),
    ],
)
def test_native_budget_verdict_requires_usage_boundary_and_complete_answer(
    reasoning, answer, finish, expected
):
    call = {
        "http_status": 200,
        "finish_reason": finish,
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": (reasoning or 0) + 30,
            "completion_tokens_details": {"reasoning_tokens": reasoning},
        },
    }
    assert probe.evaluate(call, answer, 64) == expected
