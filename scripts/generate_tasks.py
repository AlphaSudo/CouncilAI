"""Build authored CC0 benchmark packets; answer keys never enter model prompts."""

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def main():
    keys = {}
    splits = {"exploration": [], "confirmation": []}
    for index in range(12):
        tid = f"T{index + 1:02}"
        sid = f"SRC{index + 1:02}"
        kind = index % 4
        scale = 1 + index // 4
        if kind == 0:
            answer = 0.02 * scale
            unit = "seconds"
            units = ["s", "seconds"]
            terms = ["bound"]
            facts = [
                f"A hypothetical transfer moves {2_000_000_000 * scale} bytes.",
                "Assume sustained bandwidth of 100 decimal GB/s, with 1 GB = 10^9 bytes.",
                "This is a supplied analytical scenario, not a measured hardware run.",
            ]
            question = "Calculate the bandwidth-only lower bound in seconds. Explain the scope and propose a test of a competing mechanism."
        elif kind == 1:
            answer = 120 * scale
            unit = "ms"
            units = ["ms", "milliseconds"]
            terms = ["escalation"]
            facts = [
                f"A failed fast-model request takes {40 * scale} ms.",
                f"The subsequent strong-model escalation takes {70 * scale} ms.",
                f"Queueing and local validation together take {10 * scale} ms.",
                "Complete workflow timing starts before queueing and ends after validation; calls are sequential.",
            ]
            question = "Calculate complete workflow latency in milliseconds. Identify why reporting only the final request latency is misleading and propose a control."
        elif kind == 2:
            answer = 0.012 * scale
            unit = "USD"
            units = ["usd", "dollars", "$"]
            terms = ["valid"]
            facts = [
                f"A workflow attempts 10 tasks at a total attributable cost of {0.06 * scale:.3f} USD.",
                "Five tasks pass every frozen required validator; all other tasks fail.",
                "The total already includes retries, repairs and escalation charges.",
            ]
            question = "Calculate cost per valid task in USD. Explain why cost per attempted task is a different metric and suggest a quality-preserving next test."
        else:
            answer = 20 * scale
            unit = "ms"
            units = ["ms", "milliseconds"]
            terms = ["confound"]
            facts = [
                f"Treatment A changes both source packing and model identity; its observed mean workflow latency is {80 * scale} ms.",
                f"Baseline mean workflow latency is {100 * scale} ms on the same tasks.",
                "No A-only or model-only cell has been collected. Provider hardware telemetry is unavailable.",
            ]
            question = "Calculate the observed latency difference in milliseconds. Identify the causal confound and propose the missing discriminating experiment."
        splits["exploration" if index < 4 else "confirmation"].append(
            {
                "id": tid,
                "category": ["bound", "workflow", "valid_cost", "confounder"][kind],
                "question": question,
                "sources": [
                    {
                        "id": sid,
                        "provenance": "ZeroWall authored CC0 scenario",
                        "facts": facts + [facts[0]],
                        "context": "Supplied research facts. Read the values and their measurement scope carefully.",
                    }
                ],
                "constraints": [
                    "Cite the supplied source ID.",
                    "Do not claim provider hardware was measured.",
                    "Return the requested JSON contract with a discriminating next test.",
                ],
            }
        )
        keys[tid] = {
            "answer": answer,
            "unit": unit,
            "units": units,
            "tolerance": max(1e-9, answer * 1e-6),
            "required_sources": [sid],
            "finding_terms": terms,
        }
    for split, packet in splits.items():
        path = ROOT / f"benchmark/tasks/{split}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    path = ROOT / "benchmark/evaluators/hidden.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(keys, indent=2), encoding="utf-8")
    print("Generated 4 exploration and 8 confirmation tasks. No inference dispatched.")


if __name__ == "__main__":
    main()
