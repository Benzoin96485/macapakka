"""Atomic checkpoints and bounded, shell-free local processes (macOS/Linux)."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


class Store:
    def __init__(self, root, secrets=()):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.secrets = tuple(s for s in secrets if s)

    def path(self, name):
        p = (self.root / name).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError("Path escapes run directory")
        return p

    def read(self, name):
        return read_json(self.path(name))

    def write(self, name, value):
        write_json(self.path(name), value)

    def redact(self, value):
        text = json.dumps(value, ensure_ascii=False, default=str)
        for secret in self.secrets:
            text = text.replace(secret, "[REDACTED]")
        return json.loads(text)

    def log(self, event, **data):
        with self.path("events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(self.redact({"time": time.time(), "event": event, **data}), ensure_ascii=False) + "\n")

    @contextmanager
    def lock(self):
        with self.path("run.lock").open("a") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Another process is working on this run") from None
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def command(argv, log_path, timeout=900, extra_env=None, secret_env_names=()):
    """Only trusted application code supplies argv; the LLM cannot execute commands."""
    env = {k: v for k, v in os.environ.items()
           if k not in secret_env_names and not re.search(r"(API_KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", k, re.I)}
    env.update(extra_env or {})
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w") as log:
        process = subprocess.Popen([str(x) for x in argv], stdout=log, stderr=subprocess.STDOUT,
                                   env=env, start_new_session=True)
        try:
            rc = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise RuntimeError(f"Tool timed out; see {log_path}") from None
    if rc:
        raise RuntimeError(f"Tool exited with code {rc}; see {log_path}")


def worker_env():
    return {"PYTHONPATH": str(Path(__file__).resolve().parents[1]),
            "NUMBA_CACHE_DIR": "/tmp/vibacappella-numba"}
