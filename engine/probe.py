#!/usr/bin/env python3
"""probe.py — kit FLOPPY : lit la machine (système, RAM, GPU), vérifie Ollama, mesure les tokens/s réels sur un modèle du palier candidat
et propose le palier + les réglages (cadence, parallélisme). Fonctionne sur Windows, macOS et Linux. Sortie JSON dans probe.json."""
import json, os, platform, re, shutil, subprocess, sys, time, urllib.request
try: sys.stdout.reconfigure(encoding="utf-8")                      # consoles Windows en cp1252
except Exception: pass
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
TIERS = [  # (nom, VRAM min Go, RAM min Go si pas de GPU dédié (Apple Silicon unifié), modèle, jobs/h de départ, parallélisme)
    ("A", 22, 30, "gemma4:26b", 300, 3), ("B", 11, 20, "gemma4:12b", 200, 2), ("C", 5.5, 12, "qwen3.5:4b", 150, 2), ("D", 0, 6, "qwen3.5:4b", 60, 1)]
def sh(cmd):
    try: return subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=isinstance(cmd, str)).stdout.strip()
    except Exception: return ""
info = {"os": platform.system(), "os_version": platform.version()[:60], "machine": platform.machine(), "cpu": platform.processor()[:60]}
# RAM
if info["os"] == "Darwin": info["ram_gb"] = round(int(sh(["sysctl", "-n", "hw.memsize"]) or 0) / 2**30, 1)
elif info["os"] == "Windows": info["ram_gb"] = round(int(re.search(r"\d+", sh(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"]) or "0").group()) / 2**30, 1)
else: info["ram_gb"] = round(int((re.search(r"MemTotal:\s+(\d+)", open("/proc/meminfo").read()) or [0, 0])[1]) / 2**20, 1)
# GPU
smi = sh(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]) if shutil.which("nvidia-smi") else ""
if smi:
    name, mem, drv = [x.strip() for x in smi.splitlines()[0].split(",")]; info["gpu"] = name; info["vram_gb"] = round(int(re.search(r"\d+", mem).group()) / 1024, 1); info["driver"] = drv
elif info["os"] == "Darwin":
    chip = re.search(r"Chip: (.+)", sh(["system_profiler", "SPHardwareDataType"])); info["gpu"] = (chip.group(1).strip() if chip else "Apple Silicon"); info["vram_gb"] = info["ram_gb"]; info["unified"] = True
else: info["gpu"] = "aucun GPU détecté"; info["vram_gb"] = 0
# Ollama
try: info["ollama"] = json.load(urllib.request.urlopen(f"{OLLAMA}/api/version", timeout=5)).get("version")
except Exception: info["ollama"] = None
# palier
tier = next((t for t in TIERS if info["vram_gb"] >= t[1] and info["ram_gb"] >= t[2]), TIERS[-1])
info["tier"], info["model"], info["jobs_per_hour_start"], info["parallel"] = tier[0], tier[3], tier[4], tier[5]
# banc : tokens/s réels sur le modèle du palier (téléchargement si absent)
if info["ollama"] and "--no-bench" not in sys.argv:
    print(f"palier {tier[0]} → modèle {tier[3]} ; téléchargement/chargement puis mesure d'une minute…", flush=True)
    subprocess.run(["ollama", "pull", tier[3]], capture_output=True)
    def gen(prompt, n):
        body = {"model": tier[3], "prompt": prompt, "stream": False, "think": False, "options": {"num_predict": n, "temperature": 0.35}}
        req = urllib.request.Request(f"{OLLAMA}/api/generate", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
        try: return json.load(urllib.request.urlopen(req, timeout=600))
        except Exception:
            body.pop("think"); req = urllib.request.Request(f"{OLLAMA}/api/generate", data=json.dumps(body).encode(), headers={"content-type": "application/json"}); return json.load(urllib.request.urlopen(req, timeout=600))
    gen("Say OK.", 5); t0 = time.time(); toks = 0; runs = 0
    while time.time() - t0 < 60:
        o = gen("Explain in about 900 characters how TCP congestion control reacts to packet loss, answer first.", 350); toks += o.get("eval_count", 0); runs += 1
        info["tok_s"] = round(o.get("eval_count", 0) / max(o.get("eval_duration", 1) / 1e9, 1e-3), 1)
    info["bench_runs_per_min"] = runs; info["tokens_per_day_at_full_load"] = int(info["tok_s"] * 86400)
    info["jobs_per_hour_measured_max"] = int(runs * 60)         # une génération ≈ un job (sans la passe de contrôle)
json.dump(info, open("probe.json", "w"), indent=1); print(json.dumps(info, indent=1, ensure_ascii=False))
