"""Deterministic checks for unsupported evidence, not a factual correctness judge."""
import re
VERSION = 'evidence-v6'
REFERENCE = re.compile(r'\b(?:RFC\s*[-:]?\s*\d{3,5}|CVE-\d{4}-\d{4,})\b', re.I)
NUMBER = re.compile(r'\b\d+(?:\.\d+)?\s*(?:%|percent\b|ms\b|seconds?\b|MB\b|GB\b)')
MEASUREMENT = re.compile(r'\b(?:analysis (?:reveals|shows)|(?:profiling|flamegraph|benchmark|measurements?|results?) (?:shows?|reveals?|confirms?|indicates?)|(?:CPU )?time is spent|(?:reduces?|increases?|improves?|decreases?)\b.{0,100}\bby|(?:overhead|latency|CPU usage) will (?:drop|decrease|fall))\b', re.I)
HYPOTHETICAL = re.compile(r'\b(?:for example|hypothetical|illustrative|example threshold|suppose|assume|if measurements|if profiling)\b', re.I)
TEMPLATE = re.compile(r'^(?:completed work on .* successfully|coordination completed\. success criteria mapped|task completed successfully)', re.I)

def job_block_reason(title, job):
    bounds = word_bounds(job)
    if bounds and bounds[0] > 350:
        return 'requested length exceeds conservative delivery budget'
    if re.search(r'(?:at least|minimum of) (?:three|3).{0,40}(?:credible )?(?:citations|sources)', job, re.I) and not re.search(r'https?://|provided sources|attached sources', job, re.I):
        return 'verifiable citations require source material unavailable to worker'
    if re.search(r'SSTable|(?:leveled|size-tiered|FIFO) compaction', job, re.I) and re.search(r'monorepo build|build triggered on every commit', job, re.I) and not re.search(r'RocksDB|LSM.tree|storage engine', job, re.I):
        return 'storage compaction premise unsupported for build pipeline'
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
    issues=format_issues(job, answer)
    if re.search(r'allowed (?:directory|root)|path traversal|outside.{0,30}directory', job, re.I) and re.search(r'starts with|startswith|(?:directory|path) prefix', answer, re.I) and not re.search(r'not sufficient|insufficient|do not|never use|not use|instead of', answer, re.I):
        issues.append('unsafe path containment: use path components and handle symlinks/races, not string prefix')
    refs={re.sub(r'\s+', '',s).lower() for s in REFERENCE.findall(job)}
    if any(re.sub(r'\s+', '',s).lower() not in refs for s in REFERENCE.findall(answer)):
        issues.append('reference not supplied or verified by a source tool')
    if TEMPLATE.search(answer.strip()): issues.append('empty completion template')
    for sentence in re.split(r'(?<=[.!?])\s+', answer):
        if MEASUREMENT.search(sentence) and not HYPOTHETICAL.search(sentence):
            if any(n not in job for n in NUMBER.findall(sentence)):
                issues.append('measured or guaranteed figures without supplied evidence');break
    return issues


def word_bounds(job):
    match = re.search(r"\b(\d+)\s*[–-]\s*(\d+)[ -]+words?\b", job, re.I)
    if match:
        low, high = map(int, match.groups())
        if 0 < low <= high: return low, high
    return None



def word_maximum(job):
    """Explicit English word caps; strict 'under N' means at most N-1.

    This parses task text, not arbitrary semantic instructions or quoted examples.
    Counts use the same whitespace convention as format_issues.
    """
    patterns = [
        (r"\b(?:at most|no more than|maximum(?: of)?)\s+(\d+)\s+words?\b", 0),
        (r"\b(?:under|fewer than|less than)\s+(\d+)\s+words?\b", -1),
    ]
    limits = [int(m.group(1)) + offset for pattern, offset in patterns
              for m in re.finditer(pattern, job, re.I)]
    return min(limits) if limits else None


def one_sentence(job):
    return bool(re.search(r"\b(?:exactly one|one|a single) sentence\b", job, re.I))


def format_issues(job, answer):
    issues = []
    count = re.match(r"\s*Word count:\s*(\d+)\s*[.\n:]?\s*", answer, re.I)
    body = answer[count.end():] if count else answer
    words = len(body.split())
    if count and int(count.group(1)) != words: issues.append('incorrect declared word count')
    bounds = word_bounds(job)
    if bounds and not bounds[0] <= words <= bounds[1]: issues.append('explicit word range not met')
    maximum = word_maximum(job)
    if maximum is not None and words > maximum:
        issues.append('explicit word maximum exceeded')
    if one_sentence(job):
        # Common abbreviations are not sentence boundaries.
        plain = re.sub(r"\b(?:e\.g|i\.e|Dr|Mr|Ms|vs)\.", 'abbrev', body)
        if len(re.split(r"[.!?]+\s+(?=[A-Z])", plain.strip().rstrip('.!?'))) != 1:
            issues.append('one sentence requested')
    return issues


def length_instruction(job):
    instructions = []
    bounds = word_bounds(job)
    maximum = word_maximum(job)
    if bounds:
        instructions.append(f'Write {bounds[0]}–{bounds[1]} words, counted by whitespace; count accurately if requested.')
    if maximum is not None:
        instructions.append(f'Use at most {maximum} words, counted by whitespace.')
    if one_sentence(job):
        instructions.append('Write exactly one sentence.')
    return ' '.join(instructions) or 'Be concise and complete; do not pad the answer to a target length.'
