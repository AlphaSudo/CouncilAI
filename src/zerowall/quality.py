"""Offline summary of externally supplied evaluation labels; never a model truth judge."""

from statistics import median
from typing import Literal
from pydantic import Field, model_validator
from .contracts import Contract


class QualityLabels(Contract):
    reviewer: str = Field(min_length=3, max_length=200)
    origin: Literal["human_reported", "synthetic_fixture"]
    material_claims: int = Field(ge=0)
    unsupported_as_established: int = Field(ge=0)
    cited_claims: int = Field(ge=0)
    relevant_citations: int = Field(ge=0)
    objections: int = Field(ge=0)
    invalid_objections: int = Field(ge=0)
    useful_repairs: int = Field(ge=0)
    goal_drift: bool
    direct_usefulness: int = Field(ge=1, le=5)

    @model_validator(mode="after")
    def denominators(self):
        if (
            self.unsupported_as_established > self.material_claims
            or self.relevant_citations > self.cited_claims
            or self.invalid_objections > self.objections
        ):
            raise ValueError("A count exceeds its evaluation denominator")
        return self


class QualityRun(Contract):
    mode: Literal["discussion", "reviewed"]
    chat_id: str = Field(min_length=1, max_length=80)
    status: Literal["completed", "partial", "failed"]
    actual_calls: int = Field(ge=0, le=20)
    latency_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    labels: QualityLabels | None = None


class QualityPair(Contract):
    task_id: str = Field(min_length=1, max_length=100)
    question_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    selected_models: list[str] = Field(min_length=2, max_length=4)
    blinded_labels_declared: bool = False
    discussion: QualityRun
    reviewed: QualityRun

    @model_validator(mode="after")
    def modes(self):
        if (
            self.discussion.mode != "discussion"
            or self.reviewed.mode != "reviewed"
            or len(set(self.selected_models)) != len(self.selected_models)
        ):
            raise ValueError(
                "A pair requires two correct modes and distinct frozen model identities"
            )
        return self


class QualityEvaluation(Contract):
    protocol_version: Literal["generic-quality-pilot-v1"]
    dataset_frozen_before_labels: bool
    qualification_notes: str = Field(min_length=10, max_length=4000)
    pairs: list[QualityPair] = Field(default_factory=list, max_length=100)


def summarize_quality(value):
    if value.get("protocol_version") == "generic-quality-pilot-v3":
        from .quality_v3 import summarize_council_quality
        return summarize_council_quality(value)
    if value.get("protocol_version") == "generic-quality-pilot-v2":
        from .quality_v2 import summarize_scoped_quality
        return summarize_scoped_quality(value)
    study = QualityEvaluation.model_validate(value)
    pairs = study.pairs
    labels = [r.labels for p in pairs for r in (p.discussion, p.reviewed) if r.labels]
    human_count = sum(l.origin == "human_reported" for l in labels)
    result = {
        "protocol_version": study.protocol_version,
        "pairs": len(pairs),
        "dataset_frozen_before_labels": study.dataset_frozen_before_labels,
        "label_status": "human_labels_supplied_not_independently_authenticated"
        if human_count
        else "synthetic_only"
        if labels
        else "independent_quality_pending",
        "human_labeled_runs": human_count,
        "unlabeled_runs": len(pairs) * 2 - len(labels),
        "qualification_notes": study.qualification_notes,
        "statistical_significance": "not_assessed",
        "general_superiority": "not_established",
        "modes": {},
    }
    for mode in ("discussion", "reviewed"):
        runs = [getattr(p, mode) for p in pairs]
        assessed = [r.labels for r in runs if r.labels]

        def rate(numerator, denominator):
            n = sum(getattr(l, numerator) for l in assessed)
            d = sum(getattr(l, denominator) for l in assessed)
            return {"numerator": n, "denominator": d, "rate": n / d if d else None}

        latencies = [r.latency_ms for r in runs if r.latency_ms is not None]
        costs = [r.cost_usd for r in runs if r.cost_usd is not None]
        result["modes"][mode] = {
            "runs": len(runs),
            "completed": sum(r.status == "completed" for r in runs),
            "partial": sum(r.status == "partial" for r in runs),
            "failed": sum(r.status == "failed" for r in runs),
            "actual_calls": sum(r.actual_calls for r in runs),
            "unknown_cost_runs": sum(r.cost_usd is None for r in runs),
            "reported_cost_total_usd": sum(costs) if costs else None,
            "median_latency_ms": median(latencies) if latencies else None,
            "unsupported_as_established": rate(
                "unsupported_as_established", "material_claims"
            ),
            "citation_relevance": rate("relevant_citations", "cited_claims"),
            "invalid_objections": rate("invalid_objections", "objections"),
            "useful_repairs": sum(l.useful_repairs for l in assessed)
            if assessed
            else None,
            "goal_drift_runs": sum(l.goal_drift for l in assessed)
            if assessed
            else None,
            "median_direct_usefulness": median(l.direct_usefulness for l in assessed)
            if assessed
            else None,
        }
    return result
