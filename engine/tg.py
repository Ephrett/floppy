#!/usr/bin/env python3
"""tg.py — passerelle Telegram minimale (bibliothèque standard uniquement) pour l'agent Technocore.

Jeton : TELEGRAM_BOT_TOKEN dans .env (mode 600). Destinataire : l'unique chat appairé (state/tg-chat.json).
Un envoi qui échoue (pas encore appairé, réseau coupé) est mis en file dans state/tg-outbox.jsonl et rejoué
par le démon tg-bot.py. Le jeton n'est jamais journalisé ni affiché ; aucun secret ne transite par ici.

  tg.py send [--title T] [--plain] <texte…>   envoie (HTML : <b> <i> <code> <pre> <a>) ; --plain échappe le texte
  tg.py send --stdin [--title T]              texte lu sur l'entrée standard (échappé)
  tg.py photo <fichier> [légende]             envoie une image
  tg.py document <fichier> [légende]          envoie un fichier
  tg.py status                                appairage et file d'attente (aucun secret)
"""
from __future__ import annotations
import html, json, mimetypes, os, sys, time, urllib.error, urllib.request, uuid
try: import fcntl                                   # verrou de fichier : fcntl sur macOS/Linux, msvcrt sur Windows
except ImportError: fcntl = None; import msvcrt
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "state"; STATE.mkdir(exist_ok=True)
CHAT_FILE, OUTBOX, LOG = STATE / "tg-chat.json", STATE / "tg-outbox.jsonl", STATE / "tg.log"
DRAFTS, LOCK = STATE / "x-drafts.json", STATE / "tg.lock"
MAX_LEN = 3900
_TAGS = ("pre", "code", "b", "i")


def env() -> dict:
    e = dict(os.environ); f = HERE / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1); e[k.strip()] = v.strip().strip('"').strip("'")
    return e


def token() -> str: return env().get("TELEGRAM_BOT_TOKEN", "")


def chat_id():
    try: return json.loads(CHAT_FILE.read_text(encoding="utf-8", errors="replace")).get("chat_id")
    except Exception: return None


def esc(s) -> str: return html.escape(str(s), quote=False)


def _safe(s: str) -> str:
    t = token(); return s.replace(t, "<jeton>") if t else s


def log(msg: str) -> None:
    with LOG.open("a", encoding="utf-8") as f: f.write(f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] {_safe(str(msg))}\n")


class _Lock:
    def __init__(self, path: Path = LOCK): self.f = open(path, "a+")
    def __enter__(self):
        if fcntl: fcntl.flock(self.f, fcntl.LOCK_EX)
        else:
            for _ in range(200):
                try: msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1); break
                except OSError: time.sleep(0.05)
        return self
    def __exit__(self, *a):
        try:
            if fcntl: fcntl.flock(self.f, fcntl.LOCK_UN)
            else: self.f.seek(0); msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception: pass
        self.f.close()


def _multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    b = f"----tg{uuid.uuid4().hex}"; out = bytearray()
    for k, v in fields.items():
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, p in files.items():
        p = Path(p); ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{p.name}"\r\nContent-Type: {ctype}\r\n\r\n'.encode()
        out += p.read_bytes() + b"\r\n"
    out += f"--{b}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={b}"


