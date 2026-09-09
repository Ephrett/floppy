#!/usr/bin/env python3
"""FLOPPY — l'app du worker kibble/Technocore pour tout le monde : analyse la machine, installe le moteur (Ollama + modèle du palier),
crée l'identité en local (seed jamais transmise), bouton Play, et suit le travail (cadence, attestations, score du tableau).
Serveur local en lecture/écriture pour l'interface (127.0.0.1 par défaut). Les fichiers du client vivent dans FLOPPY_HOME.
Aucun secret n'est renvoyé par l'API : la seed n'est jamais lue par l'interface, le jeton Telegram jamais réaffiché."""
from __future__ import annotations
import calendar, json, os, platform, re, secrets, shutil, socket, subprocess, sys, threading, time, urllib.request, collections, zipfile
import socketserver
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
APP = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) if FROZEN else Path(__file__).resolve().parent
ENGINE_SRC = APP / "engine" if (APP / "engine").exists() else APP.parent / "kit" / "worker-win"
PROBE_SRC = (APP / "engine" / "probe.py") if (APP / "engine" / "probe.py").exists() else APP.parent / "kit" / "probe.py"
VERSION = "1.0.3"


def script_cmd(name: str, *args: str) -> list:
    """Commande pour exécuter un script du moteur : le même exécutable (gelé) ou l'interpréteur + app.py, avec --run."""
    return [sys.executable] + ([] if FROZEN else [str(Path(__file__).resolve())]) + ["--run", name, *args]
