# Worker simulé (mode FLOPPY_SIMULATE=1) : écrit des lignes de journal au format de kibble-bot sans toucher au tableau.
import random, time, json
from pathlib import Path
S = Path(__file__).resolve().parent / "state"; S.mkdir(exist_ok=True)
titles = ["Explain how TCP congestion control reacts to packet loss", "Review a structured logging schema", "Compare Bloom and Cuckoo filters", "Design a backup drill for a log shipper"]
while True:
    jid = "k" + "".join(random.choice("0123456789abcdef") for _ in range(10)); t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with (S / "bot.log").open("a", encoding="utf-8") as f:
        f.write(f"[{t}] CLAIM {jid} job_seq=1 claim_seq=2 [ollama] | {random.choice(titles)}\n"); f.write(f"[{t}] RESULT {jid} seq=3 ({random.randint(600, 1800)} caractères, moteur ollama)\n")
    if random.random() < 0.3:
        with (S / "attest-received.jsonl").open("a", encoding="utf-8") as f: f.write(json.dumps({"ts": time.time(), "job_id": jid, "verdict": "useful" if random.random() < 0.85 else "not", "attestor": "did:key:z6Mk" + "".join(random.choice("abcdefghij") for _ in range(8)), "engine": "ollama", "cat": "explain"}) + "\n")
    time.sleep(random.uniform(8, 20))
