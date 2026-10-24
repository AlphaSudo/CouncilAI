"""Harmless model formatting must survive every stage without a paid retry."""

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from test_council_chat import drain
from test_review_admission import completed_rejected_reply, extraction_context
from test_unified_council import create
from zerowall.contracts import CouncilAuditDescriptor, CouncilScrutiny
from zerowall.council_review_v1 import CouncilReview as LegacyReview
from zerowall.council_review_v2 import ScopedReview
from zerowall.council_review_v3 import UnifiedCouncil
from zerowall.db import DomainError
from zerowall.review_admission import normalize_transport
from zerowall.review_json import parse_review_json
from zerowall.review_reply_restore import restore_completed_review


@pytest.mark.parametrize("wrap", [
    lambda text: text,
    lambda text: '\ufeff\n```json\n' + text + '\n```',
    lambda text: 'Here is the review:\n' + text + '\nAdditional commentary.',
    lambda text: text + '\nThe same payload again:\n' + text,
    lambda text: text[:-1] + ',}',
])
def test_complete_objects_survive_transport_wrapping_without_changing_prose(wrap):
    value = {"text": 'Keep literal commas ,} and braces {x}, escaped "quotes" and \\.',
             "rows": [{"value": 1}]}
    parsed, changes = parse_review_json(wrap(json.dumps(value)))
    assert parsed == value
    assert isinstance(changes, list)


@pytest.mark.parametrize("raw", [
    '{"status":"pass"}\n{"status":"fail"}',
    '{"status":"pass","status":"fail"}',
    '{"value":NaN}',
    '{"value":1',
    'Plain prose with no structured answer.',
])
def test_ambiguous_or_incomplete_data_is_not_silently_selected(raw):
    with pytest.raises(ValueError):
        parse_review_json(raw)


def test_numeric_quantity_text_is_accepted_but_not_invented():
    value = {"claim_ref": "C1", "source_unit_ids": "source:u1", "kind": " Calculation ",
             "scope": "A supplied arithmetic assertion", "expected_value": 2,
             "absolute_tolerance": 0.01, "quantities": {"name": "x", "value": 2.5,
                 "uncertainty": 0.1, "basis": "A model-supplied hypothetical input"},
             "resources": None, "extra_analysis": {"note": "Unverified commentary"}}
    original = deepcopy(value)
    normalized, changes = normalize_transport(value, CouncilAuditDescriptor.model_json_schema())
    result = CouncilAuditDescriptor.model_validate(normalized)
    assert value == original
    assert result.source_unit_ids == ["source:u1"] and result.kind == "calculation"
    assert result.quantities[0].value == "2.5" and result.quantities[0].uncertainty == "0.1"
    assert result.expected_value == "2" and result.absolute_tolerance == "0.01"
    assert result.resources == []
    assert any(c["kind"] == "supplementary_field" and c["before"] == value["extra_analysis"] for c in changes)
    assert normalize_transport(normalized, CouncilAuditDescriptor.model_json_schema()) == (normalized, [])


def test_optional_null_never_becomes_a_numeric_default_or_a_trusted_permission():
    schema = CouncilAuditDescriptor.model_json_schema()
    value = {"claim_ref": "C1", "source_unit_ids": ["source:u1"], "kind": "calculation",
             "scope": "A supplied arithmetic assertion", "output_unit": None,
             "human_verified": True}
    normalized, _ = normalize_transport(value, schema)
    assert normalized["output_unit"] is None and normalized["human_verified"] is True
    with pytest.raises(ValidationError):
        CouncilAuditDescriptor.model_validate(normalized)


def noisy_reply(value):
    """Only representation changes; IDs, revisions and assertions stay the same."""
    value = deepcopy(value)
    def walk(node):
        if isinstance(node, dict):
            for key in list(node):
                if key in ("reason", "explanation", "limitations"):
                    node[key] = "OK"
                elif key in ("groups", "observations", "peer_challenges", "concerns", "evidence_ids") and node[key] == []:
                    node[key] = None
                elif key in ("source_unit_ids", "claim_ids", "finding_ids") and isinstance(node[key], list) and len(node[key]) == 1:
                    node[key] = node[key][0]
                elif key in ("reasoning_kind", "fidelity", "answer_disposition", "resolution") and isinstance(node[key], str):
                    node[key] = ' ' + node[key].replace('_', '-').upper() + ' '
                else:
                    walk(node[key])
            node["additional_comment"] = {"note": "Unverified extra model context"}
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(value)
    return 'Here is the structured response:\n```json\n' + json.dumps(value) + '\n```\nAdditional context is commentary.'


