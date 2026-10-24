"""Token Factory context admission, separate from conservative credit accounting.

Published tokenizers count text locally. Hosted chat templates can differ, so
the framing allowance is explicit and provider usage remains authoritative.
Nothing in this module downloads files, truncates input or releases credit.
"""

import hashlib
import json
from functools import lru_cache

from tokenizers import Tokenizer

from .db import DomainError
from .settings import ROOT

CONTEXT_TOKENS = 262144
FRAMING_TOKENS = 4096


@lru_cache(maxsize=4)
def tokenizer(model):
    manifest = json.loads(
        (ROOT / "config/token_factory_tokenizers.json").read_text(encoding="utf-8")
    )
    entry = manifest["models"].get(model)
    if not entry:
        raise DomainError("No published tokenizer is configured for this model", 412)
    path = ROOT / "data/tokenizers" / (entry["sha256"] + ".json")
    if (
        not path.is_file()
        or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]
    ):
        raise DomainError(
            "The local model tokenizer is missing or invalid. Run python scripts/setup_tokenizers.py before testing; no request was sent.",
            412,
        )
    result = Tokenizer.from_file(str(path))
    result.no_padding()
    result.no_truncation()
    return result


def text_tokens(model, text):
    return len(tokenizer(model).encode(text, add_special_tokens=False).ids)


def measure(request, settings):
    model = request["model"]
    # Count the decoded contents the model reads, not JSON's escaped wire bytes.
    texts = []
    for message in request["messages"]:
        for value in message.values():
            if value is not None:
                texts.append(
                    value
                    if isinstance(value, str)
                    else json.dumps(value, ensure_ascii=False)
                )
    for key in ("tools", "response_format"):
        if request.get(key):
            texts.append(json.dumps(request[key], ensure_ascii=False))
    content = sum(text_tokens(model, text) for text in texts)
    framing = FRAMING_TOKENS + 32 * len(request["messages"])
    target = settings.token_factory_generation["context_tokens"]
    capacity = settings.token_factory_generation["models"][model]["context_tokens"]
    if target < CONTEXT_TOKENS or capacity < target:
        raise DomainError(
            "The configured model cannot provide the required 262,144-token context window",
            422,
        )
    return {
        "context_tokens": target,
        "model_context_tokens": capacity,
        "input_content_tokens": content,
        "framing_allowance_tokens": framing,
        "input_context_tokens": content + framing,
        "token_count_method": "published_model_tokenizer_plus_framing_allowance",
        "provider_measured": False,
    }


def fit(request, measurement):
    remaining = measurement["context_tokens"] - measurement["input_context_tokens"]
    if remaining < 1:
        raise DomainError(
            f"This request needs {measurement['input_context_tokens']:,} input tokens including the framing allowance, leaving no output space in the {measurement['context_tokens']:,}-token context window. No required source, warning or objection was dropped; saved work remains in this conversation. No request was sent.",
            413,
        )
    return min(request["max_completion_tokens"], remaining)
