"""Command line entry point. Every input starts a versioned, resumable run."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys

from . import __version__
from .agent import run_agents
from .analysis import prepare, doctor
from .config import load_config
from .export import export_bundle
from .llm import Client
from .storage import Store, sha256, digest, read_json
from .validate import validate


def create_run(audio, cfg, run_dir=None):
    audio = Path(audio).expanduser().resolve()
    if not audio.is_file():
        raise ValueError("Input audio does not exist")
    if run_dir is None:
        slug = re.sub(r"[^A-Za-z0-9_-]", "_", audio.stem)[:48]
        run_dir = Path("runs")/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+"-"+slug)
    root = Path(run_dir).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("Run directory is not empty; use resume or a new directory")
    store = Store(root)
    (root/"input").mkdir(exist_ok=True)
    (root/"work").mkdir(exist_ok=True)
    target = root/"input"/("source"+audio.suffix.lower())
    shutil.copy2(audio, target)
    store.write("config.json", cfg)
    store.write("state.json", {"version": __version__, "status": "created", "input": str(target.relative_to(root)),
                "input_sha256": sha256(target), "config_hash": digest(cfg), "human_listening_review": False})
    store.log("created", input_sha256=sha256(target))
    return store


def status(store, phase, **kwargs):
    state = store.read("state.json")
    if phase != "failed":
        state.pop("error", None)
    state.update(status=phase, **kwargs)
    store.write("state.json", state)
    store.log("status", status=phase, **kwargs)


def execute(store, cfg, evidence_file=None, analyze_only=False, client=None):
    with store.lock():
        try:
            store.write("config.json", cfg)
            # Fail before expensive local work when a full run lacks API configuration.
            if not analyze_only and client is None:
                client = Client(cfg, store)
            status(store, "analyzing")
            evidence = prepare(store, cfg, evidence_file)
            state = store.read("state.json")
            evidence_hash = digest(evidence)
            if state.get("evidence_hash") and state["evidence_hash"] != evidence_hash:
                raise ValueError("Evidence changed inside an existing run; create a new run for revised evidence")
            status(store, "analyzed", evidence_hash=evidence_hash)
            if analyze_only:
                return
            status(store, "arranging")
            run_agents(client, store, cfg, evidence)
            status(store, "exporting")
            exported = export_bundle(store, cfg)
            status(store, "exported_draft_needs_review", export=exported)
            print(store.path(exported+"/review.html"), flush=True)
        except Exception as exc:
            status(store, "failed", error=store.redact(str(exc)))
            raise


def resume_config(store, config_path):
    old = store.read("config.json")
    if not config_path:
        return old
    new = load_config(config_path)
    if old["analysis"] != new["analysis"] or old["arrangement"] != new["arrangement"]:
        raise ValueError("Resume may change only LLM/render configuration. New analysis/arrangement settings require a new run.")
    return new


def main(argv=None):
    parser = argparse.ArgumentParser(prog="vibacappella", description="Audio → evidence → arranging/review agents → score + rehearsal tracks")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("doctor", help="Check local capabilities without downloads or API calls")
    p.add_argument("--config")
    for name in ("run", "analyze"):
        p = sub.add_parser(name)
        p.add_argument("audio")
        p.add_argument("--config")
        p.add_argument("--run-dir")
        p.add_argument("--evidence", help="Corrected evidence JSON bound to this audio's SHA-256")
    for name in ("resume", "export", "validate", "status"):
        p = sub.add_parser(name)
        p.add_argument("run_dir")
        if name in ("resume", "export"):
            p.add_argument("--config")
    p = sub.add_parser("demo", help="Explicit offline scripted-provider integration demo; no API key needed")
    p.add_argument("--config", required=True)
    p.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            print(json.dumps(doctor(load_config(args.config)), indent=2, ensure_ascii=False))
        elif args.command in ("run", "analyze"):
            cfg = load_config(args.config)
            store = create_run(args.audio, cfg, args.run_dir)
            print("Run:", store.root, flush=True)
            execute(store, cfg, args.evidence, args.command == "analyze")
        elif args.command == "demo":
            from .demo import demo
            demo(load_config(args.config), args.run_dir)
        else:
            store = Store(args.run_dir)
            cfg = resume_config(store, getattr(args, "config", None))
            if args.command == "status":
                print(json.dumps(store.read("state.json"), indent=2, ensure_ascii=False))
            elif args.command == "resume":
                execute(store, cfg)
            else:
                with store.lock():
                    store.write("config.json", cfg)
                    report = validate(store.read("score.json"), store.read("evidence.json"),
                        max_phrase_seconds=cfg["arrangement"]["max_phrase_seconds"],
                        whistle_min_confidence=cfg["arrangement"]["whistle_min_confidence"])
                    store.write("validation.json", report)
                    if args.command == "validate":
                        print(json.dumps(report, indent=2, ensure_ascii=False))
                        return 0 if report["passed"] else 2
                    status(store, "exporting")
                    try:
                        exported = export_bundle(store, cfg)
                    except Exception as exc:
                        status(store, "failed", error=store.redact(str(exc)))
                        raise
                    status(store, "exported_draft_needs_review", export=exported)
                    print(store.path(exported+"/review.html"))
        return 0
    except (ValueError, RuntimeError, FileNotFoundError, ImportError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
