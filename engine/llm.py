#!/usr/bin/env python3
"""llm.py — moteurs de rédaction partagés (kibble-bot.py, tg-bot.py, veille-x.py) : CLI claude (compte de l'opérateur, si présent, de l'opérateur, aucune clé API), puis Gemma local.

Cascade réglée dans .env : DRAFT_MODELS=fable,opus,sonnet (modèles Claude essayés dans l'ordre), puis gemma en dernier recours.
Ce qui part chez Anthropic : le prompt (job ou post public + fiche de faits), jamais un secret. La CLI tourne sans outils, sans
connecteurs MCP (~12k tokens de contexte par appel au lieu de ~90k), dans un dossier vide.
Comptabilité : chaque appel Claude est journalisé dans state/claude-usage.jsonl (tokens, coût équivalent API en USD, type job/draft).
Garde-fous : usage_since() sert aux plafonds ; un message de limite d'usage met Claude en pause (state/claude-pause.txt) pour
CLAUDE_PAUSE_MIN minutes (60 par défaut) et prévient l'opérateur sur Telegram ; tout le monde retombe alors sur Gemma."""
from __future__ import annotations
import json, os, re, subprocess, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "state"; CWD = STATE / "llm-cwd"; CWD.mkdir(parents=True, exist_ok=True)
USAGE, PAUSE = STATE / "claude-usage.jsonl", STATE / "claude-pause.txt"
PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
LABELS = {"fable": "Claude Fable 5.1", "opus": "Claude Opus 5", "sonnet": "Claude Sonnet 5", "gemma": "Gemma 27B (local)"}
LIMIT_RE = re.compile(r"usage limit|rate limit|limit reached|hit your|too many requests|quota|overloaded|429", re.I)
VOICE = os.environ.get("FLOPPY_VOICE", "An independent operator runs an autonomous agent on the FLOP/Technocore network; write in a direct, factual, first-person voice.")


class LimitError(RuntimeError):
    """Limite d'usage Claude atteinte (fenêtre de 5 h ou hebdomadaire)."""


def env() -> dict:
    e = dict(os.environ); f = HERE / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1); e[k.strip()] = v.strip().strip('"').strip("'")
    return e


def label(engine: str) -> str: return LABELS.get(engine.replace("claude-", ""), engine)


def paused_until() -> float:
    try: return float(PAUSE.read_text(encoding="utf-8", errors="replace").strip())
    except Exception: return 0.0


def paused() -> bool: return time.time() < paused_until()


def pause(minutes: int, reason: str) -> None:
    PAUSE.write_text(str(time.time() + minutes * 60))
    try:
        import tg; tg.send(f"⏸ <b>Claude en pause {minutes} min</b> (limite d'usage) — tout repasse sur Gemma en attendant.\n<code>{tg.esc(reason[:160])}</code>")
    except Exception: pass


def record_usage(rec: dict) -> None:
    with USAGE.open("a", encoding="utf-8") as f: f.write(json.dumps(rec) + "\n")


def usage_since(seconds: float, kind: str | None = None) -> dict:
    """Somme des appels Claude sur la période : {calls, tokens, cost} (coût = équivalent API en USD rapporté par la CLI)."""
    out = {"calls": 0, "tokens": 0, "cost": 0.0}
    if not USAGE.exists(): return out
    cutoff = time.time() - seconds
    with USAGE.open("rb") as f:
        f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 2_000_000)); data = f.read().decode(errors="replace")
    for line in data.splitlines():
        try: r = json.loads(line)
        except Exception: continue
        if r.get("ts", 0) < cutoff or (kind and r.get("kind") != kind): continue
        out["calls"] += 1; out["tokens"] += r.get("tokens", 0); out["cost"] += r.get("cost", 0.0)
    return out


