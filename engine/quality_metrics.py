"""Conservative attribution: one latest vote per attestor/job, only after our delivery.
A job with any known competing result is ambiguous; its votes stay visible separately.
These are attestation counts, not a percentage of all deliveries rejected.
"""
import json
from pathlib import Path

def read_rows(path):
    if not Path(path).exists(): return []
    rows = []
    for line in Path(path).read_text(errors='replace').splitlines():
        try: rows.append(json.loads(line))
        except (ValueError, TypeError): pass
    return rows

def attributed_votes(rows, deliveries):
    own = {r['job_id']: r for r in deliveries if r.get('seq') and r.get('engine')}
    ambiguous_jobs = {r.get('job_id') for r in rows if r.get('foreign')}
    latest = {}
    for r in rows:
        d = own.get(r.get('job_id'))
        if not d or r.get('verdict') not in ('useful', 'not') or not r.get('attestor'): continue
        if r.get('ts', 0) < d.get('ts', 0): continue
        key = (r['job_id'], r['attestor'])
        if r.get('ts', 0) >= latest.get(key, {}).get('ts', 0):
            latest[key] = {**r, 'engine': d['engine'], 'ambiguous': r['job_id'] in ambiguous_jobs}
    return list(latest.values())

def snapshot(state):
    state = Path(state)
    return attributed_votes(read_rows(state/'attest-received.jsonl'), read_rows(state/'dataset.jsonl'))
