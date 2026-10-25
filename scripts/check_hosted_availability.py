"""Read-only cloud checks, run by GitHub Actions without local secrets or inference."""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PRODUCTION_ORIGIN = 'https://web-mu-weld-26.vercel.app'
JUDGING_END = datetime(2026, 12, 15, 20, tzinfo=UTC)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def public_report(body):
    return {key: body.get(key) for key in ('status', 'checks', 'heartbeat_age_seconds',
                                         'worker_observation', 'warnings', 'checked_at')}


def scheduled_window_open(at):
    return at <= JUDGING_END


def check(origin, *, attempts=3, pause=time.sleep, opener=None):
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('Use a public HTTPS origin without credentials, path or query')
    opener = opener or build_opener(NoRedirect)
    last = {'status': 'unavailable', 'error': 'not_checked'}
    for attempt in range(attempts):
        try:
            request = Request(origin.rstrip('/') + '/api/operations/status', headers={
                'Accept': 'application/json', 'User-Agent': 'CouncilAI-availability-check/1',
            })
            with opener.open(request, timeout=35) as response:
                data = response.read(65537)
                if len(data) > 65536:
                    raise ValueError('Oversized health response')
                body = json.loads(data)
                if not isinstance(body, dict) or not isinstance(body.get('checks'), dict):
                    raise ValueError('Invalid health response')
                required = {'frontend': 'ready', 'database': 'ready', 'worker': 'ready', 'cloud_ledger': 'initialized'}
                good = (body.get('monitoring_version') == 1 and body.get('status') == 'ready'
                        and body.get('inference_dispatched') is False
                        and all(body.get('checks', {}).get(key) == value for key, value in required.items())
                        and body.get('checks', {}).get('file_mirror') in ('caught_up', 'pending'))
                # The public health payload contains no history or financial records.
                last = public_report(body)
                if good:
                    return True, last
        except HTTPError as error:
            last = {'status': 'unavailable', 'http_status': error.code}
            try:
                body = json.loads(error.read(65536))
                if isinstance(body, dict) and body.get('monitoring_version') == 1:
                    last.update(public_report(body))
            except (ValueError, TypeError, OSError):
                pass
        except (URLError, OSError, ValueError, TypeError):
            last = {'status': 'unavailable', 'error': 'health_response_unavailable'}
        if attempt < attempts - 1:
            pause(20)
    return False, last


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', default=PRODUCTION_ORIGIN)
    parser.add_argument('--scheduled', action='store_true')
    parser.add_argument('--report')
    args = parser.parse_args()
    if args.scheduled and not scheduled_window_open(datetime.now(UTC)):
        print(json.dumps({'status': 'judging_window_ended', 'requests_made': 0}))
        return 0
    good, report = check(args.origin)
    report.update(passed=good, inference_requests=0, scheduled=args.scheduled)
    print(json.dumps(report, indent=2))
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write('# Council availability\n\n')
            stream.write('Passed. No model or search requests were made.\n\n' if good else
                         'Failed. Check the Vercel worker/quotas and Supabase project status. No paid request was retried.\n\n')
            stream.write('```json\n' + json.dumps(report, indent=2) + '\n```\n')
    return 0 if good else 1


if __name__ == '__main__':
    raise SystemExit(main())
