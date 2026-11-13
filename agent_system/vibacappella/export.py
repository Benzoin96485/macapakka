"""Deterministic MusicXML/MIDI from the same canonical score, plus export audits."""
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

from .music import PARTS, DRUMS, TPQ, GRID, sound_events
from .storage import command, sha256, worker_env, write_json, digest

TYPES = {1920: ("whole", 0), 1440: ("half", 1), 960: ("half", 0),
         720: ("quarter", 1), 480: ("quarter", 0), 360: ("eighth", 1),
         240: ("eighth", 0), 120: ("16th", 0)}
SPELLINGS = (("C", 0), ("D", -1), ("D", 0), ("E", -1), ("E", 0), ("F", 0),
             ("G", -1), ("G", 0), ("A", -1), ("A", 0), ("B", -1), ("B", 0))


def fragments(ev):
    """Split durations into notatable beat-aware pieces; ties preserve sounding notes."""
    pos, left = ev["offset"], ev["duration"]
    out = []
    while left:
        boundary = TPQ-pos % TPQ
        maximum = left if pos % TPQ == 0 else min(left, boundary)
        d = max(k for k in TYPES if k <= maximum)
        out.append((pos, d))
        pos += d
        left -= d
    return out


def elem(parent, tag, text=None, **attrs):
    e = ET.SubElement(parent, tag, {k.replace("_", "-"): str(v) for k, v in attrs.items()})
    if text is not None:
        e.text = str(text)
    return e


def tempo_events(score):
    anchors = score["timing"]["anchors"]
    return [(a["tick"], max(1, min(0xffffff, round((b["seconds"]-a["seconds"])*1e6*TPQ/(b["tick"]-a["tick"])))))
            for a, b in zip(anchors, anchors[1:])]