def api(method: str, payload: dict | None = None, files: dict | None = None, timeout: int = 60) -> dict:
    tok = token()
    if not tok: raise RuntimeError("TELEGRAM_BOT_TOKEN absent de .env")
    url = f"https://api.telegram.org/bot{tok}/{method}"
    if files:
        fields = {k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v)) for k, v in (payload or {}).items()}
        data, ctype = _multipart(fields, files)
    else:
        data, ctype = json.dumps(payload or {}).encode(), "application/json"
    req = urllib.request.Request(url, data=data, headers={"content-type": ctype}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: res = json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        try: desc = json.loads(body).get("description", body)
        except Exception: desc = body
        raise RuntimeError(f"{method}: HTTP {e.code} {_safe(desc)}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"{method}: réseau ({e.reason})") from None
    if not res.get("ok"): raise RuntimeError(f"{method}: {res.get('description')}")
    return res["result"]


def keyboard(rows) -> dict:
    """rows = [[(libellé, url-ou-callback_data), …], …] ; une valeur commençant par http devient un bouton lien."""
    return {"inline_keyboard": [[({"text": t, "url": v} if str(v).startswith("http") else {"text": t, "callback_data": v})
                                 for t, v in row] for row in rows]}


def split_text(text: str) -> list[str]:
    parts, cur = [], ""
    for line in text.split("\n"):
        while len(line) > MAX_LEN:
            if cur: parts.append(cur); cur = ""
            parts.append(line[:MAX_LEN]); line = line[MAX_LEN:]
        if len(cur) + len(line) + 1 > MAX_LEN: parts.append(cur); cur = line
        else: cur = f"{cur}\n{line}" if cur else line
    if cur: parts.append(cur)
    return parts or [""]


def _balance(chunks: list[str]) -> list[str]:
    """Referme les balises ouvertes en fin de morceau et les rouvre au suivant (Telegram refuse l'HTML déséquilibré)."""
    out, carry = [], []
    for c in chunks:
        c = "".join(f"<{t}>" for t in carry) + c; carry = []
        for t in _TAGS:
            if c.count(f"<{t}>") > c.count(f"</{t}>"): carry.append(t)
        out.append(c + "".join(f"</{t}>" for t in reversed(carry)))
    return out


def enqueue(kind: str, payload: dict) -> None:
    with _Lock():
        with OUTBOX.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"id": uuid.uuid4().hex[:8], "ts": time.time(), "kind": kind, "payload": payload}, ensure_ascii=False) + "\n")


def _deliver(kind: str, p: dict, cid) -> int | None:
    if kind == "message":
        chunks = _balance(split_text(p["text"])); mid = None
        for i, chunk in enumerate(chunks):
            body = {"chat_id": cid, "text": chunk, "parse_mode": "HTML", "disable_notification": bool(p.get("silent")),
                    "link_preview_options": {"is_disabled": not p.get("preview", False)}}
            if p.get("buttons") and i == len(chunks) - 1: body["reply_markup"] = p["buttons"]
            try: mid = api("sendMessage", body)["message_id"]
            except RuntimeError as ex:
                if "parse" not in str(ex).lower(): raise
                body.pop("parse_mode"); mid = api("sendMessage", body)["message_id"]   # secours : texte brut
        return mid
    if kind in ("photo", "document"):
        body = {"chat_id": cid, "caption": (p.get("caption") or "")[:1000], "parse_mode": "HTML"}
        return api("send" + kind.capitalize(), body, files={kind: p["path"]}, timeout=120)["message_id"]
    raise RuntimeError(f"type inconnu {kind}")


def _send(kind: str, p: dict, queue: bool = True) -> int | None:
    cid = chat_id()
    if not cid:
        if queue: enqueue(kind, p); log(f"{kind} mis en file (aucun chat appairé)")
        return None
    try: return _deliver(kind, p, cid)
    except Exception as ex:
        log(f"{kind} échoué : {ex}")
        if queue: enqueue(kind, p)
        return None


def send(text: str, buttons: dict | None = None, *, preview: bool = False, silent: bool = False, queue: bool = True) -> int | None:
    """Envoie un message HTML au chat appairé ; renvoie le message_id (dernier morceau) ou None si mis en file."""
    return _send("message", {"text": text, "buttons": buttons, "preview": preview, "silent": silent}, queue)


def send_photo(path, caption: str = "", queue: bool = True) -> int | None:
    return _send("photo", {"path": str(Path(path).resolve()), "caption": caption}, queue)


def send_document(path, caption: str = "", queue: bool = True) -> int | None:
    return _send("document", {"path": str(Path(path).resolve()), "caption": caption}, queue)


