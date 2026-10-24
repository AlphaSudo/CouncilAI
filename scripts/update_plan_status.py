"""Apply evidence-backed engineering status without checking live/external gates."""

from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "plans/02_IMPLEMENTATION_PLAN.md"
text = p.read_text(encoding="utf-8")
pending = {
    10,
    14,
    15,
    16,
    17,
    21,
    24,
    25,
    50,
    51,
    69,
    84,
    103,
    111,
    122,
    140,
    143,
    163,
    165,
    166,
    167,
    170,
    173,
    174,
    175,
    177,
    178,
    180,
    184,
    185,
    186,
    188,
    190,
    191,
    193,
    195,
    196,
    197,
    198,
    199,
    200,
    201,
    202,
}
items = []
index = 0


def status(match):
    global index
    checked = index not in pending
    line = match.group(0)
    items.append(
        {
            "index": index,
            "task": line[6:],
            "status": "implemented_and_locally_validated"
            if checked
            else "pending_live_external_or_full_acceptance",
            "evidence": "docs/IMPLEMENTATION_STATUS.md; docs/validation/; tests/; version release record",
        }
    )
    index += 1
    return "- [x]" + line[5:] if checked else "- [ ]" + line[5:]


text = re.sub(r"^- \[[ x]\].*$", status, text, flags=re.M)
if index != 204:
    raise ValueError("Plan changed; review checklist mapping before applying status")
text = text.replace(
    "All checkboxes are future work.",
    "Checkboxes now distinguish implemented/local validation from pending live/external acceptance; see [implementation evidence](../docs/IMPLEMENTATION_STATUS.md).",
)
text = text.replace(
    "Validate response schemas; allow at most one explicitly reserved repair attempt while preserving raw invalid output.",
    "Validate response schemas; keep automatic repairs disabled and use an explicit newly reserved missing-seat continuation while preserving invalid raw output. See implementation decision 002.",
)
text = text.replace(
    "Use semantic similarity as a duplicate suggestion, not authority to suppress an experiment.",
    "Use local domain-concept/lexical similarity as a duplicate suggestion, not authority to suppress an experiment; expose its approximation limits. See implementation decision 002.",
)
p.write_text(text, encoding="utf-8")
(ROOT / "docs/validation/checklist-evidence.json").write_text(
    json.dumps(
        {
            "checked": index - len(pending),
            "total": index,
            "meaning": "Local implementation/test evidence; version release gates retain their separate live/external requirements.",
            "items": items,
        },
        indent=2,
    ),
    encoding="utf-8",
)
p = ROOT / "plans/00_MASTERPLAN.md"
text = p.read_text(encoding="utf-8").replace(
    "All implementation tasks start unchecked. A date, diagram, or fixture is not evidence of completed implementation.",
    "Implementation checkboxes now link local acceptance evidence. See [current implementation status](../docs/IMPLEMENTATION_STATUS.md); live runtime and external release gates remain pending. A date, diagram, or fixture is not evidence of genuine model execution.",
)
p.write_text(text, encoding="utf-8")
releases = {
    "0.1": (
        "Scope, contracts, task packets and model access",
        "Z01–Z04, Z14–Z18, Z22",
        "docs/decisions/001-local-token-factory-scope.md; config/model_policy.json; benchmark/",
        "Billing/credit evidence, verified current prices/categories, bounded genuine NVIDIA probe.",
    ),
    "0.2": (
        "Durable local control plane and credit ledger",
        "Z01, Z04, Z08, Z17, Z22, O01–O03",
        "src/zerowall/{db,budget,api,provider}.py; tests/test_budget.py",
        "Real-call provenance after the director unlocks billing controls.",
    ),
    "0.3": (
        "Private role-isolated commit and atomic reveal",
        "Z02–Z04, Z08, Z22",
        "tests/test_workflow.py; tests/test_recovery.py",
        "Real four-seat submissions; transport/fixture tests are not runtime NVIDIA evidence.",
    ),
    "0.4": (
        "Human governance, cross-review and dependency reopening",
        "Z05–Z08, Z20, O01–O02",
        "tests/test_workflow.py; tests/test_memory.py; service.py",
        "Real research-usefulness inspection; human final authority remains mandatory.",
    ),
    "0.5": (
        "Research memory, ranking, bounded plans and causal records",
        "Z09–Z13, Z15, Z18, Z20",
        "contracts.py; memory.py; executor.py; tests/test_memory.py",
        "Actual measured findings for any empirical claim; concept overlap is approximate.",
    ),
    "0.6": (
        "Registered local tools and guarded API experiment path",
        "Z15–Z18, Z22, O01–O03",
        "tests/test_benchmark_execution.py; tests/test_provider.py; real local calculation pack",
        "Real approved API experiment after live prerequisites; no GPU dependency.",
    ),
    "0.7": (
        "Deterministic gates, analysis, reframe and decision",
        "Z07, Z09–Z16, Z18, Z21",
        "analysis.py; tests/test_analysis.py; local seed/browser mission",
        "Real hosted workflow findings and optional separately budgeted council comparison.",
    ),
    "0.8": (
        "Eight vision views and portable research reports",
        "Z18–Z22, O02–O03, H05, H10",
        "apps/web/e2e/workspace.spec.ts; reports.py; docs/validation/",
        "Additional operator feedback; genuine saved live evidence remains uncollected.",
    ),
    "0.9": (
        "Recovery/integrity, backup, clean setup and test distribution",
        "Z16–Z22, O01–O04",
        "tests/test_recovery.py; tests/test_integrity.py; scripts/backup.py; release ZIP",
        "Independent human setup/reproduction; live validation and public free distribution URL.",
    ),
    "1.00": (
        "Local release candidate and submission materials",
        "Core implementation and H05/H10 materials",
        "README.md; LICENSE; docs/submission/; credential-free release ZIP",
        "Public repository/test-build URL, genuine NVIDIA trace, public video, eligibility/disclosure review, Devpost confirmation and access preservation.",
    ),
}
for version, (title, ids, evidence, next_dependency) in releases.items():
    path = ROOT / f"docs/releases/{version}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {version} · {title}\n\nDate: October 18, 2026. Status: local implementation candidate; the version release gate is not claimed complete.\n\nRequirements: {ids}.\n\nEvidence: {evidence}. See `docs/IMPLEMENTATION_STATUS.md`, `docs/validation/` and the test sources for commands and scope.\n\nValidation: backend test suite, production frontend build, browser workflow, checksummed pack verification and deterministic reanalysis. Provider transport doubles remain labeled software tests; no paid inference was executed.\n\nRemaining dependency: {next_dependency}\n\nBudget: $25 maximum existing-credit authority, $0 additional payments, no rented GPU. Live dispatch remains locked at the director's instruction. Optional X1 is unstarted and is not a gate.\n",
        encoding="utf-8",
    )
print(
    json.dumps(
        {
            "implemented_local_items": index - len(pending),
            "total_items": index,
            "version_records": len(releases),
            "live_gates_complete": False,
        }
    )
)