def musicxml(score, path, selected=PARTS):
    root = ET.Element("score-partwise", version="4.0")
    elem(elem(root, "work"), "work-title", score["title"])
    identification = elem(root, "identification")
    elem(identification, "creator", "Vibacappella agent · rehearsal draft", type="arranger")
    elem(elem(identification, "encoding"), "software", "vibacappella-agent 0.1")
    part_list = elem(root, "part-list")
    for p in selected:
        pid = "P"+str(PARTS.index(p)+1)
        sp = elem(part_list, "score-part", id=pid)
        elem(sp, "part-name", p)
        elem(sp, "part-abbreviation", p[:2]+".")
        presets = sorted(set(DRUMS.values())) if p == "VP" else [None]
        for drum in presets:
            iid = pid+"I"+str(drum or 1)
            si = elem(sp, "score-instrument", id=iid)
            elem(si, "instrument-name", "Vocal percussion" if drum else "Flute" if p == "Whistle" else "Grand Piano")
            mi = elem(sp, "midi-instrument", id=iid)
            elem(mi, "midi-channel", 10 if p == "VP" else PARTS.index(p)+1)
            elem(mi, "midi-program", 74 if p == "Whistle" else 1)
            if drum:
                elem(mi, "midi-unpitched", drum+1)
    for part in selected:
        pid = "P"+str(PARTS.index(part)+1)
        part_node = elem(root, "part", id=pid)
        for bi, bar in enumerate(score["bars"]):
            measure = elem(part_node, "measure", number=bi+1,
                           implicit="yes" if bar["duration_ticks"] != bar["numerator"]*TPQ*4/bar["denominator"] else "no")
            attrs = elem(measure, "attributes")
            if bi == 0:
                elem(attrs, "divisions", TPQ)
            tm = elem(attrs, "time")
            elem(tm, "beats", bar["numerator"])
            elem(tm, "beat-type", bar["denominator"])
            if bi == 0:
                clef = elem(attrs, "clef")
                elem(clef, "sign", "percussion" if part == "VP" else "F" if part == "Bass" else "G")
                if part != "VP":
                    elem(clef, "line", 4 if part == "Bass" else 2)
                if part == "Tenor":
                    elem(clef, "clef-octave-change", -1)
            base, end = bar["start_tick"], bar["start_tick"]+bar["duration_ticks"]
            if part == selected[0]:
                for tick, us in tempo_events(score):
                    if base <= tick < end:
                        d = elem(measure, "direction", placement="above")
                        if tick == base:
                            m = elem(elem(d, "direction-type"), "metronome")
                            elem(m, "beat-unit", "quarter")
                            elem(m, "per-minute", round(60e6/us, 2))
                        else:
                            elem(elem(d, "direction-type"), "words", "", print_object="no")
                        elem(d, "offset", tick-base, sound="yes")
                        elem(d, "sound", tempo=60e6/us)
                for h in score["harmonies"]:
                    if base <= h["start_tick"] < end:
                        d = elem(measure, "direction", placement="above")
                        elem(elem(d, "direction-type"), "words", h["candidates"][h["selected"]]["symbol"], font_weight="bold")
                        elem(d, "offset", h["start_tick"]-base)
            for ev in score["score"][part][bi]:
                frags = fragments(ev)
                for fi, (pos, duration) in enumerate(frags):
                    n = elem(measure, "note")
                    p = ev["pitch"]
                    if p is None:
                        elem(n, "rest")
                    elif part == "VP":
                        unpitched = elem(n, "unpitched")
                        elem(unpitched, "display-step", "C")
                        elem(unpitched, "display-octave", 5)
                    else:
                        pitch = elem(n, "pitch")
                        step, alter = SPELLINGS[p % 12]
                        elem(pitch, "step", step)
                        if alter:
                            elem(pitch, "alter", alter)
                        elem(pitch, "octave", p//12-1)
                    elem(n, "duration", duration)
                    stop = p is not None and (ev.get("tie_stop") or fi > 0)
                    start = p is not None and (ev.get("tie_start") or fi < len(frags)-1)
                    for is_tie, t in ((stop, "stop"), (start, "start")):
                        if is_tie:
                            elem(n, "tie", type=t)
                    if p is not None and part == "VP":
                        elem(n, "instrument", id=pid+"I"+str(p))
                    ty, dots = TYPES[duration]
                    elem(n, "type", ty)
                    if dots:
                        elem(n, "dot")
                    if p is not None and part == "VP":
                        elem(n, "notehead", "x")
                    if stop or start:
                        notation = elem(n, "notations")
                        for is_tie, t in ((stop, "stop"), (start, "start")):
                            if is_tie:
                                elem(notation, "tied", type=t)
                    if p is not None and ev.get("syllable") and fi == 0 and not ev.get("tie_stop"):
                        elem(elem(n, "lyric"), "text", ev["syllable"])
            if bi == len(score["bars"])-1:
                elem(elem(measure, "barline", location="right"), "bar-style", "light-heavy")
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def vlq(n):
    if n < 0:
        raise ValueError("Negative MIDI delta")
    out = [n & 127]
    while n := n >> 7:
        out.insert(0, (n & 127)|128)
    return bytes(out)


def midi(score, path, selected=PARTS):
    end_tick = score["bars"][-1]["start_tick"]+score["bars"][-1]["duration_ticks"]
    events = [(tick, 0, b"\xff\x51\x03"+us.to_bytes(3, "big")) for tick, us in tempo_events(score)]
    for b in score["bars"]:
        denom = b["denominator"].bit_length()-1
        events.append((b["start_tick"], 1, bytes([255, 88, 4, b["numerator"], denom, 24, 8])))
    tracks = [events]
    for p in selected:
        channel = 9 if p == "VP" else PARTS.index(p)
        data = [(0, -2, b"\xff\x03"+vlq(len(p))+p.encode()),
                (0, -1, bytes([0xc0|channel, 73 if p == "Whistle" else 0]))]
        for ev in sound_events(score, p):
            data += [(ev["start"], 2, bytes([0x90|channel, ev["pitch"], ev["velocity"]])),
                     (ev["end"], 0, bytes([0x80|channel, ev["pitch"], 0]))]
        tracks.append(data)
    raw = b"MThd"+struct.pack(">IHHH", 6, 1, len(tracks), TPQ)
    for track in tracks:
        data, prev = b"", 0
        for tick, _, event in sorted(track, key=lambda x: x[:2]):
            data += vlq(tick-prev)+event
            prev = tick
        data += vlq(end_tick-prev)+b"\xff\x2f\x00"
        raw += b"MTrk"+struct.pack(">I", len(data))+data
    Path(path).write_bytes(raw)


def read_midi(path):
    raw = Path(path).read_bytes()
    if raw[:4] != b"MThd":
        raise ValueError("Not MIDI")
    pos, tracks, tempos = 14, [], []
    def variable(data, i):
        value = 0
        while True:
            b = data[i]; i += 1; value = (value << 7)+(b & 127)
            if not b & 128:
                return value, i
    while pos < len(raw):
        length = int.from_bytes(raw[pos+4:pos+8], "big")
        data = raw[pos+8:pos+8+length]; pos += length+8
        i, tick, running, notes, active = 0, 0, None, [], {}
        while i < len(data):
            delta, i = variable(data, i); tick += delta
            status = data[i]
            if status & 128:
                i += 1; running = status
            else:
                status = running
            if status == 255:
                kind = data[i]; i += 1
                size, i = variable(data, i)
                content = data[i:i+size]; i += size
                if kind == 81:
                    tempos.append((tick, int.from_bytes(content, "big")))
                continue
            size = 1 if status & 240 in (192, 208) else 2
            values = data[i:i+size]; i += size
            if status & 240 == 144 and values[1]:
                active[(status & 15, values[0])] = tick
            elif status & 240 == 128 or (status & 240 == 144 and values[1] == 0):
                key = (status & 15, values[0])
                notes.append((active.pop(key), tick, key[1]))
        if active:
            raise ValueError("Hanging MIDI note")
        tracks.append({"notes": sorted(notes), "end_tick": tick})
    return tracks, tempos


def audit_notation(score, xml_path, midi_path, selected=PARTS):
    root = ET.parse(xml_path).getroot()
    errors = []
    for p, node in zip(selected, root.findall("part")):
        for bi, measure in enumerate(node.findall("measure")):
            actual = []
            for n in measure.findall("note"):
                if n.find("rest") is not None:
                    pitch = None
                elif n.find("unpitched") is not None:
                    pitch = int(n.find("instrument").get("id").split("I")[-1])
                else:
                    q = n.find("pitch")
                    pitch = (int(q.findtext("octave"))+1)*12+{"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}[q.findtext("step")]+int(q.findtext("alter", "0"))
                actual += [pitch]*(int(n.findtext("duration"))//GRID)
            expected = [ev["pitch"] for ev in score["score"][p][bi] for _ in range(ev["duration"]//GRID)]
            if actual != expected:
                errors.append(f"MusicXML differs: {p} bar {bi+1}")
    tracks, tempos = read_midi(midi_path)
    if tempos != tempo_events(score):
        errors.append("MIDI tempo map differs")
    for p, track in zip(selected, tracks[1:]):
        expected = sorted((e["start"], e["end"], e["pitch"]) for e in sound_events(score, p))
        if expected != track["notes"]:
            errors.append(f"MIDI differs: {p}")
    if len(root.findall("part")) != len(selected) or len(tracks) != len(selected)+1:
        errors.append("Exported part count differs")
    return errors


def export_bundle(store, cfg):
    score = store.read("score.json")
    report = store.read("validation.json")
    if not report["passed"]:
        raise ValueError("Cannot export a score with validation errors")
    if report.get("score_digest") != digest(score) or report.get("scope") != [1, len(score["bars"])]:
        raise ValueError("Validation is stale or covers only part of the score; validate this exact score before exporting")
    name = f"exports/revision-{score['revision']:05d}"
    base_name, attempt = name, 1
    while store.path(name).exists():
        attempt += 1
        name = f"{base_name}-render-{attempt:03d}"
    root = store.path(name)
    root.mkdir(parents=True, exist_ok=True)
    for folder in ("scores", "midi", "audio", "logs"):
        (root/folder).mkdir(exist_ok=True)
    write_json(root/"score.json", score)
    errors = []
    for label, parts in [("Full_Score", PARTS)]+[(p, [p]) for p in PARTS]:
        xp, mp = root/"scores"/(label+".musicxml"), root/"midi"/(label+".mid")
        musicxml(score, xp, parts)
        midi(score, mp, parts)
        errors += audit_notation(score, xp, mp, parts)
    if errors:
        raise RuntimeError("Export round-trip failed: "+"; ".join(errors))
    store.log("notation_audit", passed=True, files=16)
    command([cfg["render"]["python"], "-m", "vibacappella.render", str(store.root), name],
            store.path("logs/render.log"), cfg["render"]["timeout_seconds"], worker_env(), [cfg["llm"]["api_key_env"]])
    from .report import create_report
    create_report(store, root)
    files = {str(p.relative_to(root)): sha256(p) for p in sorted(root.rglob("*")) if p.is_file() and p.name != "manifest.json"}
    write_json(root/"manifest.json", {"files": files, "score_revision": score["revision"],
               "input_sha256": score["source_sha256"], "status": "exported_draft_needs_review"})
    return name
