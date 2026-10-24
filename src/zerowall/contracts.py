"""Validated public contracts. Model output never becomes executable code."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .spending_limits import TOKEN_FACTORY_CAP_USD


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Contract):
    id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=16000)
    provenance: str = Field(min_length=1, max_length=2000)


class StepSpec(Contract):
    key: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=200)
    depends_on: list[str] = Field(default_factory=list, max_length=30)


class MissionBrief(Contract):
    title: str = Field(min_length=3, max_length=160)
    goal: str = Field(min_length=10, max_length=6000)
    deliverable: str = Field(min_length=5, max_length=2000)
    constraints: list[str] = Field(min_length=1, max_length=30)
    rubric: list[str] = Field(min_length=1, max_length=20)
    sources: list[Source] = Field(default_factory=list, max_length=30)
    steps: list[StepSpec] = Field(min_length=1, max_length=30)
    primary_metric: str = "cost_per_valid_task"
    budget_usd: float = Field(default=1, ge=0, le=TOKEN_FACTORY_CAP_USD)
    latency_limit_ms: float = Field(default=60000, gt=0, le=600000)
    material_saving: float = Field(default=0.10, ge=0, lt=1)
    mode: Literal["fixture", "live"] = "fixture"
    openrouter_model: (
        Literal[
            "nvidia/nemotron-3-super-120b-a12b:free",
            "nvidia/nemotron-3.5-super-vl:free",
            "google/gemma-4-31b-it:free",
            "xingchen-agi/xing4.0-29b-a4b:free",
            "nvidia/nemotron-3.5-lightning:free",
        ]
        | None
    ) = None
    provider: Literal["nebius_token_factory", "openrouter_free", "direct_council"] = (
        "nebius_token_factory"
    )

    @model_validator(mode="after")
    def graph(self):
        if self.provider == "openrouter_free":
            self.openrouter_model = (
                self.openrouter_model or "nvidia/nemotron-3-super-120b-a12b:free"
            )
        elif self.openrouter_model is not None:
            raise ValueError(
                "An OpenRouter model belongs only to a free OpenRouter mission"
            )
        if self.provider == "openrouter_free" and (
            self.mode != "live" or self.budget_usd != 0
        ):
            raise ValueError(
                "OpenRouter free missions require live mode and a $0 allowance"
            )
        if (
            self.mode == "live"
            and self.provider == "nebius_token_factory"
            and self.budget_usd <= 0
        ):
            raise ValueError(
                "Token Factory live missions require a positive existing-credit allowance"
            )
        keys = [s.key for s in self.steps]
        if len(set(keys)) != len(keys):
            raise ValueError("Step keys must be unique")
        if len({s.id for s in self.sources}) != len(self.sources):
            raise ValueError("Source IDs must be unique")
        graph = {s.key: s.depends_on for s in self.steps}
        visiting, visited = set(), set()

        def visit(k):
            if k not in graph:
                raise ValueError("Unknown prerequisite")
            if k in visiting:
                raise ValueError("Step dependencies must be acyclic")
            if k in visited:
                return
            visiting.add(k)
            for dep in graph[k]:
                visit(dep)
            visiting.remove(k)
            visited.add(k)

        for k in graph:
            visit(k)
        return self


class RevisionAction(Contract):
    expected_revision: int = Field(ge=1)


class ConcernInput(RevisionAction):
    text: str = Field(min_length=5, max_length=3000)
    severity: Literal["critical", "major", "minor"] = "major"
    blocking: bool = True
    affected_object_ids: list[str] = Field(default_factory=list, max_length=30)
    required_response: str = Field(
        default="Address the mechanism, controls and remaining uncertainty.",
        max_length=2000,
    )


class ConcernDisposition(RevisionAction):
    disposition: str = Field(min_length=10, max_length=3000)
    status: Literal["resolved", "accepted_bounded_risk", "deferred", "blocked"] = (
        "resolved"
    )


class RoundInput(RevisionAction):
    mode: Literal["fixture", "live"] = "fixture"


class ReviewConstraint(Contract):
    text: str = Field(min_length=3, max_length=1000)
    kind: Literal["hard", "soft"] = "hard"


class ReviewOptions(Contract):
    deliverable: str = Field(
        default="A useful answer with explicit assumptions and evidence limits.",
        min_length=3,
        max_length=2000,
    )
    constraints: list[ReviewConstraint] = Field(default_factory=list, max_length=20)
    sources: list[Source] = Field(default_factory=list, max_length=4)
    baseline: str = Field(default="Unspecified", max_length=2000)
    success_criteria: list[str] = Field(default_factory=list, max_length=12)
    evidence_requirement: Literal[
        "model_review", "supplied_sources", "scoped_tool_result"
    ] = "model_review"


class ExtractedClaim(Contract):
    ref: str = Field(pattern=r"^C[1-9][0-9]?$")
    source_message_id: str = Field(min_length=1, max_length=80)
    quote: str = Field(default="", max_length=400)
    source_unit_id: str | None = Field(default=None, max_length=100)
    kind: Literal["factual", "numerical", "proposal", "preference"]
    scope: str = Field(min_length=3, max_length=500)
    assumptions: list[str] = Field(default_factory=list, max_length=8)
    dependencies: list[str] = Field(default_factory=list, max_length=8)


class ExtractionCoverage(Contract):
    message_id: str = Field(min_length=1, max_length=80)
    assessment: Literal["complete_as_assessed", "partial"]
    omitted_material: str = Field(max_length=1500)


class ClaimExtraction(Contract):
    claims: list[ExtractedClaim] = Field(min_length=1, max_length=16)
    coverage: list[ExtractionCoverage] = Field(min_length=1, max_length=4)


class ModelReviewCheck(Contract):
    # Taxonomy is descriptive model content, never an execution or verification capability.
    category: str = Field(min_length=3, max_length=40, pattern=r"^[a-z][a-z_ -]+$")
    status: Literal["pass", "fail", "unknown", "not_applicable"]
    reason: str = Field(min_length=3, max_length=700)


class ScrutinyFinding(Contract):
    claim_id: str = Field(min_length=1, max_length=80)
    claim_revision: int = Field(ge=1)
    steelman: str = Field(min_length=3, max_length=500)
    objection: str = Field(min_length=3, max_length=1000)
    candidate_test: str = Field(min_length=3, max_length=700)
    minimum_resolution: str = Field(min_length=3, max_length=700)
    checks: list[ModelReviewCheck] = Field(min_length=1, max_length=7)
    evidence_ids: list[str] = Field(default_factory=list, max_length=8)


class ScrutinyOutput(Contract):
    findings: list[ScrutinyFinding] = Field(min_length=1, max_length=16)
    limitations: str = Field(min_length=3, max_length=1500)


class ClaimRepair(Contract):
    claim_id: str = Field(min_length=1, max_length=80)
    claim_revision: int = Field(ge=1)
    finding_ids: list[str] = Field(max_length=16)
    action: Literal["retain", "rebut", "narrow", "revise", "withdraw"]
    response: str = Field(min_length=3, max_length=1200)
    revised_text: str = Field(default="", max_length=1600)
    revised_assumptions: list[str] = Field(default_factory=list, max_length=8)
    remaining_uncertainty: str = Field(min_length=3, max_length=700)


class RepairOutput(Contract):
    repairs: list[ClaimRepair] = Field(min_length=1, max_length=4)


class RecheckFinding(Contract):
    finding_id: str = Field(min_length=1, max_length=80)
    proposed_disposition: Literal[
        "issue_remains",
        "rebutted_as_assessment",
        "narrowed",
        "withdrawn",
        "no_issue_as_assessed",
    ]
    reason: str = Field(min_length=3, max_length=1000)


class RecheckOutput(Contract):
    assessments: list[RecheckFinding] = Field(max_length=16)
    limitations: str = Field(min_length=3, max_length=1500)


class AnswerBlock(Contract):
    section: Literal[
        "direct_answer",
        "supported",
        "conditional",
        "unresolved",
        "withdrawn",
        "next_tests",
    ]
    text: str = Field(min_length=3, max_length=2000)
    claim_ids: list[str] = Field(min_length=1, max_length=16)
    evidence_ids: list[str] = Field(default_factory=list, max_length=16)


class SynthesisDraft(Contract):
    blocks: list[AnswerBlock] = Field(min_length=1, max_length=20)


class ReviewDispositionInput(RevisionAction):
    finding_id: str = Field(min_length=1, max_length=80)
    status: Literal["unresolved", "rebutted", "confirmed_defect", "accepted_risk"]
    reason: str = Field(min_length=10, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=16)


class ReviewEvidenceInput(RevisionAction):
    claim_id: str = Field(min_length=1, max_length=80)
    claim_revision: int = Field(ge=1)
    content: str = Field(default="", max_length=16000)
    provenance: str = Field(min_length=3, max_length=2000)
    evidence_id: str | None = None
    relation: Literal["supports", "challenges"]
    assessment_reason: str = Field(default="", max_length=2000)
    supported_scope: str = Field(default="", max_length=500)
    scope_coverage: Literal["whole_claim_as_assessed", "partial", "unknown"] = "unknown"
    directness: Literal["direct", "indirect", "unknown"] = "unknown"
    reproduction: str = Field(default="Unknown", max_length=1000)


class ReviewReassignment(RevisionAction):
    phase: Literal["extraction", "scrutiny", "recheck", "synthesis", "repair"]
    participant_id: str
    original_author_id: str | None = None
    reason: str = Field(min_length=5, max_length=1000)


class ReviewContractChange(RevisionAction):
    question: str = Field(min_length=3, max_length=8000)
    options: ReviewOptions


class ChatCreate(Contract):
    spending_scope: Literal["conversation", "shared_existing_credit"] = "conversation"
    thinking_level: Literal["quick", "balanced", "deep", "maximum"] = "balanced"
    search_web: bool | None = None
    collective_research: bool = True
    search_query: str = Field(default="", max_length=400)
    defer_start: bool = False
    research_tools: bool = False
    prompt: str = Field(min_length=3, max_length=8000)
    provider: Literal[
        "fixture", "openrouter_free", "nebius_token_factory", "direct_council"
    ] = "fixture"
    models: list[str] = Field(min_length=2, max_length=4)
    max_rounds: int = Field(default=1, ge=1, le=3)
    budget_usd: float = Field(default=0, ge=0, le=TOKEN_FACTORY_CAP_USD)
    mode: Literal["discussion", "reviewed"] = "reviewed"
    review_protocol: Literal["reviewed_v1", "reviewed_v2", "reviewed_v3", "reviewed_v4"] = (
        "reviewed_v4"
    )
    review_options: ReviewOptions = Field(default_factory=ReviewOptions)

    @model_validator(mode="after")
    def participants(self):
        if self.spending_scope == "shared_existing_credit" and (
            self.provider != "nebius_token_factory" or self.budget_usd != TOKEN_FACTORY_CAP_USD
        ):
            raise ValueError("Shared credit councils use the existing $24 aggregate cap")
        if self.mode == "discussion" and "review_protocol" not in self.model_fields_set:
            self.review_protocol = "reviewed_v1"
        if (
            self.review_protocol in ("reviewed_v2", "reviewed_v3", "reviewed_v4")
            and self.mode != "reviewed"
        ):
            raise ValueError("Scoped review requires Reviewed council mode")
        if self.mode == "reviewed" and self.max_rounds != 1:
            raise ValueError(
                "Reviewed council uses one scrutiny/repair cycle; set max_rounds to 1"
            )
        self.prompt = self.prompt.strip()
        if len(self.prompt) < 3:
            raise ValueError("Enter a council question with at least three characters")
        if len(set(self.models)) != len(self.models):
            raise ValueError("Select distinct models for a multi-model council")
        if self.provider != "nebius_token_factory" and self.budget_usd != 0:
            raise ValueError("Free and demo councils require a $0 allowance")
        return self


class ChatMessageInput(Contract):
    text: str = Field(min_length=1, max_length=8000)
    review_protocol: Literal["reviewed_v2", "reviewed_v3", "reviewed_v4"] | None = None
    action: Literal["review", "explain", "challenge"] = "review"
    claim_ids: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def nonempty(self):
        self.text = self.text.strip()
        if not self.text:
            raise ValueError("Enter a message")
        return self


class ChatMessageEdit(ChatMessageInput):
    expected_revision: int = Field(ge=1)
    authorize_retry_with_unknown_charge: bool = False


class ChatControl(Contract):
    action: Literal[
        "pause",
        "resume",
        "stop",
        "finish",
        "accept",
        "recover_output",
        "continue_without_model",
    ]
    authorize_retry_with_unknown_charge: bool = False
    recovery_call_id: str | None = Field(default=None, max_length=80)
    additional_allowance_usd: float = Field(default=0, ge=0, le=TOKEN_FACTORY_CAP_USD)

    @model_validator(mode="after")
    def allowance_scope(self):
        if self.additional_allowance_usd and self.action != "continue_without_model":
            raise ValueError(
                "Additional allowance requires an explicit continue-without-model action"
            )
        return self


class ContinueRound(RevisionAction):
    authorize_retry_with_unknown_charge: bool = False


class Submission(Contract):
    mechanism: str = Field(min_length=10, max_length=6000)
    prediction: str = Field(min_length=5, max_length=2000)
    experiment: str = Field(min_length=5, max_length=2000)
    control: str = Field(min_length=5, max_length=2000)
    confounders: list[str] = Field(min_length=1, max_length=12)
    kill_rule: str = Field(min_length=5, max_length=2000)
    affected_layers: list[str] = Field(min_length=1, max_length=8)
    source_ids: list[str] = Field(default_factory=list, max_length=30)
    uncertainty: str = Field(min_length=3, max_length=2000)
    recommendation: str = Field(min_length=3, max_length=2000)


class CrossReview(Contract):
    challenged_hypothesis_ids: list[str] = Field(min_length=1, max_length=20)
    missing_controls: list[str] = Field(min_length=1, max_length=12)
    confounders: list[str] = Field(min_length=1, max_length=12)
    tradeoffs: list[str] = Field(min_length=1, max_length=12)
    evidence_needed: list[str] = Field(min_length=1, max_length=12)
    concern_responses: dict[str, str] = Field(default_factory=dict)
    revised_recommendation: str = Field(min_length=10, max_length=3000)


class BoundArgs(Contract):
    bytes_moved: float = Field(gt=0, le=1e18)
    bandwidth_gbps: float = Field(gt=0, le=1e6)
    assumptions: list[str] = Field(min_length=1, max_length=20)


class TrialObservation(Contract):
    task_id: str = Field(min_length=1, max_length=80)
    cell: Literal["C00", "C10", "C01", "C11"]
    cost_usd: float = Field(ge=0, le=25)
    latency_ms: float = Field(ge=0, le=1e7)
    valid: bool
    split: Literal["exploration", "confirmation"] = "exploration"
    repeat: int = Field(default=0, ge=0, le=20)


class CompareArgs(Contract):
    observations: list[TrialObservation] = Field(min_length=1, max_length=1000)
    material_saving: float = Field(default=0.1, ge=0, lt=1)
    latency_limit_ms: float = Field(default=60000, gt=0, le=1e7)


class RubricArgs(Contract):
    scores: dict[str, Annotated[float, Field(ge=0, le=4)]]
    required: list[str] = Field(min_length=1, max_length=20)
    minimum: float = Field(default=3, ge=0, le=4)
    reviewer: str = Field(min_length=1, max_length=200)
    reviewed_evidence_ids: list[str] = Field(min_length=1, max_length=30)


class ImportArgs(Contract):
    content: str = Field(min_length=1, max_length=150000)
    source: str = Field(min_length=1, max_length=2000)
    collected_at: str = Field(min_length=10, max_length=80)
    method: str = Field(min_length=5, max_length=2000)


class ValidateArgs(Contract):
    source_ids: list[str]
    claims: list[dict[str, str]] = Field(max_length=100)


class InferenceArgs(Contract):
    prompt: str = Field(min_length=1, max_length=16000)
    source_ids: list[str] = Field(default_factory=list, max_length=30)
    max_output_tokens: int = Field(default=1024, ge=32, le=4096)
    task_id: str = Field(default="director-trial", min_length=1, max_length=80)


class BenchmarkArgs(Contract):
    split: Literal["exploration", "confirmation"] = "exploration"
    repeats: int = Field(default=1, ge=1, le=3)
    routing_treatment_approved: bool = False


CAPABILITY_ARGS = {
    "analysis.calculate_bound": BoundArgs,
    "analysis.compare_trials": CompareArgs,
    "analysis.evaluate_rubric": RubricArgs,
    "evidence.import": ImportArgs,
    "evidence.validate": ValidateArgs,
    "inference.validate_request": InferenceArgs,
    "inference.run_trial": InferenceArgs,
    "inference.run_benchmark": BenchmarkArgs,
    "artifacts.package": None,
}


class ExperimentInput(RevisionAction):
    title: str = Field(min_length=5, max_length=200)
    hypothesis_ids: list[str] = Field(min_length=1, max_length=20)
    capability: str
    args: dict
    control: str = Field(min_length=3, max_length=2000)
    treatment: str = Field(min_length=3, max_length=2000)
    prediction: str = Field(min_length=5, max_length=2000)
    kill_rule: str = Field(min_length=5, max_length=2000)
    information_value: int = Field(default=3, ge=1, le=5)
    impact: int = Field(default=3, ge=1, le=5)
    feasibility: int = Field(default=4, ge=1, le=5)
    cost_score: int = Field(default=5, ge=1, le=5)
    priority_reason: str = Field(default="Director-defined priority", max_length=2000)
    tradeoff_ids: list[str] = Field(default_factory=list, max_length=20)
    refinement_of: str | None = None
    refinement_reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def capability_args(self):
        if self.capability not in CAPABILITY_ARGS:
            raise ValueError("Unregistered capability")
        contract = CAPABILITY_ARGS[self.capability]
        if contract:
            self.args = contract.model_validate(self.args).model_dump()
        elif self.args:
            raise ValueError("This capability takes no arguments")
        if (
            self.capability == "inference.run_benchmark"
            and not self.args["routing_treatment_approved"]
        ):
            raise ValueError(
                "The departure from default model priority requires director approval"
            )
        return self


class TradeoffInput(RevisionAction):
    category: Literal[
        "synergy",
        "conflict",
        "constraint_conversion",
        "hidden_cost_removal",
        "adaptive_hybrid",
        "new_operating_point",
    ]
    title: str = Field(min_length=3, max_length=200)
    expected_pros: list[str]
    expected_cons: list[str]
    observed_pros: list[str] = Field(default_factory=list)
    observed_cons: list[str] = Field(default_factory=list)
    hidden_costs: list[str]
    mitigations: list[str]
    operating_region: str
    complexity: str
    rejection_rule: str
    evidence_ids: list[str] = Field(default_factory=list)


class ChallengeGroupInput(RevisionAction):
    title: str = Field(min_length=3, max_length=200)
    hypothesis_ids: list[str] = Field(min_length=1, max_length=30)
    review_ids: list[str] = Field(default_factory=list, max_length=30)
    group_id: str | None = None
    group_revision: int = Field(default=1, ge=1)


class ReframeInput(RevisionAction):
    reason: str = Field(min_length=10, max_length=3000)
    interpretation: str = Field(min_length=10, max_length=3000)
    prediction_comparison: str = Field(min_length=10, max_length=3000)
    changed_assumptions: list[str] = Field(min_length=1, max_length=20)
    alternative_explanations: list[str] = Field(min_length=1, max_length=20)
    next_action: str = Field(min_length=5, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1, max_length=30)
    hypothesis_states: dict[
        str, Literal["supported", "falsified", "blocked", "superseded"]
    ] = Field(default_factory=dict)


class DecisionInput(RevisionAction):
    conclusion: str = Field(min_length=10, max_length=5000)
    verdict: Literal["confirmed", "rejected", "inconclusive", "invalid"]
    agreement: Literal[
        "strong_consensus",
        "conditional_consensus",
        "majority_with_dissent",
        "unresolved",
    ]
    alternatives: list[str] = Field(min_length=1)
    reasons: list[str] = Field(min_length=1)
    dissent: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(min_length=1)
    reopen_triggers: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class LiveVerification(Contract):
    existing_credit_usd: float = Field(gt=0, le=25)
    operational_cap_usd: float = Field(gt=0, le=TOKEN_FACTORY_CAP_USD)
    credit_only_confirmed: bool
    automatic_payments_disabled: bool
    billing_evidence: str = Field(min_length=15, max_length=3000)
    catalog_model_ids: list[str] = Field(min_length=1, max_length=30)
    prices: dict[str, dict[str, float]]
    price_source: str = Field(min_length=10, max_length=2000)
    token_bound_verified: bool
    token_bound_evidence: str = Field(min_length=15, max_length=3000)
    all_billing_categories_bounded: bool
    additional_billed_output_tokens: int = Field(ge=0, le=131072)
    billed_input_multiplier: float = Field(ge=1, le=16)
    expires_in_hours: int = Field(default=24, ge=1, le=48)
    acknowledgement: Literal[
        "Use existing credit only; authorize no additional payment."
    ]


class SessionInput(Contract):
    token: str = Field(min_length=32, max_length=200)


# Scoped review DTOs contain model assessments, never server permissions or tool origins.
class AtomicClaim(Contract):
    ref: str = Field(pattern=r"^C[1-9][0-9]?$")
    source_message_id: str = Field(min_length=1, max_length=80)
    source_unit_ids: list[str] = Field(min_length=1, max_length=3)
    assertion: str = Field(min_length=3, max_length=360)
    scope: str = Field(min_length=3, max_length=180)
    assumptions: list[str] = Field(default_factory=list, max_length=4)
    dependencies: list[str] = Field(default_factory=list, max_length=4)
    reasoning_kind: Literal[
        "definition", "deduction", "empirical", "proposal", "evaluation", "unclear"
    ]
    properties: list[
        Literal[
            "quantitative",
            "causal",
            "comparative",
            "normative",
            "existential",
            "universal",
        ]
    ] = Field(default_factory=list, max_length=6)
    fidelity: Literal["faithful_as_assessed", "uncertain", "compound_remaining"]
    materiality: str = Field(min_length=3, max_length=120)
    evidence_obligation: str = Field(min_length=3, max_length=160)


class ClaimGroup(Contract):
    refs: list[str] = Field(min_length=2, max_length=8)
    relation: Literal["equivalent_as_assessed", "related", "conflicting"]
    reason: str = Field(min_length=3, max_length=160)


class ReportedObservation(Contract):
    source_message_id: str = Field(min_length=1, max_length=80)
    source_unit_id: str = Field(min_length=1, max_length=100)
    classification: Literal[
        "unsupported_self_report",
        "externally_attributed",
        "hypothetical",
        "quoted",
        "supplied_reference",
    ]
    trace_reference: str = Field(default="", max_length=120)
    reason: str = Field(min_length=3, max_length=180)


class AtomicExtraction(Contract):
    claims: list[AtomicClaim] = Field(min_length=1, max_length=8)
    coverage: list[ExtractionCoverage] = Field(min_length=1, max_length=4)
    groups: list[ClaimGroup] = Field(default_factory=list, max_length=4)
    observations: list[ReportedObservation] = Field(default_factory=list, max_length=16)
    observation_coverage: str = Field(min_length=3, max_length=300)
    observation_status: Literal["complete_as_assessed", "partial", "overflow"] = (
        "partial"
    )


class CandidateTest(Contract):
    method: str = Field(min_length=3, max_length=180)
    disconfirming_outcome: str = Field(min_length=3, max_length=140)
    baseline: str = Field(min_length=3, max_length=120)
    threshold_basis: str = Field(min_length=3, max_length=120)
    limitations: str = Field(min_length=3, max_length=160)


class ScopedFinding(ScrutinyFinding):
    target: str = Field(min_length=3, max_length=120)
    in_scope_reason: str = Field(min_length=3, max_length=160)
    concern_kind: Literal[
        "contradiction",
        "missing_evidence",
        "condition",
        "operational_limitation",
        "residual_risk",
    ]
    test: CandidateTest


class ScopedScrutiny(Contract):
    findings: list[ScopedFinding] = Field(min_length=1, max_length=8)
    limitations: str = Field(min_length=3, max_length=500)


class RemainingConcern(Contract):
    kind: Literal[
        "contradiction",
        "missing_evidence",
        "condition",
        "operational_limitation",
        "residual_risk",
        "new_issue",
    ]
    detail: str = Field(min_length=3, max_length=180)
    affected_scope: str = Field(min_length=3, max_length=120)
    materiality: Literal["decision_changing", "ordinary", "unknown"]


class ScopedRecheckFinding(Contract):
    finding_id: str = Field(min_length=1, max_length=80)
    original_revision: int = Field(ge=1)
    current_revision: int = Field(ge=1)
    resolution: Literal[
        "resolved_as_assessed",
        "partly_resolved_as_assessed",
        "unresolved_as_assessed",
        "withdrawn",
    ]
    closure_basis: Literal[
        "rebuttal",
        "content_removed",
        "scope_narrowed",
        "condition_explicit",
        "actual_correction",
        "withdrawal",
        "no_effective_change",
    ]
    comparison: str = Field(min_length=3, max_length=240)
    concerns: list[RemainingConcern] = Field(default_factory=list, max_length=2)
    test_assessment: Literal[
        "suitable_as_assessed", "needs_revision", "unknown", "not_applicable"
    ]
    test_reason: str = Field(min_length=3, max_length=160)


class ScopedRecheck(Contract):
    assessments: list[ScopedRecheckFinding] = Field(min_length=1, max_length=8)
    limitations: str = Field(min_length=3, max_length=500)


class ScopedClaimRepair(ClaimRepair):
    revised_scope: str = Field(min_length=3, max_length=500)


class ScopedRepair(Contract):
    repairs: list[ScopedClaimRepair] = Field(min_length=1, max_length=2)


class ScopedAnswerBlock(AnswerBlock):
    claim_revisions: list[int] = Field(min_length=1, max_length=8)
    issue_ids: list[str] = Field(default_factory=list, max_length=16)


class ScopedSynthesis(Contract):
    answer_disposition: Literal[
        "recommendation",
        "conditional_choice",
        "comparison_only",
        "no_justified_decision",
    ]
    blocks: list[ScopedAnswerBlock] = Field(min_length=1, max_length=12)


# Current Council descriptors are proposed by models. Trusted origins/results are
# assigned by the application after source/revision admission.
# Current prose uses stage token guidance and a whole-response safety envelope.
# Legacy editorial character limits remain in the historical DTOs above.
class CouncilAtomicClaim(AtomicClaim):
    assertion: str = Field(min_length=3)
    scope: str = Field(min_length=3)
    materiality: str = Field(min_length=3)
    evidence_obligation: str = Field(min_length=3)


class CouncilExtractionCoverage(ExtractionCoverage):
    omitted_material: str


class CouncilClaimGroup(ClaimGroup):
    reason: str = Field(min_length=1)


class CouncilReportedObservation(ReportedObservation):
    reason: str = Field(min_length=1)
    trace_reference: str = ""


class CouncilReviewCheck(ModelReviewCheck):
    category: str = Field(min_length=3, pattern=r"^[a-z][a-z_ -]+$")
    reason: str = Field(min_length=1)


class CouncilOutputContract(Contract):
    deliverable: Literal[
        "answer", "explanation", "comparison", "ranked_approaches", "plan"
    ] = "answer"
    requested_count: int | None = Field(default=None, ge=1, le=20)
    criteria: list[str] = Field(default_factory=list, max_length=5)
    assumptions: list[str] = Field(default_factory=list, max_length=4)


class AuditQuantity(Contract):
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,23}$")
    value: str | None = Field(default=None, max_length=80)
    unit: str = Field(default="1", max_length=30)
    quantity_kind: str = Field(default="number", max_length=40)
    basis: str = Field(min_length=3, max_length=160)
    uncertainty: str | None = Field(default=None, max_length=80)


class ResourceTerm(Contract):
    name: str = Field(min_length=1, max_length=80)
    direction: Literal["input", "output", "maintenance", "static_requirement"]
    value: str | None = Field(default=None, max_length=80)
    unit: str = Field(default="unknown", max_length=30)
    basis: str = Field(min_length=3, max_length=160)


class CouncilAuditQuantity(AuditQuantity):
    value: str | None = None
    uncertainty: str | None = None
    unit: str = "1"
    quantity_kind: str = "number"
    basis: str = Field(min_length=3)


class CouncilResourceTerm(ResourceTerm):
    name: str = Field(min_length=1)
    value: str | None = None
    unit: str = "unknown"
    basis: str = Field(min_length=3)


class CouncilAuditDescriptor(Contract):
    claim_ref: str = Field(min_length=1, max_length=80)
    source_unit_ids: list[str] = Field(min_length=1, max_length=3)
    kind: Literal["calculation", "resource", "citation"]
    scope: str = Field(min_length=3)
    expression: str = ""
    quantities: list[CouncilAuditQuantity] = Field(default_factory=list, max_length=8)
    output_unit: str = "1"
    output_kind: str = "number"
    expected_value: str | None = None
    absolute_tolerance: str = "0"
    boundary: str = ""
    denominator: str = ""
    numerator: str = ""
    is_ratio: bool = False
    resources: list[CouncilResourceTerm] = Field(default_factory=list, max_length=8)
    missing_terms: list[str] = Field(default_factory=list, max_length=5)
    reference: str = ""
    claimed_support: str = ""


class CouncilInventoryItem(Contract):
    source_message_id: str = Field(min_length=1, max_length=80)
    source_unit_ids: list[str] = Field(min_length=1, max_length=3)
    category: Literal[
        "approach", "quantity", "equation", "citation", "constraint", "other"
    ]
    description: str = Field(min_length=3)
    claim_refs: list[str] = Field(default_factory=list, max_length=3)


class CouncilFamily(Contract):
    name: str = Field(min_length=3)
    mechanism: str = Field(min_length=3)
    refs: list[str] = Field(min_length=1, max_length=8)
    assumptions: str = Field(min_length=3)
    resources: str = Field(min_length=3)
    distinguishing_test: str = Field(min_length=3)


class CouncilExtraction(AtomicExtraction):
    claims: list[CouncilAtomicClaim] = Field(min_length=1, max_length=8)
    coverage: list[CouncilExtractionCoverage] = Field(min_length=1, max_length=4)
    groups: list[CouncilClaimGroup] = Field(default_factory=list, max_length=4)
    observations: list[CouncilReportedObservation] = Field(
        default_factory=list, max_length=16
    )
    observation_coverage: str = Field(min_length=1)
    output_contract: CouncilOutputContract
    inventory: list[CouncilInventoryItem] = Field(default_factory=list, max_length=16)
    inventory_status: Literal["complete_as_assessed", "partial", "overflow"] = "partial"
    inventory_limitations: str = Field(min_length=1)
    audits: list[CouncilAuditDescriptor] = Field(default_factory=list, max_length=8)
    families: list[CouncilFamily] = Field(default_factory=list, max_length=8)


class CouncilPeerChallenge(Contract):
    claim_id: str = Field(min_length=1, max_length=80)
    claim_revision: int = Field(ge=1)
    objection: str = Field(min_length=3)
    decision_impact: str = Field(min_length=3)
    candidate_test: str = Field(min_length=3)


class CouncilClaimRepair(ScopedClaimRepair):
    response: str = Field(min_length=3)
    revised_text: str = Field()
    revised_scope: str = Field(min_length=3)
    remaining_uncertainty: str = Field(min_length=1)

    @model_validator(mode="after")
    def actual_revision(self):
        if self.action in ("narrow", "revise") and len(self.revised_text.strip()) < 3:
            raise ValueError(
                "A narrow/revise action requires the actual revised assertion in revised_text"
            )
        return self


class CouncilDeliberation(ScopedRepair):
    repairs: list[CouncilClaimRepair] = Field(min_length=1, max_length=8)
    explanation: str = Field(min_length=1)
    peer_challenges: list[CouncilPeerChallenge] = Field(
        default_factory=list, max_length=2
    )


class CouncilCandidateTest(CandidateTest):
    method: str = Field(min_length=3)
    disconfirming_outcome: str = Field(min_length=3)
    baseline: str = Field(min_length=3)
    threshold_basis: str = Field(min_length=3)
    limitations: str = Field(min_length=1)


class CouncilFinding(ScopedFinding):
    # A critic's explanatory note never supplies evidence or changes permissions.
    evidence_obligation: str | None = None
    steelman: str = Field(min_length=3)
    objection: str = Field(min_length=3)
    candidate_test: str = Field(min_length=3)
    minimum_resolution: str = Field(min_length=3)
    checks: list[CouncilReviewCheck] = Field(min_length=1, max_length=7)
    target: str = Field(min_length=3)
    in_scope_reason: str = Field(min_length=3)
    test: CouncilCandidateTest


class CouncilScrutiny(Contract):
    findings: list[CouncilFinding] = Field(min_length=1, max_length=8)
    limitations: str = Field(min_length=1)


class CouncilRemainingConcern(RemainingConcern):
    detail: str = Field(min_length=3)
    affected_scope: str = Field(min_length=3)


class CouncilRecheckFinding(ScopedRecheckFinding):
    comparison: str = Field(min_length=1)
    test_reason: str = Field(min_length=1)
    concerns: list[CouncilRemainingConcern] = Field(default_factory=list, max_length=2)


class CouncilFamilyAssessment(Contract):
    family_id: str = Field(min_length=1, max_length=80)
    claim_ids: list[str] = Field(min_length=1, max_length=8)
    claim_revisions: list[int] = Field(min_length=1, max_length=8)
    still_distinct_as_assessed: bool
    reason: str = Field(min_length=1)


class CouncilRecheck(ScopedRecheck):
    limitations: str = Field(min_length=1)
    assessments: list[CouncilRecheckFinding] = Field(min_length=1, max_length=24)
    families: list[CouncilFamilyAssessment] = Field(max_length=8)


class CouncilRankedApproach(Contract):
    family_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1)


class CouncilAnswerBlock(ScopedAnswerBlock):
    text: str = Field(min_length=3)


class CouncilSynthesis(ScopedSynthesis):
    blocks: list[CouncilAnswerBlock] = Field(min_length=1, max_length=12)
    ranked_approaches: list[CouncilRankedApproach] = Field(
        default_factory=list, max_length=8
    )
    deliverable_limitations: str = ""


class CouncilDeltaScope(Contract):
    claim_ids: list[str] = Field(min_length=1, max_length=8)
    within_claim_scope: bool
    reason: str = Field(min_length=1)
    output_contract: CouncilOutputContract


class ContextCompactionInput(Contract):
    mode: Literal["adaptive", "compact"] = "compact"


class SharedSpendingInput(Contract):
    scope: Literal["shared_existing_credit"]


class ThinkingPreferenceInput(Contract):
    level: Literal["quick", "balanced", "deep", "maximum"]


class ConversationAllowanceInput(Contract):
    add_usd: float = Field(gt=0, le=TOKEN_FACTORY_CAP_USD)
