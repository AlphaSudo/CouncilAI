"""Lists and objects used as descriptive prose must not stop paid council work."""

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from test_council_chat import drain
from test_review_admission import completed_rejected_reply
from test_unified_council import create
from zerowall.contracts import CouncilAuditDescriptor, CouncilFamily
from zerowall.council_review_v3 import UnifiedCouncil
from zerowall.review_admission import normalize_transport
from zerowall.review_reply_restore import restore_completed_review


FAMILY = {
    "name": "Angle-selective interface",
    "mechanism": "Constrain emission to a declared acceptance angle.",
    "refs": ["C1"],
    "assumptions": ["passive reciprocal structure", "angle-limited operation"],
    "resources": ["solar input power", "fabricated photonic interface"],
    "distinguishing_test": "Measure directional absorptance and emissivity with all losses declared.",
}


@pytest.mark.parametrize("field", ["assumptions", "resources", "mechanism", "distinguishing_test"])
@pytest.mark.parametrize("notes", [
    ["First condition", "Second condition with commas, braces {x}, and \\alpha"],
    {"inputs": ["Sunlight", "Interface"], "estimated_count": 0, "measured_cost": None},
])
def test_descriptive_family_fields_accept_lists_and_objects_without_dropping_notes(field, notes):
    raw = {**deepcopy(FAMILY), field: notes}
    original = deepcopy(raw)
    prepared, changes = normalize_transport(raw, CouncilFamily.model_json_schema())
    result = CouncilFamily.model_validate(prepared)
    assert raw == original
    assert isinstance(getattr(result, field), str)
    adjustment = next(change for change in changes if change["path"] == [field])
    assert adjustment["kind"] == "structured_prose" and adjustment["before"] == notes
    if isinstance(notes, list):
        assert all(note in getattr(result, field) for note in notes)
    else:
        assert all(key + ':' in getattr(result, field) for key in notes)
        assert '0' in getattr(result, field) and 'null' in getattr(result, field)
    assert normalize_transport(prepared, CouncilFamily.model_json_schema()) == (prepared, [])


@pytest.mark.parametrize("empty", [[], {}])
def test_empty_optional_family_description_is_explicitly_missing_not_a_verification(empty):
    raw = {**deepcopy(FAMILY), "assumptions": empty, "resources": empty}
    prepared, _ = normalize_transport(raw, CouncilFamily.model_json_schema())
    result = CouncilFamily.model_validate(prepared)
    assert 'not supplied' in result.assumptions and 'not supplied' in result.resources


def test_prose_conversion_never_turns_bad_claim_references_or_units_into_valid_data():
    raw = {**deepcopy(FAMILY), "refs": [{"claim_id": "C1"}]}
    prepared, _ = normalize_transport(raw, CouncilFamily.model_json_schema())
    assert prepared["refs"] == raw["refs"]
    with pytest.raises(ValidationError):
        CouncilFamily.model_validate(prepared)
    audit = {"claim_ref": ["C1"], "source_unit_ids": ["saved:u1"], "kind": "calculation",
             "scope": "A hypothetical supplied calculation", "output_unit": ["W"],
             "expression": ["1", "+", "1"]}
    prepared, _ = normalize_transport(audit, CouncilAuditDescriptor.model_json_schema())
    assert prepared['expression'] == audit['expression'] and prepared['output_unit'] == ['W']
    with pytest.raises(ValidationError):
        CouncilAuditDescriptor.model_validate(prepared)


def structured_family_fields(output):
    output = deepcopy(output)
    for family in output['families']:
        family['assumptions'] = [family['assumptions'], 'This is a model assessment only.']
        family['resources'] = {'declared_inputs': [family['resources']], 'measured_cost': None}
    return output


def test_two_full_cycles_accept_structured_notes_in_every_stage(client, app, monkeypatch):
    original = UnifiedCouncil.demo
    def demo(self, c, chat, messages, turn):
        raw = original(self, c, chat, messages, turn)
        if turn['phase'] == 'opening':
            return raw
        value = json.loads(raw)
        if turn['phase'] == 'extraction':
            value = structured_family_fields(value)
            value['claims'][0]['assumptions'] = [{'scope': 'Synthetic demonstration only'}]
        elif turn['phase'] == 'scrutiny':
            value['limitations'] = ['Synthetic reviewer only', 'No independent evidence']
            value['findings'][0]['steelman'] = {'summary': value['findings'][0]['steelman']}
            value['findings'][0]['evidence_obligation'] = {'requirement': 'Independent scoped evidence is needed.'}
        elif turn['phase'] == 'repair':
            value['explanation'] = [value['explanation']]
            for repair in value['repairs']:
                repair['response'] = [repair['response']]
                repair['revised_text'] = [repair['revised_text']]
        elif turn['phase'] == 'recheck':
            value['limitations'] = {'scope': value['limitations']}
            for assessment in value['assessments']:
                assessment['comparison'] = [assessment['comparison']]
        elif turn['phase'] == 'synthesis':
            for block in value['blocks']:
                block['text'] = [block['text']]
        return json.dumps(value)
    monkeypatch.setattr(UnifiedCouncil, 'demo', demo)
    initial = create(client); cid = initial['chat']['id']
    for cycle in (1, 2):
        drain(app)
        view = client.get('/api/chats/' + cid).json()
        assert view['chat']['status'] == 'completed', view['chat'].get('error')
        assert view['review']['cycle'] == cycle
        assert len([m for m in view['messages'] if m.get('phase') == 'opening']) == 3 * cycle
        records = view['review']['admission_records']
        assert all(any(change['kind'] == 'structured_prose' for change in record['changes']) for record in records)
        assert len(view['review']['claims']) == 3 and not view['review']['evidence']
        if cycle == 1:
            response = client.post('/api/chats/' + cid + '/messages',
                headers={'Idempotency-Key': 'structured-notes-second-cycle'},
                json={'text': 'Compare the costs again with the same assumptions.'})
            assert response.is_success, response.text


def test_completed_reply_with_family_lists_is_recovered_locally_once(client, app, monkeypatch):
    r, chat, call, physical = completed_rejected_reply(
        client, app, monkeypatch, extraction_transform=structured_family_fields)
    with r.store.tx() as c:
        calls_before = r.store.list(c, 'call', chat['mission_id'])
        money_before = [tuple(row) for row in c.execute('SELECT * FROM reservations ORDER BY rowid')]
    result = restore_completed_review(r, call['id'])
    assert result['new_inference_calls'] == 0 and result['financial_records_changed'] is False
    assert restore_completed_review(r, call['id']) == result
    assert len(physical) == 4 and not app.state.executor.run_once()
    view = client.get('/api/chats/' + chat['id']).json()
    assert view['chat']['status'] == 'paused' and view['chat'].get('error') is None
    assert view['next_turn']['phase'] == 'scrutiny'
    assert 'model assessment only' in view['review']['families'][0]['assumptions']
    with r.store.tx() as c:
        assert r.store.list(c, 'call', chat['mission_id']) == calls_before
        assert [tuple(row) for row in c.execute('SELECT * FROM reservations ORDER BY rowid')] == money_before
