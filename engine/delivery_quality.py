"""Deterministic checks for unsupported evidence, not a factual correctness judge."""
import re
VERSION = 'evidence-v4'
REFERENCE = re.compile(r'\b(?:RFC\s*[-:]?\s*\d{3,5}|CVE-\d{4}-\d{4,})\b', re.I)
NUMBER = re.compile(r'\b\d+(?:\.\d+)?\s*(?:%|percent\b|ms\b|seconds?\b|MB\b|GB\b)')
MEASUREMENT = re.compile(r'\b(?:analysis (?:reveals|shows)|(?:profiling|flamegraph|benchmark|measurements?|results?) (?:shows?|reveals?|confirms?|indicates?)|(?:CPU )?time is spent|(?:reduces?|increases?|improves?|decreases?)\b.{0,100}\bby|(?:overhead|latency|CPU usage) will (?:drop|decrease|fall))\b', re.I)
HYPOTHETICAL = re.compile(r'\b(?:for example|hypothetical|illustrative|example threshold|suppose|assume|if measurements|if profiling)\b', re.I)
TEMPLATE = re.compile(r'^(?:completed work on .* successfully|coordination completed\. success criteria mapped|task completed successfully)', re.I)

def job_block_reason(title, job):
    # Reject specific mismatched deliverables, not every mention of these subjects.
    mismatches = [
        (r"compaction (?:algorithms|strategies) (?:in|for) jittered exponential backoff", 'storage compaction requested for retry algorithm'),
        (r"(?:sysctl|socket buffer) settings.{0,100}(?:normalis|normaliz)ing Unicode", 'network settings cannot implement Unicode normalization'),
        (r"binary integrity of (?:a DNS record|pagination by offset)", 'TPM attestation requested for non-binary object'),
        (r"replication safety proofs.{0,80}Vary header", 'consensus proof requested for HTTP cache header'),
    ]
    for pattern, reason in mismatches:
        if re.search(pattern, job, re.I): return reason
    if (re.search(r"\b(?:verify|confirm|check)\b.{0,100}\b(?:current|today.s)\b.{0,100}\b(?:hours|address|phone|prices|availability)\b", title, re.I)
            and re.search(r"official (?:website|source)|call (?:the|each)|date.{0,20}verif", job, re.I)):
        return 'live verification requires a source tool unavailable to this worker'
    # No remote repository inspection or cryptographic execution tools are attached.
    if (re.search(r"^\s*(?:check|inspect)\b.{0,100}(?:GitHub|homepage)", job, re.I)
            and re.search(r"last commit|open issue count|maintenance health", job, re.I)
            and not re.search(r"(?:provided|attached) (?:snapshot|data)|```", job, re.I)):
        return 'current repository evidence unavailable'
    if (re.search(r"^\s*(?:verify|validate)\s+\d+\b.{0,80}Ed25519.{0,60}signatures", job, re.I)
            and not re.search(r"(?:signature|public_key)\s*[:=]|```", job, re.I)):
        return 'signature verification inputs and execution unavailable'
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
