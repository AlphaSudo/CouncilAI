"""Read model review JSON through harmless prose, fences and repeated payloads."""

import json

from .db import digest


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate structured field names are ambiguous")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("Non-finite numbers are not valid review data")


def _without_trailing_commas(text):
    result, quoted, escaped, removed = [], False, False, 0
    for index, char in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == ',':
            following = index + 1
            while following < len(text) and text[following].isspace():
                following += 1
            if following < len(text) and text[following] in '}]':
                removed += 1
                continue
        result.append(char)
    return ''.join(result), removed


def parse_review_json(content):
    """Accept one unambiguous object; retain all cosmetic adjustments in audit data."""
    objects, spans, changes = [], [], []
    start, depth, quoted, escaped = None, 0, False, False
    for index, char in enumerate(content):
        if start is None:
            if char == '{':
                start, depth, quoted, escaped = index, 1, False, False
            continue
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth:
                continue
            raw = content[start:index + 1]
            prepared, removed = _without_trailing_commas(raw)
            try:
                value = json.loads(prepared, object_pairs_hook=_unique_fields,
                                   parse_constant=_invalid_constant)
            except json.JSONDecodeError:
                # Braces in ordinary prose are not another structured reply.
                if raw[1:].lstrip().startswith('"'):
                    raise
            else:
                objects.append(value)
                spans.append((start, index + 1))
                if removed:
                    changes.append({"kind": "trailing_json_commas", "path": [],
                                    "before": removed, "after": 0,
                                    "reason": "Removed trailing commas outside quoted strings"})
                if len(objects) > 16:
                    raise ValueError("Too many repeated structured reply objects")
            start = None
    if start is not None:
        raise ValueError("The structured reply has an incomplete JSON object")
    if not objects:
        raise ValueError("No complete structured reply object was found")
    hashes = {digest(value) for value in objects}
    if len(hashes) != 1:
        raise ValueError("Multiple different structured replies were returned; no version was chosen automatically")
    if len(objects) > 1:
        changes.append({"kind": "identical_repeated_payload", "path": [],
                        "before": len(objects), "after": 1,
                        "reason": "Identical repeated objects were admitted once; raw copies remain saved"})
    gaps, previous = [], 0
    for left, right in spans:
        if content[previous:left].strip('\ufeff \r\n\t'):
            gaps.append(content[previous:left])
        previous = right
    if content[previous:].strip('\ufeff \r\n\t'):
        gaps.append(content[previous:])
    if gaps:
        changes.append({"kind": "supplementary_response_text", "path": [],
                        "before": gaps, "after": None,
                        "reason": "Surrounding response text is saved as unverified commentary, outside structured decisions"})
    return objects[0], changes
