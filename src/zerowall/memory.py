"""Local concept-overlap suggestions. Never suppress or approve scientific work."""

import math, re
from collections import Counter

CONCEPTS = {
    word: concept
    for concept, words in {
        "cost": "cost costs price pricing charge charges spend spending budget money",
        "latency": "latency timing time delay delays overhead queueing",
        "evidence": "evidence provenance source sources citation citations facts factual",
        "packing": "packing packed compression compress context packet packets",
        "routing": "routing route escalation escalate fast-first fast",
        "physical": "physical physics bandwidth hardware transfer memory",
        "validity": "valid validity invalid quality failure failures correctness",
    }.items()
    for word in words.split()
}
STOP = set(
    "a an the and or to of in on for is are be by with that this it can may from under not".split()
)


def vector(text):
    return Counter(
        CONCEPTS.get(w, w)
        for w in re.findall(r"[a-z][a-z-]+", text.lower())
        if w not in STOP
    )


def similarity(a, b):
    x, y = vector(a), vector(b)
    denom = math.sqrt(sum(v * v for v in x.values()) * sum(v * v for v in y.values()))
    return sum(v * y.get(k, 0) for k, v in x.items()) / denom if denom else 0


def suggestions(hypotheses):
    pairs = []
    for i, a in enumerate(hypotheses):
        for b in hypotheses[i + 1 :]:
            score = similarity(
                a["mechanism"] + " " + a["prediction"],
                b["mechanism"] + " " + b["prediction"],
            )
            if score >= 0.6:
                pairs.append(
                    {
                        "hypothesis_ids": [a["id"], b["id"]],
                        "similarity": round(score, 3),
                        "method": "local-domain-concept-cosine-v1",
                        "scope": "Approximate concept/lexical overlap. Human review is required; no automatic duplicate suppression.",
                    }
                )
    return sorted(pairs, key=lambda x: -x["similarity"])
