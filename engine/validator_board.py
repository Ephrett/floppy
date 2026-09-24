"""Read-only board reader; one attempt, finite socket timeout and body cap."""
import json
import urllib.request

MAX_BYTES = 8 * 1024 * 1024


class BoardUnavailable(ValueError):
    pass


def read_jobs(url, opener=None):
    opener = opener or urllib.request.urlopen
    try:
        with opener(url, timeout=15) as response:
            if response.status != 200:
                raise BoardUnavailable('HTTP status %s' % response.status)
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise BoardUnavailable('response exceeds size limit')
        payload = json.loads(raw)
    except BoardUnavailable:
        raise
    except Exception as exc:
        # Do not include response bodies, URLs or exception payloads in logs.
        raise BoardUnavailable(type(exc).__name__) from None
    if not isinstance(payload, dict) or payload.get('ok') is False or payload.get('error'):
        raise BoardUnavailable('invalid board envelope')
    jobs = payload.get('jobs')
    if not isinstance(jobs, list) or any(not isinstance(job, dict) for job in jobs):
        raise BoardUnavailable('invalid jobs list')
    fields = ('job_id', 'worker_did', 'poster_did', 'status', 'result_hash', 'result', 'title', 'body')
    if any(not isinstance(job[key], str) for job in jobs for key in fields if key in job):
        raise BoardUnavailable('invalid job field type')
    return jobs
