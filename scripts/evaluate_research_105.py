"""Offline, controlled retrieval measurements; no model/search API is called."""

from pathlib import Path
import hashlib
import json
import statistics
import tempfile
import time
import logging
from zerowall.api import create_app
from zerowall.contracts import ChatCreate
from zerowall.settings import Settings


def evaluate():
    root = Path(__file__).resolve().parents[1]
    corpus_path = root / 'docs/evaluation/research-corpus-1.05.json'
    corpus = json.loads(corpus_path.read_text(encoding='utf-8'))
    measurements = []
    with tempfile.TemporaryDirectory() as temporary:
        settings = Settings(temporary)
        settings.direct_keys, settings.api_key, settings.tavily_api_key = {}, '', ''
        settings.direct_free_confirmed = False
        r = create_app(settings, run_worker=False).state.research
        for case in corpus['cases']:
            with r.store.tx() as c:
                chat = r.chat.create(c, ChatCreate(prompt=case['query'], models=['demo/analyst', 'demo/critic'], defer_start=True))['chat']
            filler = 'Background material unrelated to the question.\n' * 500
            raw = (filler + '\n# Relevant passage\n' + case['passage'] + '\n' + filler).encode()
            version = r.library.ingest(chat, raw, title=case['title'], mime='text/markdown')
            times = []
            for _ in range(30):
                start = time.perf_counter()
                with r.store.tx() as c:
                    result = r.library.search(c, chat, case['query'])
                times.append((time.perf_counter()-start)*1000)
            with r.store.tx() as c:
                snapshot = r.library.snapshot(c, chat, 'control')
                turn = {'phase': 'opening', 'key': 'control', 'participant': chat['participants'][0]}
                mandatory = {'question': case['query'], 'constraint': 'Preserve the exact qualifier and unresolved obligations.'}
                prompt, _, pack = r.context_packs.compile(c, chat, turn, json.dumps(mandatory), snapshot)
                selected = ''.join(r.store.get(c, item['chunk_id'], 'source_chunk')['text'] for item in pack['passages'])
            assert case['must_retain'] in selected
            assert json.loads(prompt) == mandatory
            ordered = sorted(times)
            measurements.append({'case': case['id'], 'source_version': version['id'], 'full_source_bytes': len(raw),
                                 'selected_source_bytes': len(selected.encode()), 'required_qualifier_retained': True,
                                 'mandatory_context_identical': True, 'lookup_runs': len(times), 'lookup_p50_ms': statistics.median(times),
                                 'lookup_p95_ms': ordered[int(.95*(len(times)-1))], 'provider_measured_tokens': None})
        for name, logger in logging.Logger.manager.loggerDict.items():
            if str(settings.data) in name and isinstance(logger, logging.Logger):
                for handler in logger.handlers[:]:
                    handler.close()
                    logger.removeHandler(handler)
    report = {'version': 'research-evaluation/1', 'corpus_sha256': hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
              'cases': measurements, 'network_calls': 0, 'model_calls': 0,
              'comparison_scope': 'Full source bytes versus selected exact source bytes under identical evidence and mandatory task. No model output, latency or token-saving superiority is asserted.',
              'independent_quality_status': 'pending'}
    output = root / 'docs/validation/research-efficiency-1.05.json'
    output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    print(json.dumps(evaluate(), indent=2))
