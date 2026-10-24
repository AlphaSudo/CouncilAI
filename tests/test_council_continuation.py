"""Transport-level checks for ongoing chats, honest attribution and bounded recovery."""

import json

import pytest
from zerowall.free_errors import FreeProviderError

from test_council_chat import drain
from test_direct_provider import direct_chat, transport
from test_review_resilience import force_due, scripted_transport
from test_workflow import post


def view(client, cid):
    return client.get('/api/chats/' + cid).json()


def finish(client, app, cid):
    for _ in range(8):
        drain(app)
        v = view(client, cid)
        if v['chat']['status'] != 'waiting':
            return v
        assert not app.state.executor.run_once()
        force_due(app.state.research)
    raise AssertionError('Recovery did not terminate')


def test_direct_followups_keep_chat_and_all_calls_beyond_old_lifetime_caps(client, app, monkeypatch):
    r, seen = transport(app, monkeypatch)
    cid = direct_chat(client, r)['chat']['id']
    drain(app)
    original = view(client, cid)['messages']
    for n in range(7):
        post(client, f'/chats/{cid}/messages', {'text': f'Refine engineering option {n + 1}.'})
        drain(app)
        v = view(client, cid)
        assert v['chat']['status'] == 'completed', v['chat'].get('error')
        assert v['messages'][:len(original)] == original
        assert v['budget']['attempts'] == 9 + 5 * (n + 1)
        assert v['chat']['id'] == cid
        assert v['continuation']['allowed']
        assert v['messages'][-1]['provider'] == 'gemini'
    assert len(seen) == 44
    assert len([m for m in v['messages'] if m['phase'] == 'opening']) == 4
    assert v['chat']['max_rounds'] == 8
    with r.store.tx() as c:
        assert len(r.store.list(c, 'chat_allowance', v['chat']['mission_id'])) == 8


def test_daily_limit_keeps_chat_and_idempotent_followup_never_grants_twice(client, app, monkeypatch):
    r, seen = transport(app, monkeypatch)
    cid = direct_chat(client, r)['chat']['id']
    drain(app)
    body = {'text': 'Compare five engineering approaches.'}
    a = post(client, f'/chats/{cid}/messages', body, key='same-followup')
    b = post(client, f'/chats/{cid}/messages', body, key='same-followup')
    assert a == b
    drain(app)
    before = view(client, cid)
    r.settings.direct_policy['daily_attempt_cap'] = len(seen) + 7
    assert not view(client, cid)['continuation']['allowed']
    post(client, f'/chats/{cid}/messages', {'text': 'One more comparison.'}, status=429)
    after = view(client, cid)
    assert after['messages'] == before['messages']
    assert after['budget']['attempts'] == 14
    with r.store.tx() as c:
        assert len(r.store.list(c, 'chat_allowance', before['chat']['mission_id'])) == 2


@pytest.mark.parametrize('fault', [413, 429, 503, 'length'])
def test_groq_switches_after_exactly_two_sent_failures_and_discloses_model(client, app, monkeypatch, fault):
    def fail_primary(out):
        if out.get('model') != 'openai/gpt-oss-120b':
            return
        if fault == 'length':
            out['choices'][0]['finish_reason'] = 'length'
        else:
            out['error'] = {'code': fault, 'message': 'Synthetic unavailable primary'}
    r, seen = transport(app, monkeypatch, mutate=fail_primary)
    cid = direct_chat(client, r)['chat']['id']
    v = finish(client, app, cid)
    assert v['chat']['status'] == 'completed', v['chat'].get('error')
    assert sum(b.get('model') == 'openai/gpt-oss-120b' for _, b in seen) == 2
    replies = [m for m in v['messages'] if m.get('provider') == 'groq']
    assert len(replies) == 2
    assert all(m['actual_model'] == 'openai/gpt-oss-20b' for m in replies)
    assert all(m['replacement_for'] == 'groq::openai/gpt-oss-120b' for m in replies)
    assert all('20B' in m['name'] for m in replies)
    assert v['budget']['attempts'] == 11
    assert v['chat']['participants'][-1]['actual_model'] == 'openai/gpt-oss-120b'
    assert v['messages'][-1]['provider'] == 'gemini'
    if fault == 'length':
        primary = [b for _, b in seen if b.get('model') == 'openai/gpt-oss-120b']
        assert [b['max_tokens'] for b in primary] == [3072, 4096]


@pytest.mark.parametrize('status', [401, 402, 403])
def test_auth_or_billing_errors_never_trigger_model_substitution(client, app, monkeypatch, status):
    def rejected(out):
        if out.get('model') == 'openai/gpt-oss-120b':
            out['error'] = {'code': status}
    r, seen = transport(app, monkeypatch, mutate=rejected)
    cid = direct_chat(client, r)['chat']['id']
    v = finish(client, app, cid)
    assert not v['chat'].get('model_overrides')
    assert not any(b.get('model') == 'openai/gpt-oss-20b' for _, b in seen)


