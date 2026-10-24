"""Lossless presentation of public model output, separate from review authority."""

import json
import re

from .db import DomainError, digest


def readable_reply(content, phase):
    """Keep Markdown intact and render every supplied structured field."""
    stripped = content.lstrip()
    if not stripped.startswith(("{", "[", "```json", "```\n")):
        return content
    candidate = stripped
    if candidate.startswith("```"):
        fence = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```\s*", candidate, re.DOTALL)
        if not fence:
            return content
        candidate = fence.group(1)

    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Ambiguous duplicate field")
            result[key] = value
        return result

    try:
        value = json.loads(candidate, object_pairs_hook=unique_fields)
    except (ValueError, TypeError, RecursionError):
        return content  # An unparseable public reply is still a saved reply.

    def render(node, depth=0):
        if isinstance(node, dict):
            return (
                "\n\n".join(
                    f"{'#' * min(depth + 3, 6)} {str(key).replace('_', ' ').capitalize()}\n\n"
                    + render(item, depth + 1)
                    for key, item in node.items()
                )
                or "{}"
            )
        if isinstance(node, list):
            if not node:
                return "[]"
            if all(not isinstance(item, (dict, list)) for item in node):
                return "\n".join("- " + render(item, depth + 1) for item in node)
            return "\n\n---\n\n".join(render(item, depth + 1) for item in node)
        return node if isinstance(node, str) else json.dumps(node, ensure_ascii=False)

    try:
        return (
            "Model-supplied review notes. Assessment labels below are the model's judgments.\n\n"
            + render(value)
        )
    except RecursionError:
        return content


def original_reply(council, c, cid, mid):
    """Read public text only; never expose a request, credential or reasoning stream."""
    chat = council.store.get(c, cid, "chat")
    message = council.store.get(c, mid, "chat_message")
    if message.get("chat_id") != cid or message.get("role") != "assistant":
        raise DomainError("This response does not belong to this conversation", 404)
    row = c.execute(
        "SELECT body FROM records WHERE kind='answer_delivery' AND mission_id=? "
        "AND json_extract(body,'$.message_id')=?",
        (chat["mission_id"], mid),
    ).fetchone()
    if row:
        delivery = json.loads(row[0])
        raw = delivery["raw_public_content"]
        if digest(raw) != delivery["raw_public_hash"]:
            raise DomainError("Saved public response integrity check failed", 422)
        origin = "saved_public_delivery"
    elif message.get("call_id"):
        call = council.store.get(c, message["call_id"], "call")
        if call["mission_id"] != chat["mission_id"] or not call.get("artifact_id"):
            raise DomainError("No saved original response is available", 404)
        artifact = council.store.get(c, call["artifact_id"], "artifact")
        receipt = council.research.artifacts.read(artifact)
        choices = receipt.get("response", {}).get("choices") or []
        raw = (choices[0].get("message") or {}).get("content") if choices else None
        if not isinstance(raw, str):
            raise DomainError("No saved public response is available", 404)
        origin = "saved_provider_receipt"
    else:
        raise DomainError("No saved original response is available", 404)
    raw = council.research.artifacts.redact(raw)
    return {
        "message_id": mid,
        "call_id": message.get("call_id"),
        "content": raw,
        "readable": readable_reply(raw, message.get("phase")),
        "sha256": digest(raw),
        "origin": origin,
        "generation_state": message.get("generation_state", "complete"),
        "review_state": message.get("review_state", "unavailable"),
        "new_inference_calls": 0,
    }