def test_full_council_and_followup_survive_cosmetic_variations_in_every_phase(client, app, monkeypatch):
    original = UnifiedCouncil.demo
    def demo(self, c, chat, messages, turn):
        raw = original(self, c, chat, messages, turn)
        if turn["phase"] == "opening":
            return raw
        value = json.loads(raw)
        if turn["phase"] == "extraction":
            # More than two valid claims from one source is not a transport failure.
            for index in (4, 5):
                value["claims"].append({**deepcopy(value["claims"][0]), "ref": f"C{index}"})
        return noisy_reply(value)
    monkeypatch.setattr(UnifiedCouncil, "demo", demo)
    v = create(client); cid = v["chat"]["id"]
    for cycle in (1, 2):
        drain(app)
        v = client.get('/api/chats/' + cid).json()
        assert v["chat"]["status"] == "completed", v["chat"].get("error")
        assert v["review"]["cycle"] == cycle
        assert len(v["review"]["claims"]) == 5
        assert len([m for m in v["messages"] if m.get('phase') == 'opening']) == cycle * 3
        assert {r["kind"] for a in v["review"]["admission_records"] for r in a["changes"]} >= {
            "supplementary_response_text", "supplementary_field", "canonical_enum", "optional_empty", "singleton_list"}
        if cycle == 1:
            response = client.post(f'/api/chats/{cid}/messages', headers={"Idempotency-Key":"forgiving-followup"},
                                   json={"text":"Reconsider costs under the same assumptions."})
            assert response.is_success, response.text
    assert LegacyReview.claims_per_author_limit == 4 and ScopedReview.claims_per_author_limit == 2


def test_missing_editorial_explanation_does_not_supply_a_positive_check():
    value, changes = normalize_transport({"limitations": None, "findings": []}, CouncilScrutiny.model_json_schema())
    assert "not supplied" in value["limitations"]
    assert value["findings"] == []
    with pytest.raises(ValidationError):
        CouncilScrutiny.model_validate(value)


def test_complete_paid_reply_with_extra_metadata_is_restored_without_a_new_request(client, app, monkeypatch):
    def transform(output):
        # The mock transport serializes this output; an extra field exercises the same intake.
        output["unfamiliar_model_note"] = {"confidence": "model opinion only"}
        return output
    r, chat, call, physical = completed_rejected_reply(client, app, monkeypatch, extraction_transform=transform)
    restored = restore_completed_review(r, call["id"])
    assert restored["new_inference_calls"] == 0 and restored["financial_records_changed"] is False
    assert len(physical) == 4 and not app.state.executor.run_once()
    v = client.get('/api/chats/' + chat["id"]).json()
    assert v["chat"]["status"] == "paused" and v["next_turn"]["phase"] == "scrutiny"
    assert any(c["kind"] == "supplementary_field" for c in v["review"]["admission_records"][0]["changes"])


@pytest.mark.parametrize("broken_claim", [False, True])
def test_auxiliary_index_is_a_warning_but_primary_claim_sources_still_must_exist(client, app, broken_claim):
    r, cid = extraction_context(client, app)
    with r.store.tx() as c:
        chat = r.store.get(c, cid, "chat")
        messages = r.chat.messages(c, chat)
        turn = r.chat.next_turn(chat, messages, c)
        output = json.loads(r.chat.review.demo(c, chat, messages, turn))
        output["inventory"][0]["source_unit_ids"] = ["unknown-source-unit"]
        output["inventory_status"] = "complete_as_assessed"
        if broken_claim:
            output["claims"][0]["source_unit_ids"] = ["unknown-source-unit"]
            with pytest.raises(DomainError):
                r.chat.review.admit(c, chat, turn, json.dumps(output), "bad-primary-source")
            assert not r.chat.review.snapshot(c, chat)["claims"]
        else:
            r.chat.review.admit(c, chat, turn, json.dumps(output), "unlinked-index")
            snap = r.chat.review.snapshot(c, chat)
            assert len(snap["claims"]) == 3 and len(snap["inventory"]) == 2
            assert snap["inventory_status"] == "partial"
            assert not snap["evidence"]
            assert any(change["kind"] == "unlinked_inventory_note" for change in snap["admission_records"][0]["changes"])
