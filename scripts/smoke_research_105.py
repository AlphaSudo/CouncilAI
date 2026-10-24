"""Explicit live pilot: one Basic search, one public fetch, no automatic model run."""

import json
import uuid
from pathlib import Path
from fastapi.testclient import TestClient
from zerowall.api import create_app
from zerowall.settings import Settings


def main():
    root = Path(__file__).resolve().parents[1]
    settings = Settings(root/'data/research-live-1.05')
    app = create_app(settings, run_worker=False)
    r = app.state.research
    report = {'scope': 'Live search/fetch/library integration only; no model inference requested.', 'model_calls': 0, 'steps': []}
    with TestClient(app) as client:
        client.headers['X-ZeroWall-Director'] = '1'
        assert client.post('/api/session', json={'token': settings.director_token}).is_success
        def post(path, body):
            response = client.post('/api'+path, json=body, headers={'Idempotency-Key': str(uuid.uuid4())})
            if not response.is_success:
                report['steps'].append({'route': path, 'status': response.status_code, 'detail': response.json().get('detail')})
                raise RuntimeError('Live pilot stopped; see sanitized report')
            return response.json()
        try:
            initial = post('/chats', {'prompt': 'Bounded search and source-library compatibility pilot.', 'provider': 'direct_council', 'models': list(r.direct_provider.entries()), 'search_web': True, 'defer_start': True})
            cid = initial['chat']['id']
            report['chat_id'] = cid
            action = {'name': 'web_search', 'arguments': {'query': 'Tavily Basic Search API credits', 'domains': ['docs.tavily.com'], 'limit': 2}}
            result = post(f'/chats/{cid}/research/tools', action)
            report['steps'].append({'name': 'web_search', 'ok': True, 'result_count': len(result['results']), 'credit_reservation': result.get('reserved_credits'), 'reported_usage': result.get('usage'), 'raw_retained': result.get('retained_result', {}).get('raw_retained')})
            reused = post(f'/chats/{cid}/research/tools', action)
            report['steps'].append({'name': 'repeat_search', 'reused': reused.get('reused')})
            fetched = post(f'/chats/{cid}/research/tools', {'name': 'web_fetch', 'arguments': {'url': 'https://docs.tavily.com/documentation/api-credits'}})
            version = fetched['version']
            report['steps'].append({'name': 'web_fetch', 'ok': True, 'mime': version['mime'], 'coverage': version['coverage'], 'parser': version['parser'], 'body_bytes': fetched['raw_bytes']})
            passage = post(f'/chats/{cid}/research/tools', {'name': 'library_read', 'arguments': {'version_id': version['id']}})
            report['steps'].append({'name': 'library_read', 'ok': bool(passage['text']), 'bytes': passage['receipt']['bytes'], 'truncated': passage['receipt']['truncated']})
            usage = client.get(f'/api/chats/{cid}/usage').json()
            report.update(model_calls=usage['total']['attempts'], shared_research=usage['shared_research'], status='passed')
        except Exception as error:
            report.update(status='partial_or_failed', error_type=type(error).__name__)
    output = root/'docs/validation/research-live-1.05.json'
    output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