def flush_outbox() -> tuple[int, int]:
    """Rejoue la file d'attente ; renvoie (envoyés, restants). Les éléments de plus de 3 jours sont abandonnés."""
    cid = chat_id()
    if not cid or not OUTBOX.exists(): return 0, 0
    with _Lock():
        lines = [l for l in OUTBOX.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]; OUTBOX.write_text("", encoding="utf-8")
    keep, sent = [], 0
    for l in lines:
        try: item = json.loads(l)
        except Exception: continue
        if time.time() - item.get("ts", 0) > 3 * 86400: continue
        try: _deliver(item["kind"], item["payload"], cid); sent += 1
        except Exception as ex:
            log(f"rejeu échoué : {ex}"); item["tries"] = item.get("tries", 0) + 1
            if item["tries"] < 20: keep.append(item)
    if keep:
        with _Lock():
            with OUTBOX.open("a", encoding="utf-8") as f:
                for it in keep: f.write(json.dumps(it, ensure_ascii=False) + "\n")
    return sent, len(keep)


# ---------------------------------------------------------------- brouillons X (partagés avec veille-x.py et tg-bot.py)
def drafts_load() -> list:
    try: return json.loads(DRAFTS.read_text(encoding="utf-8", errors="replace"))
    except Exception: return []


def _drafts_save(lst: list) -> None: DRAFTS.write_text(json.dumps(lst[-300:], ensure_ascii=False), encoding="utf-8")


def drafts_add(rec: dict) -> None:
    with _Lock():
        lst = [d for d in drafts_load() if d.get("id") != rec["id"]]; lst.append(rec); _drafts_save(lst)


def drafts_update(did: str, **fields):
    with _Lock():
        lst = drafts_load()
        for d in lst:
            if d.get("id") == did: d.update(fields); _drafts_save(lst); return d
    return None


def draft_card(d: dict) -> tuple[str, dict]:
    """Carte Telegram d'un brouillon : texte HTML + clavier (lien, posté / passer, annuler)."""
    lang = (d.get("lang") or "en").upper()[:2]; when = (d.get("created_at") or "")[:16].replace("T", " ")
    t = d.get("text") or ""
    lines = [f"🐦 <b>Brouillon X</b> · @{esc(d.get('author', '?'))} · score {esc(d.get('score', '?'))}/5 · {lang}",
             f"{d.get('likes', 0)} ❤️ · {esc(when)} UTC",
             f"<i>« {esc(t[:300])}{'…' if len(t) > 300 else ''} »</i>", "",
             f"✍️ <b>Réponse ({lang})</b> — appuie sur le bloc pour copier :", f"<pre>{esc(d.get('reply', ''))}</pre>"]
    if d.get("fr") and d["fr"].strip().upper() != "IDEM": lines.append(f"🇫🇷 <i>{esc(d['fr'])}</i>")
    if d.get("why"): lines.append(f"💡 {esc(d['why'])}")
    st = d.get("status", "pending")
    if st == "posted": lines.append(f"\n✅ <b>Posté</b> le {esc(d.get('status_at', ''))}")
    elif st == "skipped": lines.append(f"\n⏭ <b>Passé</b> le {esc(d.get('status_at', ''))}")
    rows = [[("🔗 Ouvrir le post", d.get("url", "https://x.com"))]]
    rows.append([("✅ Posté", f"post:{d['id']}"), ("⏭ Passer", f"skip:{d['id']}")] if st == "pending" else [("↩️ Annuler", f"undo:{d['id']}")])
    return "\n".join(lines), keyboard(rows)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0
    cmd, args = argv[0], list(argv[1:])
    if cmd == "send":
        title, plain, use_stdin = None, False, False
        while args and args[0].startswith("--"):
            a = args.pop(0)
            if a == "--title": title = args.pop(0); plain = True
            elif a == "--plain": plain = True
            elif a == "--stdin": use_stdin, plain = True, True
        text = sys.stdin.read() if use_stdin else " ".join(args)
        if plain: text = esc(text)
        if title: text = f"<b>{esc(title)}</b>\n{text}"
        print("envoyé" if send(text.strip()) else "mis en file (aucun chat appairé ou réseau indisponible)"); return 0
    if cmd in ("photo", "document"):
        fn = send_photo if cmd == "photo" else send_document
        print("envoyé" if fn(args[0], esc(" ".join(args[1:]))) else "mis en file"); return 0
    if cmd == "status":
        n = len([l for l in OUTBOX.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]) if OUTBOX.exists() else 0
        print(f"appairé : {'oui' if chat_id() else 'non'} · en file : {n} · jeton : {'présent' if token() else 'absent'}"); return 0
    print(__doc__); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