IS_WIN, IS_MAC = platform.system() == "Windows", platform.system() == "Darwin"
HOME = Path(os.environ.get("FLOPPY_HOME") or (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FLOPPY" if IS_WIN else Path.home() / "FLOPPY"))
ENGINE, STATE, DL = HOME / "engine", HOME / "engine" / "state", HOME / "downloads"
PORT = int(os.environ.get("FLOPPY_PORT", "8788")); BIND = os.environ.get("FLOPPY_BIND", "127.0.0.1")
SIMULATE = os.environ.get("FLOPPY_SIMULATE") == "1"
PY = sys.executable; OLLAMA_PORT = os.environ.get("FLOPPY_OLLAMA_PORT", "11434"); OLLAMA_URL = f"http://127.0.0.1:{OLLAMA_PORT}"; BOARD = "https://flop-kibble.onrender.com"; TC = "https://technocore.chat"
FORCE_INSTALL = os.environ.get("FLOPPY_FORCE_INSTALL") == "1"     # test « machine vierge » : ignore l'Ollama déjà présent
ENGINE_FILES = ["kibble-bot.py", "sign.py", "llm.py", "tg.py", "checkin.py"]
TIER_NOTES = {"A": "GPU ≥ 22 Go ou Mac ≥ 30 Go : Gemma 4 26B, ~300 jobs/h de départ", "B": "GPU ≥ 11 Go ou Mac ≥ 20 Go : Gemma 4 12B, ~200 jobs/h",
              "C": "GPU ≥ 5,5 Go ou Mac ≥ 12 Go : Qwen 3.5 4B, ~150 jobs/h", "D": "sans GPU : Qwen 3.5 4B sur CPU, cadence réduite"}
LOCK = threading.Lock(); TASK = {"name": None, "status": "idle", "log": [], "progress": 0}; WORKER = {"proc": None, "wanted": False, "since": None}
BG = {"machine": {}, "score": {}, "score_ts": 0, "ollama_models": None}


def decode_any(b: bytes) -> str:
    """UTF-8 d'abord, sinon cp1252 (journal écrit par un ancien worker Windows sans PYTHONUTF8)."""
    try: return b.decode("utf-8")
    except UnicodeDecodeError: return b.decode("cp1252", "replace")


def load_state() -> dict:
    try: return json.loads((HOME / "app.json").read_text(encoding="utf-8"))
    except Exception: return {"step": "machine", "machine_name": ("mac" if IS_MAC else "pc") + "-" + secrets.token_hex(2), "probe": {}, "ollama": {}, "model": {}, "identity": {}, "worker": {}, "options": {}}


def save_state(st: dict) -> None:
    HOME.mkdir(parents=True, exist_ok=True); (HOME / "app.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def tlog(msg: str) -> None:
    TASK["log"].append(f"[{time.strftime('%H:%M:%S')}] {msg}"); TASK["log"] = TASK["log"][-200:]


def L(fr: str, en: str) -> str:
    """Texte du journal selon la langue choisie dans les options (fr par défaut)."""
    try: return en if load_state().get("options", {}).get("lang") == "en" else fr
    except Exception: return fr


def run_task(name: str, fn) -> bool:
    if TASK["status"] == "running": return False
    TASK.update(name=name, status="running", log=[], progress=0)
    def go():
        try: fn(); TASK["status"] = "done"; TASK["progress"] = 100
        except Exception as ex: tlog(L("erreur : ", "error: ") + str(ex)); TASK["status"] = "error"
    threading.Thread(target=go, daemon=True).start(); return True


def sh(cmd, timeout=60, **kw) -> str:
    try: return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, **kw).stdout or ""
    except Exception: return ""


def ollama_version() -> str | None:
    try: return json.load(urllib.request.urlopen(f"{OLLAMA_URL}/api/version", timeout=4)).get("version")
    except Exception: return None


def ollama_bin() -> str | None:
    cands = [str(HOME / "Ollama.app" / "Contents" / "Resources" / "ollama")] if IS_MAC else []
    wide = os.environ.get("PATH", "") + os.pathsep + os.pathsep.join(["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin", str(Path.home() / ".local" / "bin")])   # une app lancée par le Finder n'a qu'un PATH minimal
    if not FORCE_INSTALL: cands += [shutil.which("ollama", path=wide)] + (["/Applications/Ollama.app/Contents/Resources/ollama", str(Path.home() / "Applications" / "Ollama.app" / "Contents" / "Resources" / "ollama")] if IS_MAC else [str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"), str(Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Ollama" / "ollama.exe")] if IS_WIN else [])
    elif IS_WIN: cands += [str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe")] if (HOME / "downloads" / "installed.flag").exists() else []
    for c in cands:
        if c and Path(c).exists(): return c
    return None


def ensure_engine_files() -> None:
    ENGINE.mkdir(parents=True, exist_ok=True); STATE.mkdir(parents=True, exist_ok=True); DL.mkdir(parents=True, exist_ok=True)
    for f in ENGINE_FILES + ["probe.py"]:
        src = (PROBE_SRC if f == "probe.py" else ENGINE_SRC / f)
        if src.exists() and (not (ENGINE / f).exists() or src.stat().st_mtime > (ENGINE / f).stat().st_mtime): shutil.copy2(src, ENGINE / f)


# ------------------------------------------------------------------ étapes
def task_scan() -> None:
    ensure_engine_files(); tlog(L("lecture de la machine (système, RAM, GPU, Ollama)…", "reading the machine (system, RAM, GPU, Ollama)…"))
    out = sh(script_cmd("probe.py", "--no-bench"), timeout=120, cwd=str(ENGINE))
    info = json.loads((ENGINE / "probe.json").read_text()) if (ENGINE / "probe.json").exists() else {}
    if not info: raise RuntimeError(L("sonde machine sans résultat : ", "machine probe returned nothing: ") + out[-200:])
    st = load_state(); st["probe"] = info; st["model"] = {"name": info.get("model"), "pulled": False}; st["ollama"] = {"installed": bool(ollama_bin()), "version": ollama_version()}
    save_state(st); TASK["progress"] = 100
    tlog(L(f"palier {info.get('tier')} · {info.get('gpu')} · RAM {info.get('ram_gb')} Go · modèle {info.get('model')}", f"tier {info.get('tier')} · {info.get('gpu')} · RAM {info.get('ram_gb')} GB · model {info.get('model')}"))


def download(url: str, dest: Path) -> None:
    tlog(L(f"téléchargement {url}", f"downloading {url}"))
    req = urllib.request.Request(url, headers={"User-Agent": "FLOPPY/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r, dest.open("wb") as f:
        total = int(r.headers.get("Content-Length") or 0); done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk: break
            f.write(chunk); done += len(chunk)
            if total: TASK["progress"] = int(95 * done / total)
    tlog(L(f"reçu {dest.name} ({done // (1 << 20)} Mo)", f"received {dest.name} ({done // (1 << 20)} MB)"))


def verify_ollama_download(dest: Path) -> None:
    """Compare l'empreinte SHA-256 du fichier téléchargé à sha256sum.txt de la dernière release officielle (GitHub ollama/ollama)."""
    import hashlib
    try:
        req = urllib.request.Request("https://github.com/ollama/ollama/releases/latest/download/sha256sum.txt", headers={"User-Agent": "FLOPPY/1.0"})
        listing = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    except Exception as ex: raise RuntimeError(L(f"liste d'empreintes officielle injoignable ({ex}) : téléchargement refusé par prudence", f"official checksum list unreachable ({ex}): download refused as a precaution"))
    expected = {os.path.basename(parts[-1].lstrip("*")): parts[0] for line in listing.splitlines() if (parts := line.split()) and len(parts) >= 2}   # entrées « ./Ollama-darwin.zip »
    if dest.name not in expected: raise RuntimeError(L(f"{dest.name} absent de la liste d'empreintes officielle : téléchargement refusé", f"{dest.name} missing from the official checksum list: download refused"))
    h = hashlib.sha256()
    with dest.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    if h.hexdigest() != expected[dest.name]: dest.unlink(missing_ok=True); raise RuntimeError(L("empreinte SHA-256 différente de l'officielle : fichier supprimé", "SHA-256 checksum differs from the official one: file deleted"))
    tlog(L("empreinte SHA-256 vérifiée contre la release officielle", "SHA-256 checksum verified against the official release"))


def start_ollama_server() -> None:
    if ollama_version(): return
    b = ollama_bin()
    if not b: raise RuntimeError(L("Ollama introuvable après installation", "Ollama not found after installation"))
    env = dict(os.environ, OLLAMA_HOST=f"127.0.0.1:{OLLAMA_PORT}", OLLAMA_MAX_LOADED_MODELS="1", OLLAMA_KEEP_ALIVE="30m", OLLAMA_FLASH_ATTENTION="1", OLLAMA_CONTEXT_LENGTH="8192", OLLAMA_MODELS=str(HOME / "models"))
    subprocess.Popen([b, "serve"], env=env, stdout=(STATE / "ollama.out").open("ab"), stderr=subprocess.STDOUT, creationflags=(0x08000000 if IS_WIN else 0))
    for _ in range(40):
        if ollama_version(): return
        time.sleep(1)
    raise RuntimeError(L("le serveur Ollama ne répond pas", "the Ollama server does not answer"))


def task_install_ollama() -> None:
    if (ollama_version() and not FORCE_INSTALL) or ollama_bin():
        tlog(L("Ollama déjà présent", "Ollama already present")); start_ollama_server()
    elif IS_MAC:
        z = DL / "Ollama-darwin.zip"; download("https://ollama.com/download/Ollama-darwin.zip", z); verify_ollama_download(z)
        target = Path("/Applications") if (os.access("/Applications", os.W_OK) and not FORCE_INSTALL) else HOME
        r = subprocess.run(["ditto", "-x", "-k", str(z), str(target)], capture_output=True, text=True, timeout=300)   # ditto conserve droits, forks et signature
        if r.returncode != 0:
            with zipfile.ZipFile(z) as zf: zf.extractall(target)
            for f in (target / "Ollama.app").rglob("*"):
                if f.is_file() and ("MacOS" in f.parts or "Resources" in f.parts) and not f.suffix: os.chmod(f, 0o755)
        app = target / "Ollama.app"; sh(["xattr", "-dr", "com.apple.quarantine", str(app)], 60); tlog(L(f"Ollama installé dans {target}", f"Ollama installed in {target}")); start_ollama_server()
    elif IS_WIN:
        exe = DL / "OllamaSetup.exe"; download("https://ollama.com/download/OllamaSetup.exe", exe); verify_ollama_download(exe)
        tlog(L("installation silencieuse…", "silent install…")); r = subprocess.run([str(exe), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=900)   # installateur Inno Setup : /S (NSIS) ouvrirait l'assistant
        if r.returncode: raise RuntimeError(L(f"l'installateur Ollama a renvoyé le code {r.returncode}", f"the Ollama installer returned code {r.returncode}"))
        (DL / "installed.flag").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"))
        for _ in range(60):
            if ollama_bin(): break
            time.sleep(2)
        start_ollama_server()
    else: raise RuntimeError(L("Linux : installez Ollama avec  curl -fsSL https://ollama.com/install.sh | sh  puis relancez cette étape", "Linux: install Ollama with  curl -fsSL https://ollama.com/install.sh | sh  then rerun this step"))
    st = load_state(); st["ollama"] = {"installed": True, "version": ollama_version()}; save_state(st)


def api_pull(model: str) -> None:
    """Télécharge le modèle par l'API du serveur Ollama qui répond (le sien ou le nôtre) : aucune dépendance au binaire dans le PATH."""
    req = urllib.request.Request(f"{OLLAMA_URL}/api/pull", data=json.dumps({"model": model, "stream": True}).encode(), headers={"content-type": "application/json"})
    last, ok = "", False
    with urllib.request.urlopen(req, timeout=900) as r:
        for raw in r:
            try: d = json.loads(raw)
            except Exception: continue
            if d.get("error"): raise RuntimeError(d["error"])
            status, tot, done = d.get("status", ""), d.get("total"), d.get("completed")
            if tot and done: TASK["progress"] = min(90, int(done / tot * 90)); msg = f"{status} · {done * 100 // tot} %"
            else: msg = status
            pct = lambda m: (lambda mm: int(mm.group(1)) if mm else None)(re.search(r"(\d+) %$", m))
            a, b = pct(msg), pct(last)
            if msg and msg != last and (msg.split(" ·")[0] != last.split(" ·")[0] or a is None or b is None or a - b >= 5):   # journal : changement d'étape ou +5 %
                last = msg; tlog(msg[:90])
            if status == "success": ok = True
    if not ok: raise RuntimeError(L("téléchargement du modèle incomplet", "model download incomplete"))


def task_pull_model() -> None:
    st = load_state(); model = st.get("model", {}).get("name") or st.get("probe", {}).get("model") or "qwen3.5:4b"
    tlog(L(f"téléchargement du modèle {model} (plusieurs Go, une seule fois)…", f"downloading model {model} (a few GB, once)…"))
    start_ollama_server()                                                                                          # le serveur qui répond (déjà présent ou le nôtre)
    try: api_pull(model)
    except Exception as ex:
        b = ollama_bin()
        if not b: raise
        tlog(L(f"API indisponible ({str(ex)[:60]}), passage par la commande ollama", f"API unavailable ({str(ex)[:60]}), falling back to the ollama command"))
        penv = dict(os.environ, OLLAMA_HOST=f"127.0.0.1:{OLLAMA_PORT}", OLLAMA_MODELS=str(HOME / "models"))            # même serveur et même dossier de modèles que le nôtre
        pr = subprocess.Popen([b, "pull", model], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=penv, creationflags=(0x08000000 if IS_WIN else 0))
        last = ""
        for line in pr.stdout:
            m = re.search(r"(\d+)%", line)
            if m: TASK["progress"] = min(90, int(m.group(1)) * 0.9)
            if line.strip() and line.strip() != last: last = line.strip(); tlog(last[:90])
        if pr.wait() != 0: raise RuntimeError(L("ollama pull a échoué", "ollama pull failed"))
    tlog(L("mesure de la vitesse (30 s)…", "measuring speed (30 s)…")); toks, runs, t0 = 0, 0, time.time(); tok_s = 0.0
    while time.time() - t0 < 30:
        body = {"model": model, "prompt": "Explain in about 600 characters how TCP congestion control reacts to packet loss, answer first.", "stream": False, "think": False, "options": {"num_predict": 250, "temperature": 0.35}}
        try: o = json.load(urllib.request.urlopen(urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=json.dumps(body).encode(), headers={"content-type": "application/json"}), timeout=600))
        except Exception:
            body.pop("think"); o = json.load(urllib.request.urlopen(urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=json.dumps(body).encode(), headers={"content-type": "application/json"}), timeout=600))
        runs += 1; tok_s = round(o.get("eval_count", 0) / max(o.get("eval_duration", 1) / 1e9, 1e-3), 1)
    st = load_state(); st["model"] = {"name": model, "pulled": True, "tok_s": tok_s, "jobs_per_hour_measured": runs * 120}; save_state(st)
    tlog(L(f"{tok_s} tokens/s · ≈ {runs * 120} générations/h mesurées (30 s, sans passe de contrôle)", f"{tok_s} tokens/s · ≈ {runs * 120} generations/h measured (30 s, without the review pass)"))


def did_of_seed() -> str:
    sys.path.insert(0, str(ENGINE)); import importlib; sign = importlib.import_module("sign")
    key, _ = sign.load_key((ENGINE / "seed.hex").read_text().strip()); return sign.did_of(key)


def task_identity(mode: str, seed_hex: str | None) -> None:
    ensure_engine_files(); seed_path = ENGINE / "seed.hex"
    if mode == "import":
        if not re.fullmatch(r"[0-9a-fA-F]{64}", seed_hex or ""): raise RuntimeError(L("clé importée invalide (64 caractères hexadécimaux attendus)", "invalid imported key (64 hexadecimal characters expected)"))
        seed_path.write_text(seed_hex.strip().lower()); tlog(L("clé importée", "key imported"))
    elif not seed_path.exists():
        seed_path.write_text(secrets.token_hex(32)); tlog(L("clé Ed25519 générée en local (jamais transmise)", "Ed25519 key generated locally (never transmitted)"))
    if IS_WIN: sh(["icacls", str(seed_path), "/inheritance:r", "/grant", f"{os.environ.get('USERNAME', '')}:F"], 30)
    else: os.chmod(seed_path, 0o600)
    did = did_of_seed(); st = load_state(); tokens = [f"machine:{st.get('machine_name', 'floppy')}", "app:floppy-1.0"]
    if st.get("options", {}).get("x_handle"): tokens.append("x:" + st["options"]["x_handle"].lstrip("@"))
    if st.get("options", {}).get("operator"): tokens.append("operator:" + st["options"]["operator"])
    note = None
    if SIMULATE: tlog(L("mode simulation : note DID non publiée", "simulation mode: DID note not published"))
    else:
        out = sh(script_cmd("checkin.py", *tokens), timeout=120, cwd=str(ENGINE)); tlog(out.strip()[-300:] or L("check-in effectué", "check-in done"))
        m = re.search(r"(https://technocore\.chat/kv/did-[^\s]+)", out); note = m.group(1) if m else None
    st["identity"] = {"did": did, "note": note, "published": bool(note) or SIMULATE, "created": time.time()}; save_state(st); write_env(st)
    tlog(L(f"identité : {did}", f"identity: {did}"))


def write_env(st: dict) -> None:
    tier = st.get("probe", {}).get("tier", "C"); model = st.get("model", {}).get("name") or st.get("probe", {}).get("model") or "qwen3.5:4b"
    cap = int(st.get("options", {}).get("cadence") or st.get("probe", {}).get("jobs_per_hour_start") or 150)
    lines = [f"BOT_NAME={st.get('machine_name', 'floppy')}", f"TC_BASE={TC}", "BOT_ENGINES=ollama", f"OLLAMA_MODEL={model}", f"OLLAMA_URL={OLLAMA_URL}", "CLAUDE_HYBRID=0",
             f"BOT_MAX_CLAIMS_DAY={cap}", f"BOT_MAX_CLAIMS_NIGHT={cap}", "BOT_LOCAL_VALIDATE_PER_HOUR=10", f"BOT_SELF_CHECK={'1' if tier in ('A', 'B') else '0'}",
             "BOT_OWN_DIDS=" + ",".join(d for d in {st.get("options", {}).get("operator", ""), st.get("options", {}).get("own_dids", "")} if d)]   # l'opérateur et ses autres machines : ni leurs jobs ni leurs livraisons
    old = {}
    if (ENGINE / ".env").exists():
        for l in (ENGINE / ".env").read_text().splitlines():
            if "=" in l: k, v = l.split("=", 1); old[k] = v
    tok = st.get("options", {}).get("telegram_token") or old.get("TELEGRAM_BOT_TOKEN", "")
    if tok: lines.append(f"TELEGRAM_BOT_TOKEN={tok}")
    if old.get("BOT_SHARD"): lines.append(f"BOT_SHARD={old['BOT_SHARD']}")                         # réglage opérateur multi-machines, conservé s'il existe
    (ENGINE / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not IS_WIN: os.chmod(ENGINE / ".env", 0o600)


# ------------------------------------------------------------------ worker
def worker_alive() -> bool: return WORKER["proc"] is not None and WORKER["proc"].poll() is None


def start_worker() -> None:
    if worker_alive(): return
    ensure_engine_files(); st = load_state(); write_env(st)
    script = ENGINE / ("fake_worker.py" if SIMULATE else "kibble-bot.py")
    if SIMULATE: shutil.copy2(APP / "fake_worker.py", script)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    WORKER["proc"] = subprocess.Popen(script_cmd(script.name), cwd=str(ENGINE), env=env, stdout=(STATE / "bot.out").open("ab"), stderr=subprocess.STDOUT, creationflags=(0x08000000 if IS_WIN else 0))
    WORKER["wanted"], WORKER["since"] = True, time.time()


def stop_worker() -> None:
    WORKER["wanted"] = False
    p = WORKER["proc"]
    if p and p.poll() is None:
        p.terminate()
        try: p.wait(10)
        except Exception: p.kill()
    WORKER["proc"] = None


TG = {"restart": 0, "hot": 0, "restart_day": None, "restarts_today": 0}


def alog(msg: str) -> None:
    """Journal de l'app (jamais de jeton dedans)."""
    try:
        with (STATE / "floppy.log").open("a", encoding="utf-8") as f: f.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}\n")
    except Exception: pass


def lang() -> str: return load_state().get("options", {}).get("lang", "fr")
def tg_token() -> str: return load_state().get("options", {}).get("telegram_token", "")


def tg_chat() -> dict:
    try: return json.loads((STATE / "tg-chat.json").read_text(encoding="utf-8"))
    except Exception: return {}


def tg_api(tok: str, method: str, payload: dict | None = None, timeout: int = 30) -> dict | list:
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/{method}", data=json.dumps(payload or {}).encode(), headers={"Content-Type": "application/json"})
    try: d = json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as ex:
        try: d = json.load(ex)
        except Exception: raise RuntimeError(f"HTTP {ex.code}")
    if not d.get("ok"): raise RuntimeError(d.get("description") or "Telegram error")
    return d["result"]


def tg_send(text: str, raise_error: bool = False) -> bool:
    """Message direct au chat appairé. Jamais bloquant pour l'app ; le jeton n'apparaît dans aucun journal."""
    tok, cid = tg_token(), tg_chat().get("chat_id")
    if not tok or not cid:
        if raise_error: raise RuntimeError("Telegram non appairé" if lang() == "fr" else "Telegram not paired")
        return False
    try: tg_api(tok, "sendMessage", {"chat_id": cid, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, 20); return True
    except Exception as ex:
        alog(f"telegram : envoi échoué ({str(ex)[:120]})")
        if raise_error: raise
        return False


def task_tg_pair() -> None:
    """Appairage : l'utilisateur envoie /start à son bot, on lit le premier message privé reçu (90 s max) et on mémorise ce chat."""
    tok = tg_token(); fr = lang() == "fr"
    if not tok: raise RuntimeError("enregistre d'abord le jeton du bot" if fr else "save the bot token first")
    bot = tg_api(tok, "getMe", {}, 20).get("username", "")
    tlog(f"bot @{bot} · " + ("ouvre-le dans Telegram et envoie /start (90 s)" if fr else "open it in Telegram and send /start (90 s)"))
    try: tg_api(tok, "deleteWebhook", {"drop_pending_updates": False}, 20)          # getUpdates est refusé tant qu'un webhook est posé
    except Exception: pass
    offset = None; t0 = time.time()
    while time.time() - t0 < 90:
        for u in tg_api(tok, "getUpdates", {"timeout": 15, "offset": offset, "allowed_updates": ["message"]}, 40):
            offset = u["update_id"] + 1; ch = (u.get("message") or {}).get("chat") or {}
            if ch.get("type") == "private" and ch.get("id"):
                name = " ".join(x for x in (ch.get("first_name"), ch.get("last_name")) if x) or ch.get("username") or str(ch["id"])
                (STATE / "tg-chat.json").write_text(json.dumps({"chat_id": ch["id"], "name": name, "bot": bot, "paired_at": time.time()}), encoding="utf-8")
                try: tg_api(tok, "getUpdates", {"offset": offset}, 20)              # acquitte les messages lus
                except Exception: pass
                mach = load_state().get("machine_name", "FLOPPY")
                tg_send(f"✅ <b>FLOPPY · {mach}</b> " + ("est connecté à ce chat. Tu recevras ici les alertes (worker arrêté, machine qui chauffe) et un point chaque soir à 20 h."
                                                         if fr else "is connected to this chat. You will get alerts here (worker stopped, machine overheating) and a daily report at 8 pm."))
                tlog(("appairé avec " if fr else "paired with ") + name); TASK["progress"] = 100; return
        TASK["progress"] = min(95, int((time.time() - t0) / 90 * 100))
    raise RuntimeError((f"aucun message reçu : ouvre @{bot} dans Telegram, envoie /start, puis réessaie" if fr else f"no message received: open @{bot} in Telegram, send /start, then retry"))


def tg_unpair() -> None:
    (STATE / "tg-chat.json").unlink(missing_ok=True)
    st = load_state(); st.get("options", {}).pop("telegram_token", None); save_state(st)
    envf = ENGINE / ".env"
    if envf.exists(): envf.write_text("".join(l for l in envf.read_text(encoding="utf-8").splitlines(True) if not l.startswith("TELEGRAM_BOT_TOKEN=")), encoding="utf-8")


def daily_text() -> str:
    s = stats(); sc = s.get("score") or {}; mach = load_state().get("machine_name", "FLOPPY"); fr = lang() == "fr"
    score = (f"\nScore kibble : {sc.get('score')} (rang {sc.get('rank')})" if fr else f"\nKibble score: {sc.get('score')} (rank {sc.get('rank')})") if sc.get("score") is not None else ""
    if fr: return f"📊 <b>FLOPPY · {mach}</b> · aujourd'hui\n{s['today']} livraisons · {s['useful24']} « utile » reçus · {s['not24']} « not » (24 h)\nCadence mesurée : {s['rate60']}/h sur la dernière heure{score}"
    return f"📊 <b>FLOPPY · {mach}</b> · today\n{s['today']} deliveries · {s['useful24']} \"useful\" received · {s['not24']} \"not\" (24 h)\nMeasured pace: {s['rate60']}/h over the last hour{score}"


def tg_watch(now: float) -> None:
    """Alertes (au plus une par 30 min / 1 h) et point quotidien à 20 h local, seulement si un chat est appairé."""
    if not tg_chat(): return
    h = BG.get("machine") or {}; g = h.get("gpu_temp"); fr = lang() == "fr"
    if g and g >= 85 and now - TG["hot"] > 3600:
        TG["hot"] = now; tg_send(f"🌡️ <b>FLOPPY</b> : GPU à {g} °C. " + ("Baisse la cadence dans les Réglages si ça persiste." if fr else "Lower the pace in Settings if it persists."))
    lt = time.localtime(now); day = time.strftime("%Y-%m-%d", lt); flag = STATE / "tg-report.day"
    if lt.tm_hour == 20 and (not flag.exists() or flag.read_text() != day):
        flag.write_text(day); tg_send(daily_text())


def keepalive() -> None:
    last = {"machine": 0, "score": 0}
    while True:
        try:
            now = time.time()
            if WORKER["wanted"] and not worker_alive():
                time.sleep(5); start_worker(); day = time.strftime("%Y-%m-%d")
                if TG["restart_day"] != day: TG["restart_day"], TG["restarts_today"] = day, 0
                TG["restarts_today"] += 1; alog(f"worker relancé ({TG['restarts_today']} fois aujourd'hui)")
                if now - TG["restart"] > 1800:
                    TG["restart"] = now; n = TG["restarts_today"]
                    tg_send(f"⚠️ <b>FLOPPY</b> : " + (f"le worker s'était arrêté, je l'ai relancé ({n} fois aujourd'hui)." if lang() == "fr" else f"the worker had stopped, I restarted it ({n} times today)."))
            if now - last["machine"] > 30: BG["machine"] = machine_health(); BG["autostart"] = autostart_enabled(); last["machine"] = now
            if now - last["score"] > 900: refresh_score(); last["score"] = now
            tg_watch(now)
        except Exception: pass
        time.sleep(3)


def machine_health() -> dict:
    h = {}
    if IS_MAC:
        m = re.search(r"used = ([\d.]+)([MG])", sh(["sysctl", "-n", "vm.swapusage"], 5)); h["swap_gb"] = round(float(m.group(1)) / (1024 if m.group(2) == "M" else 1), 1) if m else None
        m = re.search(r"free percentage: (\d+)%", sh(["memory_pressure"], 10)); h["free_pct"] = int(m.group(1)) if m else None
    elif IS_WIN:
        out = sh(["powershell", "-NoProfile", "-Command", "$o=Get-CimInstance Win32_OperatingSystem; [int]($o.FreePhysicalMemory/1024); [int]($o.TotalVisibleMemorySize/1024)"], 20).split()
        if len(out) >= 2: h["ram_free_mb"], h["ram_total_mb"] = int(out[0]), int(out[1])
    if shutil.which("nvidia-smi"):
        g = sh(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"], 10).split(",")
        if len(g) == 4: h.update(gpu_used=int(g[0]), gpu_total=int(g[1]), gpu_util=int(g[2]), gpu_temp=int(g[3]))
    try: BG["ollama_models"] = len(json.load(urllib.request.urlopen(f"{OLLAMA_URL}/api/ps", timeout=4)).get("models", []))
    except Exception: BG["ollama_models"] = None
    h["ollama"] = ollama_version(); return h


def refresh_score() -> None:
    did = load_state().get("identity", {}).get("did")
    if not did or SIMULATE: return
    try:
        d = json.load(urllib.request.urlopen(f"{BOARD}/api/score?did={did}", timeout=60)); terms = {k: v.get("count") for k, v in d.get("breakdown", {}).get("terms", {}).items()}
        BG["score"] = {"ts": time.time(), "score": d.get("score"), "rank": d.get("rank"), "franchised": d.get("franchised"), **terms}
        with (STATE / "score-history.jsonl").open("a") as f: f.write(json.dumps(BG["score"]) + "\n")
    except Exception as ex: BG["score_error"] = str(ex)[:120]


RESULT = re.compile(r"RESULT (k[0-9a-f]{10}) seq=\d+ \((\d+) caract\S*res, moteur ([a-z0-9.-]+)(?: check:[a-z_]+)?\)"); CLAIM = re.compile(r"CLAIM (k[0-9a-f]{10}) .*\| (.*)")


def stats() -> dict:
    now = time.time(); log = STATE / "bot.log"; ev = []; titles = {}; skipped = ""
    if log.exists():
        with log.open("rb") as f:
            f.seek(max(0, log.stat().st_size - 6_000_000)); lines = decode_any(f.read()).splitlines()
        for raw in lines:
            if len(raw) < 22 or raw[0] != "[": continue
            try: t = calendar.timegm(time.strptime(raw[1:20], "%Y-%m-%dT%H:%M:%S"))
            except Exception: continue
            if now - t > 86400: continue
            b = raw[23:]
            if b.startswith("RESULT "):
                m = RESULT.match(b); ev.append((t, "result", m.group(1) if m else "", m.group(3) if m else "")) if m else None
            elif b.startswith("CLAIM "):
                m = CLAIM.match(b); ev.append((t, "claim", m.group(1) if m else "", "")); titles[m.group(1)] = m.group(2)[:80] if m else ""
            elif b.startswith("génération échouée"): ev.append((t, "fail", "", ""))
            elif b.startswith("VALIDATE-local useful"): ev.append((t, "given", "", ""))
            elif b.startswith("écartés 10 min"): skipped = b
    att = []
    ap = STATE / "attest-received.jsonl"
    if ap.exists():
        for l in decode_any(ap.read_bytes()).splitlines()[-5000:]:
            try: a = json.loads(l)
            except Exception: continue
            if now - a.get("ts", 0) <= 86400: att.append(a)
    h0 = int(now // 3600) * 3600; hours = [h0 - 3600 * i for i in range(23, -1, -1)]
    def hourly(kind): c = collections.Counter(int(e[0] // 3600) * 3600 for e in ev if e[1] == kind); return [c.get(h, 0) for h in hours]
    def hourly_att(v): c = collections.Counter(int(a["ts"] // 3600) * 3600 for a in att if a.get("verdict") == v); return [c.get(h, 0) for h in hours]
    day0 = now - (time.localtime(now).tm_hour * 3600 + time.localtime(now).tm_min * 60 + time.localtime(now).tm_sec)
    res = [e for e in ev if e[1] == "result"]
    return {"now": now, "running": worker_alive(), "since": WORKER["since"], "rate10": sum(1 for e in res if now - e[0] < 600) * 6, "rate60": sum(1 for e in res if now - e[0] < 3600),
            "today": sum(1 for e in res if e[0] >= day0), "total24": len(res), "claims60": sum(1 for e in ev if e[1] == "claim" and now - e[0] < 3600), "fails60": sum(1 for e in ev if e[1] == "fail" and now - e[0] < 3600),
            "given24": sum(1 for e in ev if e[1] == "given"), "useful24": sum(a.get("verdict") == "useful" for a in att), "not24": sum(a.get("verdict") == "not" for a in att),
            "attesters24": len({a.get("attestor") for a in att if a.get("verdict") == "useful"}), "skipped": skipped, "hours": hours, "h_results": hourly("result"), "h_useful": hourly_att("useful"), "h_not": hourly_att("not"),
            "last": [{"ts": e[0], "job": e[2], "title": titles.get(e[2], ""), "engine": e[3]} for e in res[-8:][::-1]], "machine": BG["machine"], "ollama_models": BG["ollama_models"], "score": BG["score"], "score_error": BG.get("score_error")}


def launch_cmd(*args: str) -> list:
    return [sys.executable, *args] if FROZEN else [sys.executable, str(Path(__file__).resolve()), *args]


def autostart_enabled() -> bool:
    """État réel du démarrage automatique (LaunchAgent ou clé Run), lu toutes les 30 s par keepalive()."""
    try:
        if IS_MAC: return (Path.home() / "Library" / "LaunchAgents" / "com.floppy.app.plist").exists()
        if IS_WIN: return "FLOPPY" in sh(["reg", "query", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run", "/v", "FLOPPY"], 10)
    except Exception: pass
    return False


def autostart(enable: bool) -> str:
    cmd = launch_cmd("--play", "--hidden")
    if IS_MAC:
        p = Path.home() / "Library" / "LaunchAgents" / "com.floppy.app.plist"
        if not enable: sh(["launchctl", "bootout", f"gui/{os.getuid()}/com.floppy.app"], 20); p.unlink(missing_ok=True); return L("désactivé", "disabled")
        args = "".join(f"<string>{c}</string>" for c in cmd)
        p.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>\n<key>Label</key><string>com.floppy.app</string>\n<key>ProgramArguments</key><array>{args}</array>\n<key>EnvironmentVariables</key><dict><key>FLOPPY_HOME</key><string>{HOME}</string><key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string></dict>\n<key>KeepAlive</key><true/><key>RunAtLoad</key><true/>\n<key>StandardOutPath</key><string>{HOME / 'app.out'}</string><key>StandardErrorPath</key><string>{HOME / 'app.out'}</string>\n</dict></plist>\n""")
        sh(["launchctl", "bootout", f"gui/{os.getuid()}/com.floppy.app"], 20); sh(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(p)], 20); return L("activé (à l'ouverture de session, en arrière-plan)", "enabled (at login, in the background)")
    if IS_WIN:
        key = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
        if not enable: sh(["reg", "delete", key, "/v", "FLOPPY", "/f"], 20); return L("désactivé", "disabled")
        value = " ".join(f'"{c}"' for c in cmd); out = sh(["reg", "add", key, "/v", "FLOPPY", "/t", "REG_SZ", "/d", value, "/f"], 20)
        return L("activé (à l'ouverture de session, en arrière-plan)", "enabled (at login, in the background)") if "réussi" in out or "success" in out.lower() or out == "" else L("échec : ", "failed: ") + out[:80]
    return L("non pris en charge sur ce système", "not supported on this system")


# ------------------------------------------------------------------ HTTP
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def host_ok(self) -> bool:
        """Refuse les requêtes dont l'en-tête Host n'est pas local (rebinding DNS depuis une page web tierce)."""
        h = (self.headers.get("Host") or "").lower().split(":")[0].strip("[]")
        return h in ("127.0.0.1", "localhost", "::1", BIND.lower()) or (BIND == "0.0.0.0")

    def parse_request(self):
        ok = super().parse_request()
        if ok and not self.host_ok(): self.send_error(403, "Host non local"); return False
        return ok

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes): body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)

    def body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        try: return json.loads(self.rfile.read(n) or b"{}")
        except Exception: return {}

    def do_GET(self):
        try:
            if self.path in ("/", "/index.html"): self.send(200, (APP / "ui" / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path.startswith("/vendor/"):
                # fichiers statiques embarqués (polices, graphiques) : nom de fichier strict, pas de traversée
                rel = self.path[len("/vendor/"):].split("?")[0]
                if not re.fullmatch(r"[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)?", rel) or ".." in rel: self.send(404, {"error": "not found"}); return
                f = APP / "ui" / "vendor" / rel
                if not f.is_file(): self.send(404, {"error": "not found"}); return
                ctype = {"css": "text/css; charset=utf-8", "js": "application/javascript; charset=utf-8", "woff2": "font/woff2", "png": "image/png", "svg": "image/svg+xml"}.get(f.suffix.lstrip("."), "application/octet-stream")
                self.send(200, f.read_bytes(), ctype)
            elif self.path.startswith("/api/state"):
                st = load_state(); st["worker"] = {"running": worker_alive(), "since": WORKER["since"], "wanted": WORKER["wanted"]}
                st["ollama"] = {"installed": bool(ollama_bin()), "version": ollama_version()}; st["task"] = TASK; st["simulate"] = SIMULATE; st["tier_notes"] = TIER_NOTES; st["home"] = str(HOME); st["os"] = platform.system()
                st["options"] = {k: v for k, v in st.get("options", {}).items() if k != "telegram_token"}; st["telegram_set"] = bool(tg_token()); c = tg_chat(); st["telegram"] = {"set": st["telegram_set"], "paired": c.get("name"), "bot": c.get("bot") or load_state().get("options", {}).get("telegram_bot")}; st["version"] = VERSION; st["frozen"] = FROZEN; st["autostart"] = BG.get("autostart", False)
                self.send(200, st)
            elif self.path.startswith("/api/stats"): self.send(200, stats())
            elif self.path.startswith("/api/seed-backup"):
                # Révélation de la clé pour la SAUVEGARDE de l'utilisateur : uniquement depuis cette machine (127.0.0.1), jamais journalisée, jamais transmise.
                if self.client_address[0] not in ("127.0.0.1", "::1"): self.send(403, {"error": "local only"}); return
                sp = ENGINE / "seed.hex"
                if not sp.exists(): self.send(404, {"error": L("pas de clé", "no key")}); return
                self.send(200, {"seed_hex": sp.read_text().strip(), "did": load_state().get("identity", {}).get("did"), "path": str(sp)})
            elif self.path.startswith("/api/logs"):
                log = STATE / "bot.log"; lines = decode_any(log.read_bytes()).splitlines()[-80:] if log.exists() else []
                self.send(200, {"lines": lines})
            else: self.send(404, {"error": "not found"})
        except Exception as ex: self.send(500, {"error": str(ex)[:300]})

    def do_POST(self):
        try:
            if self.headers.get("X-Floppy") != "1": self.send(403, {"error": "X-Floppy header required"}); return
            b = self.body(); p = self.path
            if p == "/api/scan": self.send(200, {"started": run_task("scan", task_scan)})
            elif p == "/api/install-ollama": self.send(200, {"started": run_task("ollama", task_install_ollama)})
            elif p == "/api/pull": self.send(200, {"started": run_task("model", task_pull_model)})
            elif p == "/api/identity": self.send(200, {"started": run_task("identity", lambda: task_identity(b.get("mode", "new"), b.get("seed_hex")))})
            elif p == "/api/options":
                st = load_state(); opts = st.setdefault("options", {})
                rules = {"x_handle": r"^@?[A-Za-z0-9_]{1,15}$", "operator": r"^did:key:z[1-9A-HJ-NP-Za-km-z]{40,60}$", "cadence": r"^\d{2,3}$", "lang": r"^(fr|en)$",
                         "telegram_token": r"^\d{6,12}:[A-Za-z0-9_-]{30,60}$", "own_dids": r"^(did:key:z[1-9A-HJ-NP-Za-km-z]{40,60})(,did:key:z[1-9A-HJ-NP-Za-km-z]{40,60})*$"}
                for k, rx in rules.items():
                    if k not in b: continue
                    v = str(b[k]).strip()
                    if v == "" and k != "telegram_token": opts.pop(k, None)
                    elif re.fullmatch(rx, v): opts[k] = v if k != "cadence" else str(min(600, max(10, int(v))))
                    elif v: self.send(400, {"error": f"{k} : format invalide"}); return
                if "machine_name" in b and b["machine_name"].strip(): st["machine_name"] = re.sub(r"[^\w.-]", "-", b["machine_name"].strip())[:24]
                if b.get("telegram_token") and opts.get("telegram_token"):                       # le jeton est vérifié auprès de Telegram avant d'être gardé
                    try: opts["telegram_bot"] = tg_api(opts["telegram_token"], "getMe", {}, 15).get("username", "")
                    except Exception as ex:
                        opts.pop("telegram_token", None); opts.pop("telegram_bot", None)
                        self.send(400, {"error": ("jeton refusé par Telegram : " if lang() == "fr" else "token rejected by Telegram: ") + str(ex)[:100]}); return
                save_state(st)
                if (ENGINE / "seed.hex").exists(): write_env(st)
                self.send(200, {"ok": True})
            elif p == "/api/telegram-pair": self.send(200, {"started": run_task("telegram", task_tg_pair)})
            elif p == "/api/telegram-test":
                try: tg_send(("🧪 Test FLOPPY · " if lang() == "fr" else "🧪 FLOPPY test · ") + time.strftime("%H:%M"), raise_error=True); self.send(200, {"ok": True})
                except Exception as ex: self.send(200, {"ok": False, "error": str(ex)[:160]})
            elif p == "/api/telegram-unpair": tg_unpair(); self.send(200, {"ok": True})
            elif p == "/api/rescue-file":
                # Fichier de secours écrit PAR L'APP (la fenêtre native ne télécharge pas les fichiers générés côté page) : Téléchargements, 600, puis révélé dans le Finder/l'Explorateur.
                if self.client_address[0] not in ("127.0.0.1", "::1"): self.send(403, {"error": "local only"}); return
                sp = ENGINE / "seed.hex"
                if not sp.exists(): self.send(404, {"error": L("pas encore de clé", "no key yet")}); return
                did = load_state().get("identity", {}).get("did", "") or ""; seed = sp.read_text().strip()
                dl = Path.home() / "Downloads"; dl = dl if dl.is_dir() else HOME; f = dl / f"FLOPPY-rescue-{did[-8:] or 'key'}.txt"
                f.write_text(L(f"FLOPPY — fichier de secours de ton identité\nDID (public) : {did}\nCLÉ PRIVÉE (64 hex, SECRÈTE) : {seed}\n\nQui possède cette clé est toi. Garde ce fichier hors ligne : clé USB, gestionnaire de mots de passe ou papier. Jamais dans un chat, un e-mail ou un dossier cloud en clair.\nPour récupérer ton agent : FLOPPY → étape Identité → « Clé existante » → colle la clé privée.\n",
                               f"FLOPPY — rescue file for your identity\nDID (public): {did}\nPRIVATE KEY (64 hex, SECRET): {seed}\n\nWhoever holds this key is you. Keep this file offline: USB stick, password manager or paper. Never in a chat, an email or a plain cloud folder.\nTo recover your agent: FLOPPY → Identity step → \"Existing key\" → paste the private key.\n"), encoding="utf-8")
                try: os.chmod(f, 0o600)
                except Exception: pass
                try: subprocess.Popen(["open", "-R", str(f)] if IS_MAC else ["explorer", f"/select,{f}"] if IS_WIN else ["xdg-open", str(dl)])
                except Exception: pass
                self.send(200, {"path": str(f)})
            elif p == "/api/backup-done":
                st = load_state(); st.setdefault("identity", {})["backup_confirmed"] = True; st["identity"]["backup_at"] = time.time(); save_state(st); self.send(200, {"ok": True})
            elif p == "/api/play":
                if not load_state().get("identity", {}).get("backup_confirmed"): self.send(409, {"error": L("Confirme d'abord la sauvegarde de ta clé (étape Identité).", "Confirm your key backup first (Identity step).")}); return
                start_worker(); self.send(200, {"running": worker_alive()})
            elif p == "/api/pause": stop_worker(); self.send(200, {"running": worker_alive()})
            elif p == "/api/autostart": r = autostart(bool(b.get("enable", True))); BG["autostart"] = autostart_enabled(); self.send(200, {"result": r})
            elif p == "/api/model":
                st = load_state(); name = re.sub(r"[^\w.:/-]", "", str(b.get("name", "")))[:60]
                if name: st["model"] = {"name": name, "pulled": False}; save_state(st)
                self.send(200, {"ok": bool(name)})
            elif p == "/api/open-folder":
                subprocess.Popen(["open", str(HOME)] if IS_MAC else ["explorer", str(HOME)] if IS_WIN else ["xdg-open", str(HOME)]); self.send(200, {"ok": True})
            elif p == "/api/reset":
                stop_worker(); st = load_state(); keep = {"identity": st.get("identity", {}), "options": st.get("options", {}), "machine_name": st.get("machine_name")}
                st = {"step": "machine", "probe": {}, "ollama": {}, "model": {}, "worker": {}, **keep}; save_state(st); self.send(200, {"ok": True})
            elif p == "/api/reset-step":
                st = load_state(); st["step"] = b.get("step", "machine"); save_state(st); self.send(200, {"ok": True})
            else: self.send(404, {"error": "not found"})
        except Exception as ex: self.send(500, {"error": str(ex)[:300]})



class Server(ThreadingHTTPServer):
    def server_bind(self):
        """Sans la résolution inverse de HTTPServer.server_bind (getfqdn) : sur l'app gelée macOS elle passe par mDNS et bloque ~35 s."""
        socketserver.TCPServer.server_bind(self); self.server_name, self.server_port = self.server_address[0], self.server_address[1]


def main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == "--run":                      # exécute un script du moteur dans ce même exécutable
        import runpy; name = sys.argv[2]
        if name not in ENGINE_FILES + ["probe.py", "fake_worker.py"]: print(f"script inconnu : {name}"); return
        parent = os.getppid()
        def orphan_watch():                                                   # si l'app meurt, le script du moteur s'arrête avec elle
            while True:
                time.sleep(5)
                if os.getppid() != parent: os._exit(0)
        threading.Thread(target=orphan_watch, daemon=True).start()
        sys.argv = [str(ENGINE / name)] + sys.argv[3:]; sys.path.insert(0, str(ENGINE)); os.chdir(ENGINE)
        runpy.run_path(str(ENGINE / name), run_name="__main__"); return
    HOME.mkdir(parents=True, exist_ok=True); ensure_engine_files(); BG["autostart"] = autostart_enabled()
    threading.Thread(target=keepalive, daemon=True).start()
    if "--play" in sys.argv and load_state().get("step") == "ready" and (ENGINE / "seed.hex").exists():
        try: start_ollama_server()
        except Exception: pass
        start_worker()
    try: srv = Server((BIND, PORT), H)
    except OSError as ex:
        print(f"FLOPPY : port {PORT} déjà utilisé ({ex}) — une autre instance tourne ?", flush=True)
        if "--hidden" not in sys.argv:
            import webbrowser; webbrowser.open(f"http://127.0.0.1:{PORT}")
        return
    print(f"FLOPPY {VERSION} sur http://{BIND}:{PORT} · dossier {HOME}" + (" · SIMULATION" if SIMULATE else ""), flush=True)
    if "--hidden" in sys.argv: srv.serve_forever(); return
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        import webview                                                      # fenêtre native (pywebview) si disponible
        webview.create_window("FLOPPY", f"http://127.0.0.1:{PORT}", width=1180, height=820, min_size=(900, 640), background_color="#0b0f14")
        webview.start()
    except ImportError:
        import webbrowser; webbrowser.open(f"http://127.0.0.1:{PORT}")
        srv.serve_forever()
    except Exception as ex:
        print(f"fenêtre native indisponible ({ex}) : navigateur", flush=True); import webbrowser; webbrowser.open(f"http://127.0.0.1:{PORT}"); srv.serve_forever()


if __name__ == "__main__":
    main()