def claude(prompt: str, model: str = "sonnet", timeout: int = 180, kind: str = "draft") -> str:
    """CLI claude en mode impression, sans outils ni MCP, dossier vide. Journalise l'usage. Exceptions : pause, non connectée, limite, vide."""
    if paused(): raise RuntimeError(f"claude en pause encore {int((paused_until() - time.time()) / 60)} min")
    r = subprocess.run(["claude", "-p", prompt, "--model", model, "--output-format", "json", "--tools", "",
                        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}'],
                       capture_output=True, text=True, timeout=timeout, cwd=CWD, stdin=subprocess.DEVNULL, env={**os.environ, "PATH": PATH})
    try: d = json.loads(r.stdout)
    except Exception: d = {"result": (r.stdout or "").strip(), "is_error": True}
    text = (d.get("result") or "").strip(); err = (r.stderr or "").strip(); u = d.get("usage") or {}
    tokens = sum(int(u.get(k, 0) or 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"))
    if tokens: record_usage({"ts": time.time(), "model": model, "kind": kind, "tokens": tokens, "out": int(u.get("output_tokens", 0) or 0),
                             "cost": float(d.get("total_cost_usd") or 0.0), "error": bool(d.get("is_error"))})
    blob = text + " " + err
    if r.returncode != 0 or d.get("is_error") or not text or "logged in" in blob.lower():
        if LIMIT_RE.search(blob):
            pause(int(env().get("CLAUDE_PAUSE_MIN", "60")), blob[:200]); raise LimitError(f"claude {model}: limite — {blob[:120]}")
        raise RuntimeError(f"claude {model}: code {r.returncode} {(err or text)[:160]}")
    return text


def ollama_generate(body: dict, timeout: int = 300, base: str | None = None) -> dict:
    """POST /api/generate avec think=False (Gemma 4, Qwen… ne dépensent pas leur budget en raisonnement caché) ; repli sans le paramètre
    pour les modèles qui ne le connaissent pas."""
    import urllib.error
    base = base or env().get("OLLAMA_URL", "http://127.0.0.1:11434"); body = dict(body); body.setdefault("think", False)
    for attempt in (1, 2):
        req = urllib.request.Request(f"{base}/api/generate", data=json.dumps(body).encode(), headers={"content-type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if attempt == 1 and "think" in msg.lower() and "think" in body: body.pop("think"); continue
            raise RuntimeError(f"ollama HTTP {e.code}: {msg[:160]}") from None


def gemma(prompt: str, images: list[str] | None = None, num_predict: int = 500, temperature: float = 0.7, timeout: int = 300) -> str:
    e = env(); body = {"model": e.get("OLLAMA_MODEL", "gemma3:27b"), "prompt": prompt, "stream": False,
                       "options": {"temperature": temperature, "num_predict": num_predict}}
    if images: body["images"] = images
    return ollama_generate(body, timeout).get("response", "")


def mlx_generate(prompt: str, system: str | None = None, max_tokens: int = 700, temperature: float = 0.35, timeout: int = 300) -> str:
    """Serveur mlx_lm local (MLX_URL, port 11435) : Adaptateur seulement si MLX_ADAPTER_PATH est configuré. API compatible OpenAI."""
    e = env(); msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": e.get("MLX_MODEL", "floppy"), "messages": msgs, "max_tokens": max_tokens, "temperature": temperature,
            "top_p": 0.95, "repetition_penalty": 1.05, "chat_template_kwargs": {"enable_thinking": False}}   # sans réflexion cachée, mêmes réglages qu'Ollama
    # MLX server 0.31.3 does not inherit the CLI adapter for an explicit model path.
    # Empty configuration intentionally requests the base model; never claim a LoRA is active implicitly.
    adapter = e.get("MLX_ADAPTER_PATH", "").strip()
    if adapter:
        adapter_dir = Path(adapter).expanduser()
        if not (adapter_dir / "adapters.safetensors").is_file() or not (adapter_dir / "adapter_config.json").is_file():
            raise RuntimeError("Configured MLX adapter is incomplete; refusing silent base fallback")
        body["adapters"] = str(adapter_dir.resolve())
    req = urllib.request.Request(f"{e.get('MLX_URL', 'http://127.0.0.1:11435')}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r: d = json.load(r)
    return (d.get("choices") or [{}])[0].get("message", {}).get("content", "")


FLOPPY_SYSTEM = None
def floppy_system() -> str:
    """Consigne système gravée dans floppy-gemma4 (Modelfile), réutilisée pour le modèle MLX affiné."""
    global FLOPPY_SYSTEM
    if FLOPPY_SYSTEM is None:
        try: FLOPPY_SYSTEM = (HERE / "state" / "Modelfile.floppy").read_text(encoding="utf-8", errors="replace").split('SYSTEM """')[1].split('"""')[0].strip()
        except Exception: FLOPPY_SYSTEM = ""
    return FLOPPY_SYSTEM


def generate(prompt: str, models: list[str] | None = None, gemma_kwargs: dict | None = None, kind: str = "draft") -> tuple[str, str]:
    """Essaie les modèles Claude dans l'ordre (sauf pause), puis Gemma ; renvoie (texte, moteur). Exception si tout échoue."""
    e = env(); models = models if models is not None else [m.strip() for m in e.get("DRAFT_MODELS", "fable,opus,sonnet").split(",") if m.strip()]
    errors = []
    for m in ([] if paused() else models):
        try: return claude(prompt, m, kind=kind), f"claude-{m}"
        except LimitError as ex: errors.append(str(ex)); break
        except Exception as ex: errors.append(f"{m}: {ex}")
    try: return gemma(prompt, **(gemma_kwargs or {})), "gemma"
    except Exception as ex: errors.append(f"gemma: {ex}")
    raise RuntimeError(" ; ".join(errors)[:400])
