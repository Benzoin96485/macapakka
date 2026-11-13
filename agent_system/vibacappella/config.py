"""Configuration contains environment variable NAMES, never credentials."""
import copy
import os
from pathlib import Path
import sys
import tomllib
from urllib.parse import urlparse

DEFAULTS = {
    "llm": {"base_url_env": "PRIME_BASE_URL", "model_env": "PRIME_MODEL",
            "api_key_env": "PRIME_API_KEY",
            "base_url": "https://api.pinference.ai/api/v1", "model": "z-ai/glm-5.3",
            "secrets_file": "secrets/prime.env", "team_id_env": "PRIME_TEAM_ID",
            "include_usage": True,
            "endpoint": "chat/completions", "auth_header": "Authorization",
            "auth_prefix": "Bearer ", "tool_mode": "native",
            "max_tokens_field": "max_tokens", "max_output_tokens": 4096,
            "timeout_seconds": 120, "retries": 2, "max_calls": 512,
            "max_total_tokens": 800000, "max_turns_per_window": 12},
    "analysis": {"python": sys.executable, "separation": "demucs",
                 "demucs_model": "htdemucs_6s", "device": "cpu", "stems_dir": "",
                 "transcriber": "basic_pitch", "lead_backend": "basic_pitch",
                 "game_model_dir": "", "game_language": "en",
                 "tempo": 0.0, "meter": "auto", "first_downbeat_seconds": 0.0,
                 "timeout_seconds": 7200, "max_audio_seconds": 1200},
    "arrangement": {"title": "A cappella arrangement", "window_bars": 8,
                    "max_phrase_seconds": 10.0, "whistle_min_confidence": 0.8,
                    "preserve_harmony": True},
    "render": {"python": sys.executable, "audio_backend": "samples",
               "soundfont": "", "musescore": "", "fluidsynth": "fluidsynth",
               "ffmpeg": "ffmpeg", "ffprobe": "ffprobe", "pdf_backend": "musescore",
               "font_file": "", "pdf_python": "", "timeout_seconds": 900, "sample_rate": 44100,
               "mp3": True},
}


def load_config(path=None):
    cfg = copy.deepcopy(DEFAULTS)
    if path:
        with open(path, "rb") as f:
            override = tomllib.load(f)
        for section, values in override.items():
            if section not in cfg or not isinstance(values, dict):
                raise ValueError(f"Unknown configuration section: {section}")
            for key, value in values.items():
                if key not in cfg[section]:
                    raise ValueError(f"Unknown configuration field: {section}.{key}")
                cfg[section][key] = value
    if cfg["llm"]["tool_mode"] not in ("native", "json"):
        raise ValueError("llm.tool_mode must be native or json")
    if cfg["llm"]["max_tokens_field"] not in ("max_tokens", "max_completion_tokens"):
        raise ValueError("Unsupported token limit field")
    if not 1 <= cfg["arrangement"]["window_bars"] <= 8:
        raise ValueError("window_bars must be 1..8")
    if cfg["render"]["audio_backend"] not in ("samples", "musescore", "fluidsynth"):
        raise ValueError("audio_backend must be samples, musescore or fluidsynth")
    if cfg["render"]["pdf_backend"] not in ("musescore", "proof"):
        raise ValueError("pdf_backend must be musescore or proof")
    if cfg["analysis"]["separation"] not in ("demucs", "provided", "none"):
        raise ValueError("separation must be demucs, provided or none")
    if not cfg["arrangement"]["preserve_harmony"]:
        raise ValueError("This workflow preserves reference harmony; reharmonization is not supported")
    for key in ("max_output_tokens", "max_total_tokens", "max_calls", "max_turns_per_window", "timeout_seconds"):
        if type(cfg["llm"][key]) is not int or cfg["llm"][key] <= 0:
            raise ValueError(f"llm.{key} must be a positive integer")
    if not 0 <= cfg["llm"]["retries"] <= 5:
        raise ValueError("llm.retries must be 0..5")
    return cfg


def provider_values(cfg):
    """Read literal dotenv values without executing shell code or exporting secrets.

    Relative paths are anchored to agent_system, independent of the working directory.
    Explicit environment values take precedence over file values.
    """
    c = cfg["llm"]
    values = {}
    filename = c.get("secrets_file", "")
    if filename:
        path = Path(filename).expanduser()
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / path
        if path.is_file():
            allowed = {c["api_key_env"], c["base_url_env"], c["model_env"], c.get("team_id_env", "")}
            for line in path.read_text().splitlines():
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:].strip()
                if not line or line.startswith("#"):
                    continue
                name, sep, value = line.partition("=")
                name, value = name.strip(), value.strip()
                if not sep or name not in allowed:
                    continue
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1]
                values[name] = value
    for name in (c["api_key_env"], c["base_url_env"], c["model_env"], c.get("team_id_env", "")):
        if name in os.environ:
            values[name] = os.environ[name]
    return values


def endpoint_config(cfg):
    c = cfg["llm"]
    values = provider_values(cfg)
    base = values.get(c["base_url_env"], "") or c["base_url"]
    model = values.get(c["model_env"], "") or c["model"]
    key = values.get(c["api_key_env"], "")
    if not base or not model or not key:
        raise ValueError(f"Set {c['base_url_env']}, {c['model_env']}, {c['api_key_env']}; or provide them in the configured secrets_file")
    u = urlparse(base)
    if u.scheme != "https" and not (u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost", "::1")):
        raise ValueError("LLM URL must use HTTPS (HTTP is allowed only for local tests)")
    if u.username or u.password or u.query or u.fragment:
        raise ValueError("Do not put credentials, query parameters or fragments in base_url")
    if c["endpoint"].startswith(("/", "http")) or ".." in c["endpoint"]:
        raise ValueError("endpoint must be a relative API route")
    return base.rstrip("/") + "/" + c["endpoint"], model, key
