"""Boot the packaged app with an empty, isolated profile before distributing it."""
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
            for name in ("quality_metrics.py", "delivery_quality.py", "kibble-bot.py"):
                assert (Path(folder) / "engine" / name).is_file(), name
            with urlopen(f"http://127.0.0.1:{port}/api/stats", timeout=10) as response:
                assert json.load(response)["worker_status"] == "paused"
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
