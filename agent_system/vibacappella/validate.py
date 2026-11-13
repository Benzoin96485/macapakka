"""Independent invariants. Musical evidence confidence is never a proof of fidelity."""
from .music import PARTS, RANGES, DRUMS, GRID, tick_to_seconds, seconds_to_tick, sound_events, effective_evidence
from .storage import digest


def validate(score, evidence, start=1, end=None, max_phrase_seconds=10, whistle_min_confidence=.8):
    end = end or len(score["bars"])
    evidence = effective_evidence(score, evidence)
    errors, warnings = [], []
    ids = {n["id"]: n for n in evidence["notes"]}
    drums = {d["id"]: d for d in evidence.get("drums", [])}
    def issue(dest, code, **kw):
        dest.append(dict(code=code, **kw))
    references = {h["id"]: h for h in evidence["harmonies"]}
    for h in score["harmonies"]:
        ref = references.get(h["id"])
        if ref is None or h["candidates"] != ref["candidates"] or h["start_tick"] != ref["start_tick"] or h["end_tick"] != ref["end_tick"]:
            issue(errors, "harmony_evidence_changed", harmony=h["id"])
        elif ref.get("locked") and h["selected"] != 0:
            issue(errors, "locked_harmony_changed", harmony=h["id"])
    for bi in range(start-1, end):
        bar = score["bars"][bi]
        if bi+1 not in score["arranged_bars"]:
            issue(errors, "unarranged_bar", bar=bi+1)
            continue
        for part in PARTS:
            cursor = 0
            for ev in score["score"][part][bi]:
                if ev["offset"] != cursor or ev["duration"] <= 0 or ev["duration"] % GRID or ev["offset"] % GRID:
                    issue(errors, "bar_grid_or_overlap", part=part, bar=bi+1)
                cursor = ev["offset"]+ev["duration"]
                p = ev["pitch"]
                if p is None:
                    continue
                if type(p) is not int or not 0 <= p <= 127:
                    issue(errors, "invalid_pitch", part=part, bar=bi+1)
                    continue
                if part in RANGES and not RANGES[part][0] <= p <= RANGES[part][1]:
                    issue(errors, "range", part=part, bar=bi+1, pitch=p)
                if not isinstance(ev.get("velocity"), int) or not 1 <= ev["velocity"] <= 127:
                    issue(errors, "velocity", part=part, bar=bi+1)
                sources = ev.get("source_ids", [])
                if any(s not in ids and s not in drums for s in sources):
                    issue(errors, "unknown_source", part=part, bar=bi+1)
                ns = [ids[s] for s in sources if s in ids]
                if part == "Whistle" and not any(n["instrument"] == "flute" and n.get("instrument_confidence", 0) >= whistle_min_confidence and n["pitch"] % 12 == p % 12 for n in ns):
                    issue(errors, "whistle_without_flute", bar=bi+1)
                if part == "Lead" and not any(n["role"] == "lead" and n["pitch"] % 12 == p % 12 for n in ns):
                    issue(errors, "lead_without_evidence", bar=bi+1)
                if ns and not any(n["pitch"] % 12 == p % 12 for n in ns):
                    issue(errors, "source_pitch_changed", part=part, bar=bi+1)
                if ev.get("role") not in ("lead", "piano", "flute", "bass", "vocal_backing", "harmonic_support", "editorial", "vp_source", "vp_editorial"):
                    issue(errors, "unknown_musical_role", part=part, bar=bi+1)
                if part == "Whistle" and ev.get("role") != "flute":
                    issue(errors, "whistle_role", bar=bi+1)
                if part == "Lead" and ev.get("role") != "lead":
                    issue(errors, "lead_role", bar=bi+1)
                if ev.get("role") in ("lead", "piano", "flute", "bass", "vocal_backing"):
                    matching = [n for n in ns if n["pitch"] % 12 == p % 12]
                    if not matching:
                        issue(errors, "source_pitch_changed", part=part, bar=bi+1)
                    a = bar["start_tick"]+ev["offset"]
                    if matching and not any(seconds_to_tick(evidence, n["start"])-GRID <= a <= seconds_to_tick(evidence, n["end"])+GRID for n in matching):
                        issue(errors, "source_time_mismatch", part=part, bar=bi+1)
                    valid_role = {"lead": lambda n: n["role"] == "lead",
                                  "piano": lambda n: n["source"] in ("piano", "guitar"),
                                  "flute": lambda n: n["instrument"] == "flute",
                                  "bass": lambda n: n["source"] == "bass",
                                  "vocal_backing": lambda n: n["role"] in ("backing", "backing_candidate")}[ev["role"]]
                    if not any(valid_role(n) for n in ns):
                        issue(errors, "source_role_mismatch", part=part, bar=bi+1)
                if part == "VP" and p not in DRUMS.values():
                    issue(errors, "unsupported_vp_sound", bar=bi+1)
                if part == "VP" and ev.get("role") == "vp_source":
                    a = bar["start_tick"]+ev["offset"]
                    if not any(s in drums and DRUMS[drums[s]["kind"]] == p and abs(seconds_to_tick(evidence, drums[s]["time"])-a) <= GRID for s in sources):
                        issue(errors, "vp_source_mismatch", bar=bi+1)
            if cursor != bar["duration_ticks"]:
                issue(errors, "bar_duration", part=part, bar=bi+1, actual=cursor)
        for tick in range(0, bar["duration_ticks"], GRID):
            pitches = []
            for part in ("Soprano", "Alto", "Tenor", "Bass"):
                for ev in score["score"][part][bi]:
                    if ev["offset"] <= tick < ev["offset"]+ev["duration"] and ev["pitch"] is not None:
                        pitches.append((part, ev["pitch"]))
                        break
            if any(a[1] < b[1] for a, b in zip(pitches, pitches[1:])):
                issue(warnings, "voice_crossing", bar=bi+1, tick=tick)
                break
    lo, hi = score["bars"][start-1]["start_tick"], score["bars"][end-1]["start_tick"]+score["bars"][end-1]["duration_ticks"]
    for h in score["harmonies"]:
        if h["end_tick"] <= lo or h["start_tick"] >= hi:
            continue
        c = h["candidates"][h["selected"]]
        sounding, bass = set(), set()
        for part in ("Soprano", "Alto", "Tenor", "Bass"):
            for ev in sound_events(score, part):
                if ev["start"] < h["end_tick"] and ev["end"] > h["start_tick"]:
                    sounding.add(ev["pitch"] % 12)
                    if part == "Bass":
                        bass.add(ev["pitch"] % 12)
        missing = set(c.get("required_pcs", []))-sounding
        if missing:
            issue(errors, "missing_harmonic_colour", harmony=h["id"], symbol=c["symbol"], pitch_classes=sorted(missing))
        if c["bass_pc"] not in bass:
            issue(errors, "missing_slash_bass", harmony=h["id"], pitch_class=c["bass_pc"])
        if h.get("confidence") in ("low", "provisional"):
            issue(warnings, "unverified_harmony", harmony=h["id"], symbol=c["symbol"])
    for part in PARTS:
        all_events = [(b["start_tick"]+e["offset"], e) for b, evs in zip(score["bars"], score["score"][part]) for e in evs]
        for i, (tick, ev) in enumerate(all_events):
            if not lo <= tick < hi:
                continue
            if ev.get("tie_stop"):
                prev = all_events[i-1] if i else None
                if not prev or not prev[1].get("tie_start") or prev[1]["pitch"] != ev["pitch"] or prev[0]+prev[1]["duration"] != tick:
                    issue(errors, "broken_tie_stop", part=part, tick=tick)
            if ev.get("tie_start"):
                nxt = all_events[i+1] if i+1 < len(all_events) else None
                if not nxt or not nxt[1].get("tie_stop") or nxt[1]["pitch"] != ev["pitch"] or tick+ev["duration"] != nxt[0]:
                    issue(errors, "broken_tie_start", part=part, tick=tick)
        phrase_start, last_end = None, None
        previous_event = None
        for ev in sound_events(score, part):
            a, b = tick_to_seconds(evidence, ev["start"]), tick_to_seconds(evidence, ev["end"])
            if last_end is None or a-last_end >= .12:
                phrase_start = a
            if b-phrase_start > max_phrase_seconds and lo <= ev["start"] < hi:
                issue(warnings, "long_phrase", part=part, seconds=round(b-phrase_start, 2))
                phrase_start = a
            if part != "VP" and previous_event and a-previous_event["end_seconds"] < 2 and lo <= ev["start"] < hi:
                if abs(ev["pitch"]-previous_event["pitch"]) > 12:
                    issue(warnings, "large_melodic_leap", part=part, tick=ev["start"], semitones=ev["pitch"]-previous_event["pitch"])
            previous_event = dict(ev, end_seconds=b)
            last_end = b
    # Guard against a silent lead / piano / backing / VP being called a finished arrangement.
    for role, parts, predicate in (
        ("lead", ["Lead"], lambda n: n["role"] == "lead"),
        ("piano", ["Soprano", "Alto", "Tenor"], lambda n: n["source"] == "piano"),
        ("vocal_backing", ["Soprano", "Alto", "Tenor"], lambda n: n["role"] in ("backing", "backing_candidate"))):
        src = [n for n in evidence["notes"] if predicate(n) and lo <= seconds_to_tick(evidence, n["start"]) < hi]
        represented = {s for p in parts for ev in sound_events(score, p) if ev.get("role") == role and lo <= ev["start"] < hi for s in ev["source_ids"]}
        if src and not represented:
            issue(errors if role == "lead" else warnings, "missing_source_layer", role=role)
        if role == "lead" and src:
            lost = [n["id"] for n in src if n["id"] not in represented]
            if lost:
                issue(warnings, "lead_candidates_not_used", source_ids=lost[:40], count=len(lost))
    relevant_drums = [d for d in evidence.get("drums", []) if lo <= seconds_to_tick(evidence, d["time"]) < hi]
    if relevant_drums and not any(lo <= ev["start"] < hi for ev in sound_events(score, "VP")):
        issue(warnings, "vp_absent_despite_source_drums")
    return {"passed": not errors, "errors": errors, "warnings": warnings,
            "human_listening_review": False, "scope": [start, end], "score_digest": digest(score)}
