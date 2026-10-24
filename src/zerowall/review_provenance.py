"""Fallible source cues, never experimental results or evidence authority."""

import re

from .db import digest

CUES = re.compile(
    r"\b(?:observed results?|personal testing|I (?:tested|measured|ran)|we (?:tested|measured|ran)|our (?:tests?|experiment)|(?:copy|snapshot|restore|test|run) took)\b",
    re.IGNORECASE,
)


def observation_cues(message):
    content = message["content"]
    found = []
    in_observations = False
    for line in re.finditer(r"[^\n]+", content):
        value = line.group()
        cue = bool(CUES.search(value))
        if value.lstrip().startswith("#"):
            in_observations = cue
        if not (cue or (in_observations and re.search(r"\d", value))):
            continue
        contextual = bool(
            re.search(
                r"^\s*>|\b(?:if|hypothetical|example|quoted|according to)\b",
                value,
                re.IGNORECASE,
            )
        )
        found.append(
            {
                "id": "cue_" + digest([message["id"], line.start(), line.end()])[:16],
                "source_message_id": message["id"],
                "source_span": {
                    "start": line.start(),
                    "end": line.end(),
                    "hash": digest(value),
                },
                "text": value,
                "classification": "context_requires_assessment"
                if contextual
                else "unsupported_self_report",
                "origin": "local_cue_scan",
                "status": "unverified_report",
                "reason": "Possible claimed observation; no execution or external verification is established by this passage.",
            }
        )
    return found
