"""User-selected reasoning presets mapped to each model's documented controls."""

from copy import deepcopy

from .db import DomainError

LEVELS = {
    "quick": {"label": "Quick", "reasoning_tokens": 2000},
    "balanced": {"label": "Balanced", "reasoning_tokens": 4000},
    "deep": {"label": "Deep", "reasoning_tokens": 8000},
    "maximum": {"label": "Maximum", "reasoning_tokens": 16000},
}


def controls_for(model, level, defaults):
    if level not in LEVELS:
        raise DomainError("Choose a supported thinking level", 422)
    if level == "balanced":
        return deepcopy(defaults), None
    if model == "reflection/beam":
        effort = {"quick": "low", "deep": "medium", "maximum": "high"}[level]
        return {**deepcopy(defaults), "reasoning_effort": effort}, effort
    if model.startswith(("zai-org/", "deepseek-ai/")):
        effort = {"quick": "low", "deep": "high", "maximum": "max"}[level]
        template = {"reasoning_effort": effort}
        if model.startswith("zai-org/"):
            template["clear_thinking"] = True
        return {"reasoning_effort": effort, "chat_template_kwargs": template}, effort
    if model == "nvidia/Nemotron-3.5-Super-VL":
        template = {"enable_thinking": True}
        if level == "quick":
            template["medium_effort"] = True
        return {
            "chat_template_kwargs": template
        }, "medium" if level == "quick" else "enabled"
    if model == "nvidia/Nemotron-3_5-Lightning":
        return {"chat_template_kwargs": {"enable_thinking": True}}, "enabled"
    raise DomainError("No verified thinking-level mapping exists for this model", 422)


def catalogue():
    return [{"id": key, **value} for key, value in LEVELS.items()]


def projection(settings, models, level="balanced"):
    from .token_factory_generation import profile

    return {
        "supported": True,
        "level": level,
        "levels": catalogue(),
        "reasoning_budget_tokens": LEVELS[level]["reasoning_tokens"],
        "enforcement": "system_instruction_only",
        "applies_to": "requests_not_started_yet",
        "models": [
            {
                "model": model,
                "reasoning": value["reasoning"],
                "controls": value["controls"],
                "reasoning_budget_tokens": value["reasoning_budget_tokens"],
                "native_reasoning_budget_tokens": value["native_reasoning_budget_tokens"],
                "model_reasoning_override": value["model_reasoning_override"],
                "native_effort_available": model != "nvidia/Nemotron-3_5-Lightning",
            }
            for model in models
            for value in [
                profile(
                    settings,
                    {"phase": "opening", "participant": {"model": model}},
                    thinking_level=level,
                )
            ]
        ],
    }
