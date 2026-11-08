import json
from pathlib import Path

p = Path('reports/ty/autonomy_queue.json')
d = json.loads(p.read_text(encoding='utf-8'))
items = {i['id']: i for i in d['items']}

a9 = items.get('M0.3b-token-meter', {'id': 'M0.3b-token-meter'})
a9.update({
    "status": "done",
    "commit": "d82a5b3f",
    "verification": ("python -m pytest -q Northstar_backend/test_token_meter.py -> 17 passed; "
                     "live: --session ses_e4d0675a2ffe4yNWug2cO5BRRe -> 180,803 tokens while "
                     "tys_runner status recorded 2,162 today, which is the size of the soft-cap hole"),
    "evidence": ["reports/ty/A9_token_meter.md", "tools/token_meter.py"],
})
items['M0.3b-token-meter'] = a9

items['A9b-wire-meter'] = {
    "id": "A9b-wire-meter", "kind": "automation", "priority": 1185, "status": "pending",
    "title": "Wire the token meter into the launcher so the daily cap is enforced, not estimated in prose",
    "next": ("After each cycle, call token_meter.estimate_session(<worker session id>) and pass it as "
             "result['tokens'] to tys_runner.complete; fall back to estimate_payload when the store is "
             "unavailable and record which source was used."),
    "write_paths": ["tools/tys_launcher.py"],
    "acceptance_commands": [["python", "-m", "pytest", "-q", "test_tys_launcher.py"]],
    "depends_on": ["M0.3b-token-meter", "M2-worker-lane"],
}

d['items'] = sorted(items.values(), key=lambda i: (-(i.get('priority') or 0), i['id']))
d['updated'] = '2026-11-06T11:00:00Z'
p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('A9 done; next:', [i['id'] for i in d['items'] if i['status'] == 'pending'][:3])
