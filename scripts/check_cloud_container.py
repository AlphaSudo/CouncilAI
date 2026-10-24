"""Run isolated Postgres/storage integration tests inside the built Linux image.

Requires a disposable local Postgres on 127.0.0.1:55432 with the synthetic
local-test-only password. It must contain NO application data. The fixtures clear
the zerowall schema. No production environment file or provider key is loaded.
Podman host networking refers to its Linux VM, not the developer web server.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='localhost/zerowall:vercel-check')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    command = ['podman', 'run', '--rm', '--network', 'host', '--memory', '1g',
        '--env', 'ZEROWALL_MODE=local', '--env', 'ZEROWALL_DATA_DIR=/tmp/zerowall',
        '--env', 'ZEROWALL_TEST_DATABASE_URL=postgresql://postgres:local-test-only@127.0.0.1:55432/postgres',
        '--volume', str(root / 'tests') + ':/app/tests:ro',
        '--volume', str(root / 'docs') + ':/app/docs:ro',
        '--entrypoint', 'python', args.image, '-m', 'pytest',
        'tests/test_cloud_storage.py', 'tests/test_cloud_council.py',
        'tests/test_cloud_migration.py', 'tests/test_cloud_configuration.py',
        'tests/test_cloud_responses.py',
        '-q', '--tb=short', '-p', 'no:cacheprovider']
    result = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)
    print(result.stdout)
    if result.returncode:
        raise SystemExit('Container integration check failed; no production credentials were used')
    sources = sorted(p.relative_to(root).as_posix() for p in (root / 'src/zerowall').glob('*.py'))
    proof = subprocess.run(['podman', 'run', '--rm', '--entrypoint', 'python', args.image, '-c',
        'import hashlib,json,pathlib; p=pathlib.Path("/app"); print(json.dumps({n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ' + repr(sources) + '}))'],
        capture_output=True, text=True, timeout=30, check=True)
    hashes = json.loads(proof.stdout)
    if any(hashlib.sha256((root / name).read_bytes()).hexdigest() != sha for name, sha in hashes.items()):
        raise SystemExit('The image differs from current source; rebuild and rerun')
    image = subprocess.run(['podman', 'image', 'inspect', '--format', '{{.Id}}', args.image],
        capture_output=True, text=True, timeout=30, check=True).stdout.strip()
    report = {'image': image, 'memory_limit_mib': 1024, 'result': result.stdout.strip(),
        'source_sha256': hashes, 'paid_inference_calls': 0,
        'database': 'real temporary local Postgres 17', 'storage_http': 'transport double',
        'public_deployment_verified': False, 'real_supabase_bucket_verified': False}
    output = root / 'docs/validation/cloud-container.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Source hashes match; wrote docs/validation/cloud-container.json')


if __name__ == '__main__':
    main()
