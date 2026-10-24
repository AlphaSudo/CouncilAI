"""Offline current-versus-scoped evaluation; no provider calls or invented labels."""

from statistics import median
from typing import Literal

from pydantic import Field, model_validator

from .contracts import Contract
from .quality_v2 import ScopedQualityLabels


class CouncilQualityRun(Contract):
    protocol: Literal["reviewed_v2", "reviewed_v3"]
    policy_version: str
    prompt_version: str
    selected_models: list[str] = Field(min_length=2, max_length=4)
    chat_id: str = Field(min_length=1, max_length=80)
    status: Literal["completed", "partial", "failed"]
    planned_calls: int = Field(ge=8, le=16)
    focused_exchange_calls: int = Field(default=0, ge=0, le=3)
    actual_calls: int = Field(ge=0, le=20)
    tokens: int | None = Field(default=None, ge=0)
    latency_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    labels: ScopedQualityLabels | None = None


class CouncilQualityPair(Contract):
    task_id: str
    question_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    blinded_labels_declared: bool = False
    baseline: CouncilQualityRun
    council: CouncilQualityRun

    @model_validator(mode="after")
    def comparable(self):
        if (
            self.baseline.protocol != "reviewed_v2"
            or self.council.protocol != "reviewed_v3"
        ):
            raise ValueError(
                "The study requires a scoped baseline and the current Council"
            )
        if self.baseline.selected_models != self.council.selected_models or len(
            set(self.baseline.selected_models)
        ) != len(self.baseline.selected_models):
            raise ValueError("Paired runs require the same distinct exact models")
        base = 2 * len(self.baseline.selected_models) + 4
        if (
            self.baseline.focused_exchange_calls
            or self.baseline.planned_calls != base
            or self.council.planned_calls != base + self.council.focused_exchange_calls
        ):
            raise ValueError("Disclose the actual base and focused-exchange schedules")
        if (
            self.baseline.policy_version != "generic-publication-v2"
            or self.council.policy_version != "generic-publication-v3"
        ):
            raise ValueError(
                "The declared policies do not match the evaluated protocols"
            )
        return self


class CouncilQualityStudy(Contract):
    protocol_version: Literal["generic-quality-pilot-v3"]
    dataset_frozen_before_labels: bool
    task_set_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    treatment: Literal["base_schedule", "focused_exchange"] = "base_schedule"
    qualification_notes: str = Field(min_length=10, max_length=4000)
    frozen_models: list[str] = Field(min_length=2, max_length=4)
    baseline_prompt_version: str = Field(min_length=3, max_length=100)
    council_prompt_version: str = Field(min_length=3, max_length=100)
    pairs: list[CouncilQualityPair] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def treatment_schedule(self):
        if len(set(self.frozen_models)) != len(self.frozen_models):
            raise ValueError("Freeze distinct exact model identities")
        if any(
            pair.baseline.selected_models != self.frozen_models
            or pair.council.selected_models != self.frozen_models
            or pair.baseline.prompt_version != self.baseline_prompt_version
            or pair.council.prompt_version != self.council_prompt_version
            for pair in self.pairs
        ):
            raise ValueError("Run models/prompts drifted from the frozen study")
        if self.treatment == "base_schedule" and any(
            p.council.focused_exchange_calls for p in self.pairs
        ):
            raise ValueError(
                "Extra exchanges are a separate treatment, not a matched-call base comparison"
            )
        return self


def summarize_council_quality(value):
    study = CouncilQualityStudy.model_validate(value)
    result = {
        "protocol_version": study.protocol_version,
        "quality_status": "independent_quality_pending",
        "pairs": len(study.pairs),
        "task_set_hash": study.task_set_hash,
        "treatment": study.treatment,
        "general_superiority": "not_established",
        "statistical_significance": "not_assessed",
        "qualification_notes": study.qualification_notes,
        "arms": {},
        "paired_usefulness": [],
    }
    human = 0
    for arm in ("baseline", "council"):
        runs = [getattr(pair, arm) for pair in study.pairs]
        labels = [
            run.labels
            for run in runs
            if run.labels and run.labels.origin == "human_reported"
        ]
        human += len(labels)

        def rate(numerator, denominator, labels=labels):
            n, d = (
                sum(getattr(x, numerator) for x in labels),
                sum(getattr(x, denominator) for x in labels),
            )
            return {"numerator": n, "denominator": d, "rate": n / d if d else None}

        defects = rate("missed_defects", "material_defects")
        result["arms"][arm] = {
            "runs": len(runs),
            "completed": sum(r.status == "completed" for r in runs),
            "partial": sum(r.status == "partial" for r in runs),
            "failed": sum(r.status == "failed" for r in runs),
            "unlabeled_runs": sum(r.labels is None for r in runs),
            "human_labelled_runs": len(labels),
            "synthetic_labelled_runs": sum(
                bool(r.labels and r.labels.origin == "synthetic_fixture") for r in runs
            ),
            "actual_calls": sum(r.actual_calls for r in runs),
            "unknown_cost_runs": sum(r.cost_usd is None for r in runs),
            "unsupported_as_established": rate(
                "unsupported_as_established", "material_claims"
            ),
            "false_rejection": rate("unnecessary_rejections", "valid_scoped_proposals"),
            "coverage": rate("covered_material_claims", "source_material_claims"),
            "source_fidelity": rate("faithful_extractions", "extracted_claims"),
            "false_closure": rate("false_closures", "closed_objections"),
            "missed_defects": defects,
            "defect_recall": {
                "numerator": defects["denominator"] - defects["numerator"],
                "denominator": defects["denominator"],
                "rate": 1 - defects["rate"] if defects["rate"] is not None else None,
            },
            "median_usefulness": median(x.direct_usefulness for x in labels)
            if labels
            else None,
        }
    for pair in study.pairs:
        a, b = pair.baseline.labels, pair.council.labels
        if a and b and a.origin == b.origin == "human_reported":
            result["paired_usefulness"].append(
                {
                    "task_id": pair.task_id,
                    "delta": b.direct_usefulness - a.direct_usefulness,
                    "blinded_labels_declared": pair.blinded_labels_declared,
                }
            )
    result["human_label_records"] = human
    result["dataset_frozen_before_labels"] = study.dataset_frozen_before_labels
    if human:
        result["quality_status"] = "human_reports_available_for_descriptive_review"
    result["independence_authenticated"] = False
    return result
