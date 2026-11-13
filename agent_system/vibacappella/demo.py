"""An explicitly scripted provider and original synthetic audio for integration QA.

This is not an LLM and is never selected by production run/resume commands.
"""
import json
import math
from pathlib import Path
import struct
import tempfile
import wave

from .music import TPQ, check_evidence
from .storage import sha256, write_json


def fixture(audio):
    sr, duration = 16000, 8.0
    notes, drums = [], []
    chords = [dict(symbol="Cadd9", pcs=[0,2,4,7], required_pcs=[2,4], bass_pc=0),
              dict(symbol="G7/B", pcs=[7,11,2,5], required_pcs=[11,5], bass_pc=11),
              dict(symbol="Am7", pcs=[9,0,4,7], required_pcs=[0,7], bass_pc=9),
              dict(symbol="Fadd9", pcs=[5,7,9,0], required_pcs=[7,9], bass_pc=5)]
    def add(source, role, a, b, p, instrument=None):
        n = dict(id=f"{source}:{len(notes)}", source=source, role=role, start=a, end=b,
                 pitch=p, confidence=.95, instrument=instrument or source)
        if source == "flute":
            n.update(instrument_confidence=1., attribution="synthetic_fixture_ground_truth")
        notes.append(n)
    for bar, chord in enumerate(chords):
        start = bar*2
        for i, pitch in enumerate((67,69,71,72)):
            add("lead", "lead", start+i*.5, start+i*.5+.375, pitch)
        add("bass", "bass", start, start+1.875, 36+chord["bass_pc"])
        # A recognisable syncopated instrumental line, not a repeated chord template.
        for i, pc in enumerate((chord["pcs"][0], chord["pcs"][-1], chord["pcs"][1])):
            a = start+(0,.75,1.25)[i]
            add("piano", "candidate", a, a+.25, 60+pc)
        add("backing", "backing", start+.5, start+1.75, 60+chord["required_pcs"][0])
        if bar == 2:
            add("flute", "flute", start, start+.75, 77)
            add("flute", "flute", start+1, start+1.75, 79)
        for i, kind in enumerate(("K", "t", "pf", "t", "K", "t", "pf")):
            drums.append(dict(id=f"drum:{bar}:{i}", time=start+i*.25, kind=kind, strength=.85))
    samples = []
    for i in range(round(duration*sr)):
        t = i/sr
        value = 0.
        for n in notes:
            if n["start"] <= t < n["end"]:
                env = min(1, (t-n["start"])*100, (n["end"]-t)*100)
                value += .055*math.sin(2*math.pi*440*2**((n["pitch"]-69)/12)*t)*env
        samples.append(round(max(-1, min(1, value))*32767))
    with wave.open(str(audio), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes(struct.pack("<"+"h"*len(samples), *samples))
    evidence = dict(schema_version=1, audio_sha256=sha256(audio), duration_seconds=duration,
        timing={"anchors": [{"tick": i*480, "seconds": i*.5} for i in range(17)]},
        bars=[dict(number=i+1, start_tick=i*1920, duration_ticks=1920, numerator=4, denominator=4, section="fixture") for i in range(4)],
        notes=notes, drums=drums,
        harmonies=[dict(id=f"h:{i}", start_tick=i*1920, end_tick=(i+1)*1920, candidates=[dict(c, score=1)],
                        locked=True, confidence="fixture") for i, c in enumerate(chords)],
        alerts=["OFFLINE DEMO: original synthetic input and ground-truth fixture evidence; scripted provider, not a real LLM or transcription benchmark."],
        provenance={"synthetic_fixture": True})
    return check_evidence(evidence)


class ScriptedClient:
    def complete(self, messages, schemas):
        task = json.loads(messages[1]["content"])
        start, end = task["bars"]
        completed = [m for m in messages if m["role"] == "tool"]
        if not completed:
            name, args = "inspect_bars", {"start": start, "end": end}
        elif len(completed) == 1 and task["role"] == "arranger":
            name, args = "arrange_bars", dict(start=start, end=end, texture="flow", backing=True, vp_style="fill", density=.7)
        elif len(completed) < (3 if task["role"] == "arranger" else 2):
            name, args = "validate", {}
        else:
            name, args = "finish", {"review_note": "Offline scripted integration check: preserve known colors and source roles. Real LLM judgement and human listening have not been exercised."}
        return {"role": "assistant", "content": None, "tool_calls": [{"id": f"call_{len(completed)}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)}}]}


def demo(cfg, run_dir):
    from .cli import create_run, execute
    with tempfile.TemporaryDirectory(prefix="vibacappella-demo-") as tmp:
        audio = Path(tmp)/"original_fixture.wav"
        evidence = fixture(audio)
        path = Path(tmp)/"evidence.json"
        write_json(path, evidence)
        cfg["arrangement"]["title"] = "Vibacappella - Offline Integration Demo"
        store = create_run(audio, cfg, run_dir)
        store.log("demo", provider="scripted", transcription="fixture_ground_truth", real_llm=False)
        execute(store, cfg, path, client=ScriptedClient())
