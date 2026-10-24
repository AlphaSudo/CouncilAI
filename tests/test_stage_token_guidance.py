"""Stage guidance must save tokens without replacing coverage or context limits."""

import pytest

from zerowall.token_factory_generation import configure, profile


@pytest.mark.parametrize("phase", ["extraction", "scrutiny"])
def test_stage_guidance_is_a_complete_output_target_not_a_lower_context_cap(app, phase):
    research = app.state.research
    model = research.settings.models[1]
    generation = profile(
        research.settings, {"phase": phase, "participant": {"model": model}}
    )
    request = research.provider.request(
        "Keep every mandatory claim and objection.", 32768, model
    )
    configure(request, generation)
    configure(request, generation)
    system = request["messages"][0]["content"]
    assert system.count(generation["stage_token_instruction"]) == 1
    assert "Aim for 3,000 public-output tokens" in system
    assert (
        "exceed it when needed" in system and "Never omit mandatory coverage" in system
    )
    assert (
        generation["context_tokens"] == 262144
        and request["max_completion_tokens"] == 32768
    )
    assert generation["reasoning_budget_tokens"] == 4000
    assert (
        request["messages"][1]["content"] == "Keep every mandatory claim and objection."
    )


def test_independent_openings_keep_their_existing_open_length_policy(app):
    research = app.state.research
    model = research.settings.models[0]
    generation = profile(
        research.settings, {"phase": "opening", "participant": {"model": model}}
    )
    request = research.provider.request(
        "An independent opening question.", 262144, model
    )
    configure(request, generation)
    assert generation["stage_output_target_tokens"] is None
    assert generation["stage_token_instruction"] is None
    assert request["max_completion_tokens"] == 262144
    assert "public-output tokens" not in request["messages"][0]["content"]
