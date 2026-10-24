"""Versioned, lossless token projections. Unknown values never become zero."""

import math

from .db import digest

VERSION = "usage/1"


def normalize(provider, raw):
    raw = raw if isinstance(raw, dict) else {}
    errors, fields, states = [], {}, {}

    def count(name, value, state="not_reported"):
        if value is not None and (type(value) is not int or value < 0):
            errors.append(name + ": invalid nonnegative integer")
            value, state = None, "invalid"
        fields[name], states[name] = value, "known" if value is not None else state
        return value

    if provider == "gemini":
        inp = count("input_total_reported", raw.get("promptTokenCount"))
        cached = count("cache_read_input", raw.get("cachedContentTokenCount"))
        visible = count("output_visible", raw.get("candidatesTokenCount"))
        reasoning = count("output_reasoning", raw.get("thoughtsTokenCount"))
        output = (
            visible + reasoning
            if visible is not None and reasoning is not None
            else None
        )
        count("output_total_reported", None)
        count("billable_output", output)
        count("provider_total_reported", raw.get("totalTokenCount"))
        rule = "Gemini candidate and thought counts are disjoint; billing output is their sum."
    else:
        inp = count(
            "input_total_reported", raw.get("prompt_tokens", raw.get("input_tokens"))
        )
        details = raw.get("prompt_tokens_details") or {}
        if not isinstance(details, dict):
            errors.append("Invalid prompt token details")
            details = {}
        cached = count(
            "cache_read_input",
            details.get("cached_tokens", raw.get("prompt_cache_hit_tokens")),
        )
        output = count(
            "output_total_reported",
            raw.get("completion_tokens", raw.get("output_tokens")),
        )
        out_details = raw.get("completion_tokens_details") or {}
        if not isinstance(out_details, dict):
            errors.append("Invalid completion token details")
            out_details = {}
        reasoning = count("output_reasoning", out_details.get("reasoning_tokens"))
        count("billable_output", output)
        count(
            "output_visible",
            output - reasoning
            if output is not None and reasoning is not None and reasoning <= output
            else None,
        )
        count("provider_total_reported", raw.get("total_tokens"))
        if output is not None and reasoning is not None and reasoning > output:
            errors.append("reasoning exceeds inclusive completion count")
        rule = (
            "Cached prompt is a subset of input; reasoning is a subset of completion."
        )
    if cached is not None and inp is not None and cached > inp:
        errors.append("cache read exceeds inclusive prompt count")
    count(
        "input_uncached",
        inp - cached
        if inp is not None and cached is not None and cached <= inp
        else None,
    )
    # These endpoints do not have a separately billed, measured cache-write category.
    count(
        "cache_write_input",
        None,
        "not_applicable" if provider in ("groq", "zai", "gemini") else "not_reported",
    )
    count("cache_write_long_retention", None, states["cache_write_input"])

    def safe(value):
        if isinstance(value, dict):
            return {k: safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [safe(v) for v in value]
        return (
            {"invalid_numeric": repr(value)}
            if isinstance(value, float) and not math.isfinite(value)
            else value
        )

    raw = safe(raw)
    return {
        "version": VERSION,
        "provider": provider,
        "categories": fields,
        "states": states,
        "status": "invalid"
        if errors
        else "not_reported"
        if not any(v is not None for v in fields.values())
        else "reported",
        "errors": errors,
        "inclusion_rules": rule,
        "raw_field_map": raw,
        "raw_hash": digest(raw),
    }
