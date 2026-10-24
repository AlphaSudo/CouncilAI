"""Production delivery progresses despite review faults, without creating evidence."""

import json
from copy import deepcopy

import httpx
import pytest

from test_council_chat import drain
from test_review_admission import completed_rejected_reply
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing
from test_unified_council import create
from zerowall.council_review_v3 import UnifiedCouncil
from zerowall.db import DomainError, digest
from zerowall.review_delivery import admit_deliverable, public_text
from zerowall.review_reply_restore import restore_completed_review


FINAL = "The preferred approach is conditional on the stated assumptions. Compare the alternatives and run the proposed test before relying on it."


def test_natural_final_answer_keeps_its_json_examples_and_surrounding_explanation():
    text = 'Use this API payload:\n\n```json\n{"mode":"safe"}\n```\n\nThen check the returned result.'
    assert public_text(text, 'synthesis') == text


def transport(client, app, monkeypatch, failed_phase, *, unsupported_closure=False):
    r = setup_testing(app)
    original, attempts, injected = httpx.Client, [], []
    def handler(request):
        body = json.loads(request.content)
        with r.store.tx() as c:
            chat = json.loads(c.execute("SELECT body FROM records WHERE kind='chat' ORDER BY rowid DESC LIMIT 1").fetchone()[0])
            messages = r.chat.messages(c, chat)
            turn = r.chat.next_turn(chat, messages, c)
            phase = turn['phase']
            if phase == 'opening':
                dt = deepcopy(turn)
                dt['participant']['model'] = ['demo/analyst', 'demo/critic', 'demo/builder'][int(turn['participant']['id'].split('_')[-1]) - 1]
                text = r.chat.demo_answer(chat, messages, dt)
            elif phase == 'synthesis' and r.chat.review.record(c, chat).get('delivery_degraded'):
                payload = json.loads(body['messages'][-1]['content'])
                assert payload['review_incomplete'] is True and 'response_schema' not in payload
                assert payload['public_messages']
                text = FINAL
            else:
                text = r.chat.review.demo(c, chat, messages, turn)
            if phase == 'repair' and unsupported_closure and turn['author_id'] == 'member_1':
                value = json.loads(text)
                for repair in value['repairs']:
                    repair.update(action='retain', revised_text='')
                text = json.dumps(value)
            if phase == failed_phase and not injected:
                injected.append(phase)
                if not unsupported_closure:
                    text = FINAL if phase == 'synthesis' else 'My public discussion remains useful, but the structured review annotation is unavailable.'
                elif phase == 'recheck':
                    value = json.loads(text)
                    value['families'] = []  # Missing optional group checks cannot discard valid assessments.
                    text = json.dumps(value)
            attempts.append({'phase': phase, 'model': body['model'], 'text': text})
        return httpx.Response(200, headers={'content-type':'text/event-stream'}, text=sse(body['model'], text=text))
    monkeypatch.setattr('zerowall.provider.httpx.Client', lambda **kw: original(**kw, transport=httpx.MockTransport(handler)))
    response = client.post('/api/chats', headers={'Idempotency-Key':'noninterrupting-' + failed_phase}, json={
        'provider':'nebius_token_factory', 'prompt':'Compare generic approaches with explicit assumptions.',
        'models':r.settings.policy['council_default_models'], 'budget_usd':2,
        'review_protocol':'reviewed_v3',
    })
    assert response.is_success, response.text
    return r, response.json()['chat']['id'], attempts


@pytest.mark.parametrize('phase,expected_calls', [('extraction',5),('scrutiny',6),('repair',10),('recheck',10),('synthesis',10)])
def test_bad_review_output_at_each_phase_continues_to_an_answer_without_retry(client, app, monkeypatch, phase, expected_calls):
    r, cid, attempts = transport(client, app, monkeypatch, phase)
    drain(app)
    view = client.get('/api/chats/' + cid).json()
    assert view['chat']['status'] == 'completed', view['chat'].get('error')
    assert view['chat'].get('error') is None and view['chat'].get('active_turn') is None
    assert view['review']['delivery_degraded'] is True
    assert len(attempts) == expected_calls
    assert sum(item['phase'] == phase for item in attempts) == (3 if phase == 'repair' else 1)
    assert len([message for message in view['messages'] if message.get('phase') == 'opening']) == 3
    assert view['messages'][-1]['phase'] == 'synthesis'
    assert FINAL in view['messages'][-1]['content']
    assert view['messages'][-1]['partial'] is True
    assert not view['review']['evidence']
    assert view['review']['delivery_warnings']
    if phase == 'extraction':
        assert not view['review']['claims'] and not view['review']['findings']
    assert view['budget']['attempts'] == expected_calls
    assert not app.state.executor.run_once()


