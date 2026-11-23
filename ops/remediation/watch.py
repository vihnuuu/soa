import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ALLOWED = frozenset({'catalog-service', 'lending-service', 'notification-service'})
ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / '.remediation-state.json'
PROM = os.getenv('REMEDIATION_PROMETHEUS_URL', 'http://127.0.0.1:9090')
ALERTS = os.getenv('REMEDIATION_ALERTMANAGER_URL', 'http://127.0.0.1:9093')
ENABLED = os.getenv('REMEDIATION_ENABLE_RESTART', 'false').lower() == 'true'
INTERVAL = max(15, int(os.getenv('REMEDIATION_POLL_SECONDS', '30')))
COOLDOWN = max(600, int(os.getenv('REMEDIATION_COOLDOWN_SECONDS', '600')))


def fetch(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.load(response)


def confirmed_down(service):
    query = urllib.parse.urlencode({'query': f'up{{job="{service}"}}'})
    payload = fetch(f'{PROM}/api/v1/query?{query}')
    if payload.get('status') != 'success':
        return False
    results = payload.get('data', {}).get('result', [])
    return len(results) == 1 and results[0].get('value', [None, None])[1] == '0'


def load_state():
    try:
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_state(state):
    temp = STATE_PATH.with_suffix('.tmp')
    temp.write_text(json.dumps(state, indent=2), encoding='utf-8')
    temp.replace(STATE_PATH)


def check_once():
    state = load_state()
    alerts = fetch(f'{ALERTS}/api/v2/alerts')
    now = time.time()
    for alert in alerts:
        labels = alert.get('labels', {})
        service = labels.get('job') or labels.get('service')
        if labels.get('alertname') != 'NodeDown' or service not in ALLOWED:
            continue
        if alert.get('status', {}).get('state') != 'active':
            continue
        fingerprint = alert.get('fingerprint')
        if not fingerprint:
            continue
        key = f'{service}:{fingerprint}'
        if key in state.get('incidents', {}):
            continue
        if now - state.get('last_restart', {}).get(service, 0) < COOLDOWN:
            continue
        if not confirmed_down(service):
            continue
        cmd = ['docker', 'compose', '-f', 'docker-compose.yml', '-f', 'docker-compose.monitor.yml', 'restart', '--', service]
        if not ENABLED:
            print(f'[DRY RUN] Would restart {service}; alert={fingerprint}', flush=True)
            continue
        print(f'[RESTART] {service}; alert={fingerprint}', flush=True)
        state.setdefault('incidents', {})[key] = now
        state.setdefault('last_restart', {})[service] = now
        save_state(state)
        result = subprocess.run(cmd, cwd=ROOT, timeout=90, check=False, capture_output=True, text=True)
        print(f'[RESULT] {service}: exit={result.returncode} {result.stderr[-500:]}', flush=True)
    return None


def main():
    if not (ROOT / 'docker-compose.yml').exists():
        raise RuntimeError('Cannot locate repository root')
    print(f'Remediation watcher: enabled={ENABLED}, allowlist={sorted(ALLOWED)}', flush=True)
    while True:
        try:
            check_once()
        except Exception as exc:
            print(f'[ERROR] {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
        time.sleep(INTERVAL)


if __name__ == '__main__':
    main()
