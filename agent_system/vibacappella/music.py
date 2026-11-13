"""Canonical concert-pitch score. Time is integer ticks (480 per quarter)."""
from bisect import bisect_right
from copy import deepcopy
import math

TPQ = 480
GRID = 120
PARTS = ("Lead", "Soprano", "Alto", "Tenor", "Bass", "VP", "Whistle")
RANGES = {"Lead": (48, 84), "Soprano": (60, 81), "Alto": (55, 74),
          "Tenor": (48, 69), "Bass": (36, 60), "Whistle": (65, 86)}
DRUMS = {"K": 36, "pf": 38, "ka": 37, "t": 42, "ts": 46, "ksh": 49, "dm": 45}
QUALITIES = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10),
             "maj7": (0, 4, 7, 11), "m7": (0, 3, 7, 10), "sus4": (0, 5, 7),
             "sus2": (0, 2, 7), "7sus4": (0, 5, 7, 10), "add9": (0, 2, 4, 7),
             "madd9": (0, 2, 3, 7), "6": (0, 4, 7, 9), "m6": (0, 3, 7, 9),
             "dim": (0, 3, 6), "m7b5": (0, 3, 6, 10), "aug": (0, 4, 8)}
NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def tick_to_seconds(evidence, tick):
    anchors = evidence["timing"]["anchors"]
    i = min(len(anchors) - 2, max(0, bisect_right([x["tick"] for x in anchors], tick) - 1))
    a, b = anchors[i:i + 2]
    return a["seconds"] + (tick-a["tick"]) / (b["tick"]-a["tick"]) * (b["seconds"]-a["seconds"])


def seconds_to_tick(evidence, seconds):
    anchors = evidence["timing"]["anchors"]
    i = min(len(anchors) - 2, max(0, bisect_right([x["seconds"] for x in anchors], seconds) - 1))
    a, b = anchors[i:i + 2]
    return a["tick"] + (seconds-a["seconds"]) / (b["seconds"]-a["seconds"]) * (b["tick"]-a["tick"])


def check_evidence(e):
    if e.get("schema_version") != 1:
        raise ValueError("Evidence schema_version must be 1")
    if not finite(e.get("duration_seconds")) or e["duration_seconds"] <= 0:
        raise ValueError("Invalid duration")
    anchors = e["timing"]["anchors"]
    if len(anchors) < 2 or anchors[0]["tick"] != 0:
        raise ValueError("Timing needs at least two anchors beginning at tick 0")
    for a in anchors:
        if not isinstance(a["tick"], int) or not finite(a["seconds"]) or a["seconds"] < 0:
            raise ValueError("Invalid timing anchor")
    if any(b["tick"] <= a["tick"] or b["seconds"] <= a["seconds"] for a, b in zip(anchors, anchors[1:])):
        raise ValueError("Timing anchors must be strictly increasing")
    if anchors[-1]["seconds"] > e["duration_seconds"] + .1:
        raise ValueError("Timing extends beyond source audio")
    end = 0
    for i, b in enumerate(e["bars"], 1):
        if b["number"] != i or b["start_tick"] != end or not isinstance(b["duration_ticks"], int) or b["duration_ticks"] <= 0:
            raise ValueError("Bars must be contiguous and numbered from 1")
        if b["duration_ticks"] % GRID or b["denominator"] not in (2, 4, 8, 16):
            raise ValueError("Unsupported meter/grid")
        if b["duration_ticks"] > b["numerator"] * TPQ * 4 / b["denominator"]:
            raise ValueError("Bar exceeds its meter (short pickup/final bars are allowed)")
        end += b["duration_ticks"]
    if end != anchors[-1]["tick"]:
        raise ValueError("Bar and timing endpoints differ")
    ids = set()
    for n in e["notes"]:
        if not isinstance(n["id"], str) or n["id"] in ids:
            raise ValueError("Source note IDs must be unique strings")
        ids.add(n["id"])
        if not all(finite(n[k]) for k in ("start", "end", "confidence")) or not 0 <= n["start"] < n["end"] <= e["duration_seconds"] + .1:
            raise ValueError(f"Invalid source note time: {n['id']}")
        if type(n["pitch"]) is not int or not 0 <= n["pitch"] <= 127 or not 0 <= n["confidence"] <= 1:
            raise ValueError(f"Invalid source note: {n['id']}")
    for d in e.get("drums", []):
        if d["id"] in ids or d["kind"] not in DRUMS or not finite(d["time"]) or not 0 <= d["time"] <= e["duration_seconds"]:
            raise ValueError("Invalid drum evidence")
        ids.add(d["id"])
    end = 0
    for h in e["harmonies"]:
        if h["start_tick"] != end or h["end_tick"] <= end or h["end_tick"] % GRID:
            raise ValueError("Harmony evidence must cover a contiguous timeline")
        if not h["candidates"]:
            raise ValueError("Harmony needs candidates, even if uncertain")
        for c in h["candidates"]:
            if not c["pcs"] or any(type(p) is not int or not 0 <= p < 12 for p in c["pcs"] + c.get("required_pcs", [])):
                raise ValueError("Invalid chord pitch classes")
            if not set(c.get("required_pcs", [])).issubset(c["pcs"]):
                raise ValueError("Required colors must belong to the reference chord")
        end = h["end_tick"]
    if end != anchors[-1]["tick"]:
        raise ValueError("Harmony evidence does not cover the score")
    return e


