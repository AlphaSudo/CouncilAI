"""Client-observed request timing. Stream chunks are never token counts."""

import math


def seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        return None
    return value / 1000


def summarize(call, usage):
    elapsed = seconds(call.get("latency_ms"))
    stream = call.get("stream_progress") or {}
    interruption = call.get("interruption_reason")
    if not interruption and call.get("error") == "ReadTimeout" and stream:
        interruption = (
            "read_timeout_before_headers"
            if stream.get("headers_received_ms") is None
            else "read_timeout_during_body"
        )
    categories = usage["categories"]

    def rate(category):
        tokens = categories.get(category)
        return (
            tokens / elapsed
            if elapsed and tokens is not None and usage["status"] != "invalid"
            else None
        )

    return {
        "version": "response-timing/1",
        "elapsed_seconds": elapsed,
        "first_stream_seconds": seconds(stream.get("first_event_ms")),
        "first_answer_seconds": seconds(stream.get("first_answer_ms")),
        "output_tokens_per_second": rate("billable_output"),
        "visible_tokens_per_second": rate("output_visible"),
        "rate_basis": "reported_output_tokens_per_request_wall_time",
        "stream": stream or None,
        "interruption_reason": interruption,
        "read_idle_timeout_seconds": call.get("read_idle_timeout_seconds"),
        "notice": "Request time includes connection, provider waiting, prefill, reasoning and answer delivery. Provider queue time and engine-only TPS are not measured. Chunk counts are not token counts.",
    }