def test_unsupported_recheck_closure_keeps_author_revision_and_issue_open(client, app, monkeypatch):
    r, cid, attempts = transport(client, app, monkeypatch, 'recheck', unsupported_closure=True)
    drain(app)
    view = client.get('/api/chats/' + cid).json()
    assert view['chat']['status'] == 'completed', view['chat'].get('error')
    assert len(attempts) == 10
    original_claim = next(claim for claim in view['review']['claims'] if claim['author_id'] == 'member_1')
    assert original_claim['revision'] == 1
    with r.store.tx() as c:
        chat = r.store.get(c, cid, 'chat'); record = r.chat.review.record(c, chat)
        finding = next(item for item in view['review']['findings'] if item['claim_id'] == original_claim['claim_id'])
        assessment = next(item for item in record['rechecks'] if item['finding_id'] == finding['id'])
        assert assessment['resolution'] == 'unresolved_as_assessed'
        assert assessment['closure_basis'] == 'no_effective_change'
        assert not record['focused_authors']
        assert len(record['rechecks']) == len(view['review']['findings'])
        assert all(family.get('recheck_state') == 'not_reviewed' for family in view['review']['families'])
    change = next(change for record in view['review']['admission_records'] for change in record['changes']
                  if change['kind'] == 'unsupported_recheck_closure')
    assert change['before']['resolution'] == 'resolved_as_assessed'
    assert change['after']['resolution'] == 'unresolved_as_assessed'
    assert FINAL in view['messages'][-1]['content']


def test_unexpected_sidecar_bug_rolls_back_annotations_and_preserves_answer(client, app, monkeypatch):
    def broken_extract(self, c, chat, record, output, message_id):
        self.put(c, chat, record, 'review_claim', {'claim_id':'MUST_NOT_SURVIVE', 'revision':1})
        raise RuntimeError('Injected sidecar bug')
    monkeypatch.setattr(UnifiedCouncil, 'extract', broken_extract)
    r, cid, attempts = transport(client, app, monkeypatch, 'never')
    drain(app)
    view = client.get('/api/chats/' + cid).json()
    assert view['chat']['status'] == 'completed', view['chat'].get('error')
    assert len(attempts) == 5 and not view['review']['claims']
    assert FINAL in view['messages'][-1]['content']


def test_new_cycle_clears_delivery_fallback_without_erasing_prior_results(client, app, monkeypatch):
    r, cid, attempts = transport(client, app, monkeypatch, 'extraction')
    drain(app)
    before = client.get('/api/chats/' + cid).json()
    assert before['chat']['status'] == 'completed'
    response = client.post('/api/chats/' + cid + '/messages', headers={'Idempotency-Key':'after-degraded-cycle'},
                           json={'text':'Now compare implementation effort under the same assumptions.'})
    assert response.is_success, response.text
    drain(app)
    after = client.get('/api/chats/' + cid).json()
    assert after['chat']['status'] == 'completed', after['chat'].get('error')
    assert after['review']['cycle'] == 2 and not after['review']['delivery_degraded']
    assert after['messages'][:len(before['messages'])] == before['messages']
    assert len(attempts) == 15


def test_financial_action_boundary_is_not_downgraded_to_a_review_warning(client, app, monkeypatch):
    initial = create(client)
    for _ in range(3):
        app.state.executor.run_once()
    r = app.state.research
    def no_authority(*args, **kwargs):
        raise DomainError('Financial reservation unavailable',402)
    monkeypatch.setattr(r.chat.review, 'admit', no_authority)
    with r.store.tx() as c:
        chat = r.store.get(c, initial['chat']['id'], 'chat')
        turn = r.chat.next_turn(chat, r.chat.messages(c, chat), c)
        with pytest.raises(DomainError, match='Financial reservation unavailable'):
            admit_deliverable(r.chat,c,chat,turn,'Public reply','guarded-delivery')
        assert not r.chat.review.record(c,chat).get('delivery_degraded')


def test_local_recheck_recovery_uses_saved_reply_without_new_inference(client, app, monkeypatch):
    r, chat, call, physical = completed_rejected_reply(client, app, monkeypatch, phase='recheck')
    with r.store.tx() as c:
        call_hash = digest(r.store.list(c,'call',chat['mission_id']))
        money = [tuple(row) for row in c.execute('SELECT * FROM reservations ORDER BY rowid')]
    restored = restore_completed_review(r,call['id'])
    assert restored['new_inference_calls'] == 0 and restored['financial_records_changed'] is False
    assert restored['status'] == 'paused' and len(physical) == 9
    assert restore_completed_review(r,call['id']) == restored
    with r.store.tx() as c:
        assert digest(r.store.list(c,'call',chat['mission_id'])) == call_hash
        assert [tuple(row) for row in c.execute('SELECT * FROM reservations ORDER BY rowid')] == money
