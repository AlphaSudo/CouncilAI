"""The current review must execute through the ordinary entry point, not just fixtures."""

from copy import deepcopy

from zerowall.contracts import ChatCreate
from zerowall.review_exports import verify_review_pack
from test_council_chat import create, drain
from test_council_review import create_review
from test_direct_provider import direct_chat, transport
from test_workflow import post


def view(client, cid):
    return client.get('/api/chats/' + cid).json()


def test_current_default_executes_all_scoped_review_stages(client, app):
    v = post(client, '/chats', {'prompt': 'Compare two generic designs and preserve their necessary conditions.', 'models': ['demo/analyst', 'demo/critic']})
    assert v['chat']['mode'] == 'reviewed'
    assert v['chat']['protocol']['version'] == 'reviewed_v4'
    assert v['review']['contract']['claims_per_author'] == 8
    drain(app)
    v = view(client, v['chat']['id'])
    assert v['chat']['status'] == 'completed', v['chat'].get('error')
    phases = [m['phase'] for m in v['messages']]
    assert phases == ['prompt', 'opening', 'opening', 'extraction', 'scrutiny', 'repair', 'repair', 'recheck', 'synthesis']
    assert v['review']['claims'] and v['review']['decisions']


def test_explicit_legacy_selection_still_uses_its_frozen_protocol():
    body = {'prompt': 'Compare two generic designs.', 'models': ['demo/analyst', 'demo/critic']}
    assert ChatCreate(**body, mode='discussion', max_rounds=2).review_protocol == 'reviewed_v1'
    assert ChatCreate(**body, mode='reviewed', review_protocol='reviewed_v1').review_protocol == 'reviewed_v1'


def test_discussion_adopts_review_on_explicit_followup_in_same_chat(client, app, tmp_path):
    cid = create(client, rounds=1)['chat']['id']
    drain(app)
    old = deepcopy(view(client, cid))
    request = {'text': 'Now compare the strongest distinct approaches under the original constraints.', 'review_protocol': 'reviewed_v2'}
    a = post(client, f'/chats/{cid}/messages', request, key='adopt-scoped-once')
    b = post(client, f'/chats/{cid}/messages', request, key='adopt-scoped-once')
    assert a == b
    assert a['chat']['id'] == cid
    assert a['chat']['protocol_history'][0]['protocol'] == old['chat']['protocol']
    assert a['chat']['protocol_history'][0]['protocol_hash'] == old['chat']['protocol_hash']
    assert old['chat']['original_prompt'] in a['review']['contract']['question']
    assert request['text'] in a['review']['contract']['question']
    assert not a['baseline']
    drain(app)
    v = view(client, cid)
    assert v['chat']['status'] == 'completed', v['chat'].get('error')
    assert v['messages'][:len(old['messages'])] == old['messages']
    assert len(v['baseline']) == 3
    assert all(m.get('review_cycle') == 1 for m in v['baseline'])
    assert len([m for m in v['messages'] if m['phase'] == 'protocol_transition']) == 1
    assert len([m for m in v['messages'] if m['phase'] == 'extraction']) == 1
    assert not v['chat']['accepted']
    exported = post(client, f'/chats/{cid}/review/exports', {})
    path = tmp_path / 'adopted-review.zip'
    path.write_bytes(client.get(exported['download']).content)
    assert verify_review_pack(path)['reproduced']


def test_v1_to_v2_upgrade_preserves_original_publications_and_separates_cycles(client, app, tmp_path):
    cid = create_review(client)['chat']['id']
    drain(app)
    old = deepcopy(view(client, cid))
    r = app.state.research
    with r.store.tx() as c:
        publications = deepcopy(r.store.list(c, 'review_publication', old['chat']['mission_id']))
        prior_record = deepcopy(r.store.get(c, old['chat']['review_id'], 'chat_review'))
    post(client, f'/chats/{cid}/messages', {'text': 'Review the revised tradeoff under 1.02.', 'review_protocol': 'reviewed_v2'})
    drain(app)
    v = view(client, cid)
    assert v['chat']['status'] == 'completed', v['chat'].get('error')
    assert v['review']['cycle'] == old['review']['cycle'] + 1
    assert v['messages'][:len(old['messages'])] == old['messages']
    assert len(v['review']['claims']) == 3
    assert all(x['review_cycle'] == v['review']['cycle'] for x in v['review']['claims'])
    with r.store.tx() as c:
        assert r.store.list(c, 'review_publication', old['chat']['mission_id'])[:len(publications)] == publications
        assert r.store.get(c, prior_record['id'], 'chat_review') == prior_record
    item = post(client, f'/chats/{cid}/review/exports', {})
    path = tmp_path / 'both-versions.zip'
    path.write_bytes(client.get(item['download']).content)
    assert verify_review_pack(path)['reproduced']


def test_upgrade_cannot_change_running_protocol(client, app):
    cid = create(client, rounds=1)['chat']['id']
    old = view(client, cid)
    post(client, f'/chats/{cid}/messages', {'text': 'Switch methods mid-flight.', 'review_protocol': 'reviewed_v2'}, status=409)
    assert view(client, cid)['chat'] == old['chat']


def test_upgrade_preflights_full_review_without_resetting_usage(client, app, monkeypatch):
    r, seen = transport(app, monkeypatch)
    cid = direct_chat(client, r)['chat']['id']
    drain(app)
    old = view(client, cid)
    r.settings.direct_policy['daily_attempt_cap'] = len(seen) + 14
    assert not view(client, cid)['review_adoption']['allowed']
    post(client, f'/chats/{cid}/messages', {'text': 'Use the current review.', 'review_protocol': 'reviewed_v2'}, status=429)
    v = view(client, cid)
    assert v['messages'] == old['messages']
    assert v['budget']['attempts'] == old['budget']['attempts'] == 9
    assert v['chat']['protocol'] == old['chat']['protocol']
