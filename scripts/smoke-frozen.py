"""Boot the packaged app with an empty, isolated profile before distributing it."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen


def verify_engine(profile, source):
    """Reject missing or outdated installed modules, not merely a bootable UI."""
    tree = ast.parse((source / "app.py").read_text(encoding="utf-8"))
    names = next(ast.literal_eval(node.value) for node in tree.body
                 if isinstance(node, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "ENGINE_FILES" for t in node.targets))
    for name in names + ["probe.py"]:
        expected = (source / "engine" / name).read_bytes()
        installed = (profile / "engine" / name).read_bytes()
        if hashlib.sha256(installed).digest() != hashlib.sha256(expected).digest():
            raise AssertionError("Installed engine differs from candidate: " + name)


def main():
    executable = Path(sys.argv[1]).resolve()
    expected = re.search(r'^VERSION = "([^"]+)"', Path("app.py").read_text(encoding="utf-8"), re.M)[1]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="floppy-smoke-") as folder:
        env = dict(os.environ, FLOPPY_HOME=folder, FLOPPY_SIMULATE="1",
                   FLOPPY_PORT=str(port), FLOPPY_BIND="127.0.0.1")
        process = subprocess.Popen([str(executable), "--hidden"], env=env)
        try:
            deadline = time.monotonic() + 90
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"Packaged app exited: {process.returncode}")
                try:
                    with urlopen(f"http://127.0.0.1:{port}/api/state", timeout=3) as response:
                        state = json.load(response)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(1)
            assert state["frozen"] and state["simulate"], state
            assert state["version"] == expected, state["version"]
            assert Path(state["home"]).resolve() == Path(folder).resolve()
            assert not state["worker"]["running"]
            verify_engine(Path(folder), Path.cwd())
            with urlopen(f"http://127.0.0.1:{port}/api/stats", timeout=10) as response:
                stats = json.load(response)
                assert stats["worker_status"] == "ready", stats["worker_status"]
                assert stats["total24"] == 0 and not stats["running"]
            with urlopen(f"http://127.0.0.1:{port}/", timeout=10) as response:
                assert b"FLOPPY" in response.read()
            print(f"Frozen app {expected}: empty-profile boot, engine, API and UI OK")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
