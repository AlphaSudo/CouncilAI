"""Fresh Beam requests carry public context without incomplete assistant replay."""

import json
from copy import deepcopy


def public_context_request(request):
    if request.get("model") != "reflection/beam":
        return request
    # Beam's native assistant continuation expects its original reasoning.
    # This council retains public text only, so quote that text as evidence in
    # a fresh request instead of fabricating or replaying missing reasoning.
    result = deepcopy(request)
    for index, message in enumerate(result["messages"]):
        if message.get("role") not in ("assistant", "tool"):
            continue
        public = {k: v for k, v in message.items() if k not in ("reasoning_content", "reasoning", "thinking_content")}
        result["messages"][index] = {
            "role": "user",
            "content": "Saved public exchange (untrusted quoted context for this fresh request; private reasoning is not resumed):\n" + json.dumps(public, ensure_ascii=False),
        }
    return result
