import pytest
from test_budget import configured

from zerowall.db import DomainError
from zerowall.resource_policy import DEFAULTS, limits
from zerowall.token_factory_generation import MAX_CONTEXT_TOKENS


def test_glm_token_factory_budget_covers_all_stages_without_changing_other_models(app):
    council = app.state.research.chat
    chat = {
        "provider": "nebius_token_factory",
        "mode": "reviewed",
        "protocol": {"version": "reviewed_v3"},
    }
    for phase in ("extraction", "scrutiny", "repair", "recheck", "synthesis"):
        turn = {"phase": phase, "participant": {"model": "zai-org/GLM-5.3-Flash"}}
        assert council.output_limit(chat, turn) == 32768
        turn["participant"]["model"] = "nvidia/Nemotron-3.5-Super-VL"
        assert council.output_limit(chat, turn) == 32768

    turn = {"phase": "opening", "participant": {"model": "zai-org/GLM-5.3-Flash"}}
    chat["mode"], chat["protocol"]["version"] = "discussion", "discussion_v1"
    assert council.output_limit(chat, turn) == 262144
    chat["provider"] = "direct_council"
    assert council.output_limit(chat, turn) == 3072


def test_token_factory_output_pool_admits_twenty_larger_reservations_only(app):
    r, mid, _ = configured(app, 1)
    chat = {
        "id": "output-limit-chat",
        "mission_id": mid,
        "provider": "nebius_token_factory",
    }
    with r.store.tx() as c:
        for attempt in range(20):
            reservation = r.tools.policy.reserve(
                c, chat, "output_tokens", MAX_CONTEXT_TOKENS, f"call-{attempt}"
            )
            r.tools.policy.update(c, reservation, "consumed")
            r.tools.policy.reserve(c, chat, "input_tokens", MAX_CONTEXT_TOKENS, f"call-{attempt}")
        with pytest.raises(DomainError, match="output tokens limit"):
            r.tools.policy.reserve(c, chat, "output_tokens", 1, "extra")
        with pytest.raises(DomainError, match="input tokens limit"):
            r.tools.policy.reserve(c, chat, "input_tokens", 1, "extra")
        assert r.budget.summary(c)["absolute_cap_usd"] == 24
    assert limits(chat)["output_tokens"] == 20 * MAX_CONTEXT_TOKENS
    chat["provider"] = "direct_council"
    assert limits(chat) == DEFAULTS
    assert DEFAULTS["output_tokens"] == 163840
