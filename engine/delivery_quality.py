"""Deterministic checks for unsupported evidence, not a factual correctness judge."""
import re
VERSION = 'evidence-v1'
REFERENCE = re.compile(r'\b(?:RFC\s*[-:]?\s*\d{3,5}|CVE-\d{4}-\d{4,})\b', re.I)
NUMBER = re.compile(r'\b\d+(?:\.\d+)?\s*(?:%|ms\b|seconds?\b|MB\b|GB\b)')
MEASUREMENT = re.compile(r'\b(?:analysis (?:reveals|shows)|(?:profiling|flamegraph|benchmark|measurements?|results?) (?:shows?|reveals?|confirms?|indicates?)|(?:CPU )?time is spent|(?:overhead|latency|CPU usage) will (?:drop|decrease|fall))\b', re.I)
HYPOTHETICAL = re.compile(r'\b(?:for example|hypothetical|illustrative|example threshold|suppose|assume|if measurements|if profiling)\b', re.I)
TEMPLATE = re.compile(r'^(?:completed work on .* successfully|coordination completed\. success criteria mapped|task completed successfully)', re.I)

def job_block_reason(title, job):
    # Our text engine has no flamegraph, code execution or profiling tool attached.
    if re.search(r'\b(?:analy[sz]e|isolat\w*|identify)\b.*\b(?:using|from) (?:the |a )?flamegraphs?\b', job, re.I) and not re.search(r'(?:\b\w+;\w+;\w+\s+\d+|```|samples\s*[:=]\s*\d+)', job, re.I):
        return 'profiling evidence missing'
    return None

def output_issues(job, answer):
    issues=[]
    refs={re.sub(r'\s+', '',s).lower() for s in REFERENCE.findall(job)}
    if any(re.sub(r'\s+', '',s).lower() not in refs for s in REFERENCE.findall(answer)):
        issues.append('reference not supplied or verified by a source tool')
    if TEMPLATE.search(answer.strip()): issues.append('empty completion template')
    for sentence in re.split(r'(?<=[.!?])\s+', answer):
        if MEASUREMENT.search(sentence) and not HYPOTHETICAL.search(sentence):
            if any(n not in job for n in NUMBER.findall(sentence)):
                issues.append('measured or guaranteed figures without supplied evidence');break
    return issues
