"""Offline v1/v2 paired scoring; missing human evidence stays missing."""

from statistics import median
from typing import Literal

from pydantic import Field, model_validator

from .contracts import Contract
from .quality import QualityLabels


class ScopedQualityLabels(QualityLabels):
    extracted_claims: int = Field(ge=0)
    faithful_extractions: int = Field(ge=0)
    source_material_claims: int = Field(ge=0)
    covered_material_claims: int = Field(ge=0)
    valid_scoped_proposals: int = Field(ge=0)
    retained_valid_proposals: int = Field(ge=0)
    unnecessary_rejections: int = Field(ge=0)
    material_defects: int = Field(ge=0)
    missed_defects: int = Field(ge=0)
    closed_objections: int = Field(ge=0)
    false_closures: int = Field(ge=0)
    reported_observations: int = Field(ge=0)
    correctly_attributed_observations: int = Field(ge=0)
    proposed_tests: int = Field(ge=0)
    justified_tests: int = Field(ge=0)
    final_faithfulness: int = Field(ge=1, le=5)
    critical_failures: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def scoped_denominators(self):
        pairs = [
            (self.faithful_extractions, self.extracted_claims),
            (self.covered_material_claims, self.source_material_claims),
            (self.retained_valid_proposals, self.valid_scoped_proposals),
            (self.unnecessary_rejections, self.valid_scoped_proposals),
            (self.missed_defects, self.material_defects),
            (self.false_closures, self.closed_objections),
            (self.correctly_attributed_observations, self.reported_observations),
            (self.justified_tests, self.proposed_tests),
        ]
        if any(n > d for n, d in pairs):
            raise ValueError("Scoped quality count exceeds its denominator")
        return self


class ScopedQualityRun(Contract):
    protocol: Literal["reviewed_v1", "reviewed_v2"]
    prompt_version: str = Field(min_length=3, max_length=100)
    policy_version: str = Field(min_length=3, max_length=100)
    selected_models: list[str] = Field(min_length=2, max_length=4)
    chat_id: str = Field(min_length=1, max_length=80)
    status: Literal["completed", "partial", "failed"]
    planned_calls: int = Field(ge=8, le=12)
    actual_calls: int = Field(ge=0, le=20)
    claims_per_author: int = Field(ge=1, le=4)
    tokens: int | None = Field(default=None, ge=0)
    latency_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    labels: ScopedQualityLabels | None = None


class ScopedQualityPair(Contract):
    task_id: str = Field(min_length=1, max_length=100)
    question_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    blinded_labels_declared: bool = False
    v1: ScopedQualityRun
    v2: ScopedQualityRun

    @model_validator(mode="after")
    def comparable(self):
        if (
            self.v1.protocol != "reviewed_v1"
            or self.v2.protocol != "reviewed_v2"
            or self.v1.selected_models != self.v2.selected_models
            or len(set(self.v1.selected_models)) != len(self.v1.selected_models)
        ):
            raise ValueError("Pair requires v1/v2 and the same distinct exact models")
        planned = 2 * len(self.v1.selected_models) + 4
        if self.v1.planned_calls != planned or self.v2.planned_calls != planned:
            raise ValueError("Pair must disclose the actual common base schedule")
        return self


class ScopedQualityEvaluation(Contract):
    protocol_version: Literal["generic-quality-pilot-v2"]
    dataset_frozen_before_labels: bool
    task_set_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    qualification_notes: str = Field(min_length=10, max_length=4000)
    pairs: list[ScopedQualityPair] = Field(default_factory=list, max_length=100)


def summarize_scoped_quality(value):
    study = ScopedQualityEvaluation.model_validate(value)
    result = {
        "protocol_version": study.protocol_version,
        "pairs": len(study.pairs),
        "task_set_hash": study.task_set_hash,
        "dataset_frozen_before_labels": study.dataset_frozen_before_labels,
        "quality_status": "independent_quality_pending",
        "statistical_significance": "not_assessed",
        "general_superiority": "not_established",
        "qualification_notes": study.qualification_notes,
        "arms": {},
        "paired_usefulness": [],
    }
    total_human = 0
    for arm in ("v1", "v2"):
        runs = [getattr(p, arm) for p in study.pairs]
        labels = [r.labels for r in runs if r.labels]
        total_human += sum(l.origin == "human_reported" for l in labels)

        def rate(n, d, labels=labels):
            numerator = sum(getattr(l, n) for l in labels)
            denominator = sum(getattr(l, d) for l in labels)
            return {
                "numerator": numerator,
                "denominator": denominator,
                "rate": numerator / denominator if denominator else None,
            }

        result["arms"][arm] = {
            "runs": len(runs),
            "completed": sum(r.status == "completed" for r in runs),
            "partial": sum(r.status == "partial" for r in runs),
            "failed": sum(r.status == "failed" for r in runs),
            "unlabeled_runs": sum(r.labels is None for r in runs),
            "actual_calls": sum(r.actual_calls for r in runs),
            "unknown_cost_runs": sum(r.cost_usd is None for r in runs),
            "reported_cost_total_usd": sum(
                r.cost_usd for r in runs if r.cost_usd is not None
            )
            if any(r.cost_usd is not None for r in runs)
            else None,
            "extraction_fidelity": rate("faithful_extractions", "extracted_claims"),
            "extraction_coverage": rate(
                "covered_material_claims", "source_material_claims"
            ),
            "valid_proposal_retention": rate(
                "retained_valid_proposals", "valid_scoped_proposals"
            ),
            "unnecessary_rejection": rate(
                "unnecessary_rejections", "valid_scoped_proposals"
            ),
            "missed_defects": rate("missed_defects", "material_defects"),
            "false_closure": rate("false_closures", "closed_objections"),
            "observation_attribution": rate(
                "correctly_attributed_observations", "reported_observations"
            ),
            "test_validity": rate("justified_tests", "proposed_tests"),
            "unsupported_as_established": rate(
                "unsupported_as_established", "material_claims"
            ),
            "direct_usefulness_median": median(l.direct_usefulness for l in labels)
            if labels
            else None,
            "faithfulness_median": median(l.final_faithfulness for l in labels)
            if labels
            else None,
            "critical_failures": [s for l in labels for s in l.critical_failures],
        }
    result["paired_usefulness"] = [
        {
            "task_id": p.task_id,
            "v2_minus_v1": p.v2.labels.direct_usefulness
            - p.v1.labels.direct_usefulness,
        }
        for p in study.pairs
        if p.v1.labels and p.v2.labels
    ]
    if total_human:
        result["quality_status"] = (
            "human_labels_supplied_not_independently_authenticated"
        )
    elif any(r.labels for p in study.pairs for r in (p.v1, p.v2)):
        result["quality_status"] = "synthetic_only"
    return result
