"""Protocol invariants for eighteen predeclared cases, not a semantic quality score."""

from copy import deepcopy
from pathlib import Path
import json
import pytest
from pydantic import ValidationError
from zerowall.contracts import ScrutinyOutput
from zerowall.review_policy import publication_decisions, ledger_markdown
from zerowall.analysis import calculate_bound
from test_council_review import completed

CASES = json.loads(
    (Path(__file__).resolve().parents[1] / "benchmark/review_cases.json").read_text()
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_predeclared_review_invariants(case, client, app):
    s = deepcopy(completed(client, app)["review"])
    claim = s["claims"][0]
    finding = s["findings"][0]
    s["claims"] = [claim]
    s["findings"] = [finding]
    s["rechecks"] = [
        {
            "finding_id": finding["id"],
            "claim_revision": claim["revision"],
            "proposed_disposition": "no_issue_as_assessed",
        }
    ]
    s["dispositions"] = []
    s["evidence"] = []
    finding["checks"] = [
        {"category": "reasoning", "status": "pass", "reason": "Model assessment only"}
    ]
    evidence = {
        "id": "test_evidence",
        "claim_id": claim["claim_id"],
        "claim_revision": claim["revision"],
        "integrity": "pass",
        "origin": "director_supplied_source",
        "relation": "supports",
        "assessment_reason": "The director checked the stated scope and relevance.",
    }
    cid = case["id"]
    if cid == "T01":
        calculation = calculate_bound(
            {
                "bytes_moved": 2_000_000_000,
                "bandwidth_gbps": 100,
                "assumptions": ["Decimal bytes per second", "Ideal lower bound only"],
            }
        )
        assert calculation["minimum_seconds"] == 0.02
        s["evidence"] = [
            {
                **evidence,
                "origin": "calculated",
                "tool_capability": "analysis.calculate_bound",
            }
        ]
        s["contract"]["options"]["evidence_requirement"] = "scoped_tool_result"
        assert publication_decisions(s)[0]["permission"] == "supported"
    elif cid in ("T02", "T04", "T14"):
        claim["text"] = "All models agree this untested claim is certainly correct."
        assert publication_decisions(s)[0]["permission"] == "conditional"
    elif cid in ("T03", "T06"):
        finding["checks"][0]["status"] = "fail"
        s["dispositions"] = [
            {
                "finding_id": finding["id"],
                "claim_revision": claim["revision"],
                "status": "rebutted",
                "reason": "The critic's counterexample violates the stated scope.",
            }
        ]
        assert publication_decisions(s)[0]["permission"] == "conditional"
    elif cid == "T05":
        s["evidence"] = [{**evidence, "relation": "challenges"}]
        s["dispositions"] = [
            {
                "finding_id": finding["id"],
                "claim_revision": claim["revision"],
                "status": "confirmed_defect",
                "evidence_ids": [evidence["id"]],
                "reason": "A human assessed a retained in-scope counterexample.",
            }
        ]
        assert publication_decisions(s)[0]["permission"] == "withdrawn"
    elif cid in ("T07", "T08"):
        finding["checks"] = [
            {
                "category": "resources",
                "status": "unknown" if cid == "T08" else "fail",
                "reason": case["expectation"],
            }
        ]
        s["rechecks"] = []
        assert publication_decisions(s)[0]["permission"] == "unresolved"
    elif cid in ("T09", "T10", "T11"):
        if cid == "T09":
            evidence["integrity"] = "invalid"
        elif cid == "T10":
            evidence["assessment_reason"] = ""
        else:
            evidence["claim_revision"] -= 1
        s["evidence"] = [evidence]
        assert publication_decisions(s)[0]["permission"] != "supported"
    elif cid == "T12":
        premise = {
            **claim,
            "id": "premise_revision",
            "claim_id": "premise",
            "dependencies": [],
        }
        claim["dependencies"] = ["premise"]
        s["claims"].append(premise)
        assert publication_decisions(s)[0]["permission"] == "unresolved"
    elif cid == "T13":
        claim["kind"] = "preference"
        finding["checks"] = [
            {
                "category": "reasoning",
                "status": "not_applicable",
                "reason": "No numerical or mathematical assertion is made",
            }
        ]
        assert publication_decisions(s)[0]["permission"] == "conditional"
    elif cid == "T15":
        s["coverage"] = [
            {
                "message_id": "source",
                "assessment": "partial",
                "omitted_material": "An unreviewed section remains.",
            }
        ]
        s["decisions"] = publication_decisions(s)
        assert "unreviewed section" in ledger_markdown(s)
        assert s["decisions"][0]["permission"] != "supported"
    elif cid == "T16":
        s["rechecks"] = []
        s["partial_reasons"] = ["Required recheck unavailable"]
        assert publication_decisions(s)[0]["permission"] == "unresolved"
    elif cid == "T17":
        with pytest.raises(ValidationError):
            ScrutinyOutput.model_validate(
                {
                    "findings": [],
                    "limitations": "A model cannot grant authority.",
                    "trusted_verification": True,
                }
            )
    else:
        s["claims"] = []
        s["decisions"] = []
        assert publication_decisions(s) == []
        assert "No structured claims" in ledger_markdown(s)
