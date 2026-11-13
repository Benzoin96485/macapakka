"""Local audio preparation; heavy libraries are isolated in a worker interpreter."""
from pathlib import Path
import shutil

from .music import check_evidence
from .storage import command, sha256, worker_env


def prepare(store, cfg, evidence_file=None):
    state = store.read("state.json")
    original = store.path(state["input"])
    if sha256(original) != state["input_sha256"]:
        raise ValueError("Input changed since this run was created")
    if store.path("evidence.json").exists():
        e = check_evidence(store.read("evidence.json"))
        if e["audio_sha256"] != state["input_sha256"]:
            raise ValueError("Evidence belongs to a different recording")
        return e
    if evidence_file:
        from .storage import read_json
        e = check_evidence(read_json(evidence_file))
        if e["audio_sha256"] != state["input_sha256"]:
            raise ValueError("Imported evidence hash does not match this audio")
        store.write("evidence.json", e)
        store.log("import_evidence", sha256=sha256(evidence_file))
        return e
    command([cfg["render"]["ffmpeg"], "-nostdin", "-v", "error", "-y", "-i", original,
             "-ar", "44100", "-ac", "2", "-c:a", "pcm_f32le", store.path("work/input.wav")],
            store.path("logs/ingest.log"), cfg["analysis"]["timeout_seconds"], secret_env_names=[cfg["llm"]["api_key_env"]])
    command([cfg["analysis"]["python"], "-m", "vibacappella.audio_worker", str(store.root)],
            store.path("logs/analysis.log"), cfg["analysis"]["timeout_seconds"], worker_env(), [cfg["llm"]["api_key_env"]])
    return check_evidence(store.read("evidence.json"))


def doctor(cfg):
    import importlib.util
    import os
    def executable(p):
        return bool(p and (shutil.which(p) or (Path(p).is_file() and os.access(p, os.X_OK))))
    checks = {"ffmpeg": executable(cfg["render"]["ffmpeg"]),
              "ffprobe": executable(cfg["render"]["ffprobe"]),
              "analysis_python": executable(cfg["analysis"]["python"]),
              "render_python": executable(cfg["render"]["python"]),
              "musescore": executable(cfg["render"]["musescore"]),
              "soundfont": Path(cfg["render"]["soundfont"]).is_file() if cfg["render"]["soundfont"] else False,
              "fluidsynth": executable(cfg["render"]["fluidsynth"])}
    from .config import endpoint_config
    try:
        endpoint_config(cfg)
        checks["llm_configured"] = True
    except (ValueError, OSError):
        checks["llm_configured"] = False
    checks["current_python_modules"] = {m: bool(importlib.util.find_spec(m)) for m in ("numpy", "librosa", "basic_pitch", "demucs", "soundfile", "reportlab")}
    checks["note"] = "Module checks refer to the current interpreter. No model downloads or paid API calls were made."
    return checks
