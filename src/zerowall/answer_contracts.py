"""Additive answer-first contracts; legacy schema hashes do not change."""

from typing import Literal

from pydantic import Field

from .contracts import Contract, CouncilFinding


class AnswerFinding(CouncilFinding):
    priority: Literal["critical", "major", "moderate", "minor"] = "moderate"
    decision_impact: str = "Decision impact not supplied"


class FalsificationNote(Contract):
    claim_id: str
    claim_revision: int = Field(ge=1)
    outcome: Literal["attack_did_not_defeat_claim", "uncertain"]
    reason: str
    applicable_lenses: list[str] = Field(default_factory=list, max_length=6)


class AnswerScrutiny(Contract):
    findings: list[AnswerFinding] = Field(default_factory=list, max_length=8)
    notes: list[FalsificationNote] = Field(default_factory=list, max_length=8)
    limitations: str = "Assessment coverage is incomplete"


class StageResult(Contract):
    turn_key: str
    context_hash: str | None = None
    state: Literal["pending", "success", "partial", "degraded", "skipped"]
    generation_state: Literal[
        "not_requested", "responding", "complete", "partial", "unavailable"
    ]
    review_state: Literal["pending", "complete", "incomplete", "unavailable"]
    annotation_coverage: str = "unknown"
    warning_ids: list[str] = Field(default_factory=list)
    call_id: str | None = None
    receipt_id: str | None = None


class ReviewWarning(Contract):
    category: Literal[
        "cosmetic",
        "annotation_quarantine",
        "sidecar_unavailable",
        "provider_unavailable",
        "action_boundary",
    ]
    source_message_id: str | None = None
    path: list[str | int] = Field(default_factory=list)
    consequence: str
    public_note: str
    grants_authority: Literal[False] = False