@pytest.mark.parametrize('protocol', ['reviewed_v1', 'reviewed_v2'])
def test_review_continuation_preserves_published_hashes_and_full_accounting(client, app, monkeypatch, protocol):
    r, seen = scripted_transport(app, monkeypatch)
    v = post(client, '/chats', {
        'prompt': 'Compare generic software approaches with explicit uncertainty.',
        'provider': 'direct_council', 'models': list(r.direct_provider.entries()),
        'mode': 'reviewed', 'review_protocol': protocol, 'max_rounds': 1,
    })
    cid = v['chat']['id']
    drain(app)
    first = view(client, cid)
    assert first['chat']['status'] == 'completed', first['chat'].get('error')
    with r.store.tx() as c:
        publications = r.store.list(c, 'review_publication', first['chat']['mission_id'])
    post(client, f'/chats/{cid}/messages', {'text': 'Now compare the execution tradeoffs.'})
    drain(app)
    v = view(client, cid)
    assert v['chat']['status'] == 'completed', v['chat'].get('error')
    assert v['budget']['attempts'] == 24
    assert v['messages'][:len(first['messages'])] == first['messages']
    with r.store.tx() as c:
        assert r.store.list(c, 'review_publication', first['chat']['mission_id'])[:len(publications)] == publications
    assert v['review']['cycle'] == 2


def test_groq_context_is_bounded_and_latest_request_is_not_lost(client, app, monkeypatch):
    r, seen = transport(app, monkeypatch)
    cid = direct_chat(client, r)['chat']['id']
    drain(app)
    note = 'Please rank the best five engineering approaches and their next test.'
    post(client, f'/chats/{cid}/messages', {'text': note})
    drain(app)
    prompts = [json.loads(b['messages'][1]['content']) for _, b in seen if b.get('model') == 'openai/gpt-oss-120b']
    assert prompts[-1]['director_notes'][-1]['text'] == note
    assert 'excerpts' in prompts[-1]['context_policy']
    assert all(len(json.dumps(p, ensure_ascii=False).encode()) <= 10500 for p in prompts)
    assert all(b['max_tokens'] == 3072 for _, b in seen if b.get('model') == 'openai/gpt-oss-120b')


def test_saved_primary_failures_trigger_fallback_on_followup_without_rewriting_old_replies(client, app, monkeypatch):
    failed = []
    def reject(out):
        if failed and out.get('model') == 'openai/gpt-oss-120b':
            out['error'] = {'code': 413}
    r, seen = transport(app, monkeypatch, mutate=reject)
    cid = direct_chat(client, r)['chat']['id']
    drain(app)
    old = view(client, cid)
    failed.append(True)
    for _ in range(2):
        with pytest.raises(FreeProviderError):
            r.direct_provider.call(old['chat']['mission_id'], 'A retained failed request.', model='groq::openai/gpt-oss-120b', purpose=f'chat:{cid}:retained_failure')
    primary_count = sum(b.get('model') == 'openai/gpt-oss-120b' for _, b in seen)
    post(client, f'/chats/{cid}/messages', {'text': 'Continue with five engineering approaches.'})
    drain(app)
    v = view(client, cid)
    assert v['chat']['status'] == 'completed', v['chat'].get('error')
    assert sum(b.get('model') == 'openai/gpt-oss-120b' for _, b in seen) == primary_count
    assert v['messages'][:len(old['messages'])] == old['messages']
    assert v['budget']['attempts'] == 16
    assert any(m.get('actual_model') == 'openai/gpt-oss-20b' for m in v['messages'])


def test_failed_alternative_is_attributed_to_actual_model_and_phase(client, app, monkeypatch):
    def failure(out):
        if out.get('model') == 'openai/gpt-oss-120b':
            out['error'] = {'code': 503}
        elif out.get('model') == 'openai/gpt-oss-20b':
            out['choices'][0]['finish_reason'] = 'length'
    r, seen = transport(app, monkeypatch, mutate=failure)
    cid = direct_chat(client, r)['chat']['id']
    v = finish(client, app, cid)
    assert v['chat']['status'] == 'completed'
    assert v['messages'][-1]['partial']
    notice = v['participation_notices'][0]
    assert notice['name'] == 'Groq · GPT OSS 20B'
    assert notice['model'] == 'groq::openai/gpt-oss-20b'
    assert notice['actual_model'] == 'openai/gpt-oss-20b'
    assert notice['phase'] == 'opening'
    assert notice['call_id']
    assert v['budget']['attempts'] == len(seen) <= 20


def test_quoted_schema_words_do_not_turn_discussion_into_structured_output(app):
    provider = app.state.research.direct_provider
    prompt = json.dumps({'original_question': 'Explain the words "response_schema" in plain English.'})
    for entry in provider.entries().values():
        _, body = provider.request(entry, prompt, 512)
        assert 'response_format' not in body
        assert body.get('generationConfig', {}).get('responseMimeType') is None