def empty_score(evidence, title):
    evidence = deepcopy(evidence)
    return {"schema_version": 1, "title": title, "revision": 0, "human_listening_review": False,
            "source_sha256": evidence["audio_sha256"], "bars": evidence["bars"],
            "timing": evidence["timing"], "parts": list(PARTS), "ranges": RANGES,
            "harmonies": [dict(h, selected=0, selection_reason="Unreviewed analysis candidate") for h in evidence["harmonies"]],
            "score": {p: [[] for _ in evidence["bars"]] for p in PARTS}, "arranged_bars": [],
            "decisions": [], "review_notes": [], "source_roles": {}}


def effective_evidence(score, evidence):
    """Layer explicit vocal-role interpretations over immutable raw observations."""
    overrides = score.get("source_roles", {})
    if not overrides:
        return evidence
    notes = []
    for n in evidence["notes"]:
        if n["id"] in overrides:
            o = overrides[n["id"]]
            if n["source"] not in ("vocals", "lead", "backing") or o["role"] not in ("lead", "backing_candidate", "ignore"):
                raise ValueError("Invalid vocal-role interpretation")
            n = dict(n, role=o["role"], original_role=n["role"], role_interpretation=o["reason"])
        notes.append(n)
    return dict(evidence, notes=notes)


def nearest_pitch(pc, part, previous=None):
    lo, hi = RANGES[part]
    choices = [p for p in range(lo, hi+1) if p % 12 == pc]
    target = previous if previous is not None else (lo+hi)/2
    return min(choices, key=lambda p: abs(p-target))


def note(pitch, offset, duration, role, source_ids=(), velocity=64, syllable="", confidence=0.5):
    return dict(pitch=pitch, offset=offset, duration=duration, role=role,
                source_ids=list(source_ids), confidence=confidence, velocity=velocity, syllable=syllable)


def active_notes(score, part):
    for b, events in zip(score["bars"], score["score"][part]):
        for ev in events:
            if ev["pitch"] is not None:
                yield b["start_tick"] + ev["offset"], b["start_tick"] + ev["offset"] + ev["duration"], ev


def sound_events(score, part):
    """Merge only explicit ties; repeated pitches remain separate attacks."""
    result = []
    for start, end, ev in active_notes(score, part):
        if ev.get("tie_stop") and result and result[-1]["end"] == start and result[-1]["pitch"] == ev["pitch"]:
            result[-1]["end"] = end
            result[-1]["source_ids"] = list(dict.fromkeys(
                result[-1].get("source_ids", []) + ev.get("source_ids", [])))
        else:
            result.append(dict(ev, start=start, end=end))
    return result


def fill_rests(events, duration):
    out, cursor = [], 0
    for ev in sorted(events, key=lambda e: e["offset"]):
        if ev["offset"] < cursor:
            raise ValueError("Monophonic parts cannot contain overlapping events")
        if ev["offset"] > cursor:
            out.append(note(None, cursor, ev["offset"]-cursor, "rest"))
        out.append(ev)
        cursor = ev["offset"] + ev["duration"]
    if cursor < duration:
        out.append(note(None, cursor, duration-cursor, "rest"))
    if cursor > duration:
        raise ValueError("Event crosses bar boundary; split it with an explicit tie")
    return out
