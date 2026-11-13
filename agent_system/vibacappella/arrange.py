"""Source-conditioned orchestration tools; the LLM chooses texture and edits events."""
from copy import deepcopy

from .music import (PARTS, RANGES, GRID, TPQ, DRUMS, note, nearest_pitch,
                    seconds_to_tick, tick_to_seconds, fill_rests, effective_evidence)


def source_spans(e):
    return [(max(0, round(seconds_to_tick(e, n["start"])/GRID)*GRID),
             max(GRID, round(seconds_to_tick(e, n["end"])/GRID)*GRID), n) for n in e["notes"]]


def events_from_cells(cells):
    events, i = [], 0
    while i < len(cells):
        ev = cells[i]
        j = i+1
        while j < len(cells) and cells[j] == ev:
            j += 1
        if ev is None:
            events.append(note(None, i*GRID, (j-i)*GRID, "rest"))
        else:
            events.append(dict(ev, offset=i*GRID, duration=(j-i)*GRID))
        i = j
    return events


def arrange_bars(score, evidence, start, end, texture="flow", backing=True,
                 vp_style="source", density=0.65, whistle_min_confidence=.8):
    if texture not in ("flow", "sustain", "sparse") or vp_style not in ("source", "sparse", "drive", "fill", "silent"):
        raise ValueError("Unknown texture or VP style")
    if not 0.1 <= density <= 1:
        raise ValueError("density must be 0.1..1")
    evidence = effective_evidence(score, evidence)
    spans = source_spans(evidence)
    previous = {p: (RANGES[p][0]+RANGES[p][1])//2 for p in RANGES}
    if start > 1:
        for p in previous:
            for ev in reversed(score["score"][p][start-2]):
                if ev["pitch"] is not None:
                    previous[p] = ev["pitch"]
                    break
    for bi in range(start-1, end):
        bar = score["bars"][bi]
        base, dur = bar["start_tick"], bar["duration_ticks"]
        cells = {p: [None]*(dur//GRID) for p in PARTS}
        local = [(max(0, a-base), min(dur, max(a+GRID, b)-base), n)
                 for a, b, n in spans if a < base+dur and b > base]
        local.sort(key=lambda row: (row[0], -row[2]["confidence"]))

        def put(part, a, b, n, role, exact=False):
            p = n["pitch"] if exact and RANGES[part][0] <= n["pitch"] <= RANGES[part][1] else nearest_pitch(n["pitch"] % 12, part, previous[part])
            for i in range(a//GRID, min(len(cells[part]), max(a+GRID, b)//GRID)):
                if cells[part][i] is None:
                    cells[part][i] = note(p, 0, GRID, role, [n["id"]],
                                          80 if part == "Lead" else 64, n.get("syllable", ""), n["confidence"])
            previous[part] = p

        # Preserve melody pitch classes; only register is adaptable.
        for a, b, n in local:
            if n["role"] == "lead":
                put("Lead", a, b, n, "lead", exact=True)
            elif n["instrument"] == "flute" and n.get("instrument_confidence", 0) >= whistle_min_confidence:
                put("Whistle", a, b, n, "flute", exact=True)
            elif n["source"] == "bass":
                put("Bass", a, b, n, "bass", exact=True)

        # Actual source onsets and pitches determine the moving accompaniment.
        piano = [(a, b, n) for a, b, n in local if n["source"] in ("piano", "guitar")]
        for a, b, n in piano:
            if n["confidence"] < .15 or (texture == "sparse" and n["confidence"] < .45):
                continue
            candidates = []
            for p in ("Soprano", "Alto", "Tenor"):
                if cells[p][a//GRID] is not None:
                    continue
                pitch = nearest_pitch(n["pitch"] % 12, p, previous[p])
                if any(cells[q][a//GRID] and
                       ((PARTS.index(q) < PARTS.index(p) and cells[q][a//GRID]["pitch"] < pitch) or
                        (PARTS.index(q) > PARTS.index(p) and cells[q][a//GRID]["pitch"] > pitch))
                       for q in ("Soprano", "Alto", "Tenor", "Bass")):
                    continue
                candidates.append((abs(pitch-previous[p])+.3*abs(pitch-n["pitch"]), p))
            if candidates:
                p = min(candidates)[1]
                release = min(b, a+(TPQ if texture == "sustain" else TPQ//2))
                put(p, a, release, n, "piano")

        # Source backing is distinct from editorial support and never called verified.
        if backing:
            for a, b, n in local:
                if n["role"] not in ("backing", "backing_candidate"):
                    continue
                p = min(("Alto", "Tenor", "Soprano"),
                        key=lambda p: sum(c is not None for c in cells[p][a//GRID:b//GRID]))
                put(p, a, b, n, "vocal_backing")

        harmonies = [h for h in score["harmonies"] if h["start_tick"] < base+dur and h["end_tick"] > base]
        for h in harmonies:
            c = h["candidates"][h["selected"]]
            a, b = max(0, h["start_tick"]-base)//GRID, min(dur, h["end_tick"]-base)//GRID
            if a == b:
                continue
            # Maintain slash bass even where the source bass transcriber is sparse.
            for i in range(a, b):
                if cells["Bass"][i] is None:
                    cells["Bass"][i] = note(nearest_pitch(c["bass_pc"], "Bass", previous["Bass"]), 0, GRID, "harmonic_support", velocity=57, syllable="dum")
            required = c.get("required_pcs", c["pcs"])
            present = {v["pitch"] % 12 for p in ("Soprano", "Alto", "Tenor", "Bass") for v in cells[p][a:b] if v}
            missing = [pc for pc in required if pc not in present]
            for pc in missing + [pc for pc in c["pcs"] if pc not in missing]:
                options = [(sum(v is None for v in cells[p][a:b]), p) for p in ("Tenor", "Alto", "Soprano")]
                free, p = max(options)
                if free == 0:
                    break
                pitch = nearest_pitch(pc, p, previous[p])
                for i in range(a, b):
                    if cells[p][i] is None:
                        cells[p][i] = note(pitch, 0, GRID, "harmonic_support", velocity=48 if texture == "sparse" else 56, syllable="oo")
                previous[p] = pitch

        # Register correction changes octaves, never source pitch classes.
        import itertools
        for i in range(dur//GRID):
            present = [(p, cells[p][i]) for p in ("Soprano", "Alto", "Tenor", "Bass") if cells[p][i]]
            choices = [[x for x in range(RANGES[p][0], RANGES[p][1]+1) if x % 12 == ev["pitch"] % 12] for p, ev in present]
            combinations = [xs for xs in itertools.product(*choices) if all(x >= y for x, y in zip(xs, xs[1:]))]
            if combinations:
                best = min(combinations, key=lambda xs: sum(abs(x-ev["pitch"])*(3 if ev["role"] == "piano" else 1) for x, (_, ev) in zip(xs, present)))
                for pitch, (p, ev) in zip(best, present):
                    cells[p][i] = dict(ev, pitch=pitch)

        # Single performer VP: one articulation per cell, source-led density and fills.
        if vp_style != "silent":
            hits = {}
            for d in evidence.get("drums", []):
                tick = round(seconds_to_tick(evidence, d["time"])/GRID)*GRID-base
                if 0 <= tick < dur and d["strength"] >= 1-density:
                    if vp_style == "sparse" and d["kind"] not in ("K", "pf"):
                        continue
                    index = tick//GRID
                    priority = d["strength"] + (.2 if d["kind"] != "t" else 0)
                    if index not in hits or priority > hits[index][0]:
                        hits[index] = (priority, d)
            for i, (_, d) in hits.items():
                cells["VP"][i] = note(DRUMS[d["kind"]], 0, GRID, "vp_source", [d["id"]],
                                      int(55+35*d["strength"]), d["kind"])
            if hits and vp_style in ("drive", "fill"):
                for i in range(2, len(cells["VP"])-1, 2):
                    if cells["VP"][i] is None:
                        cells["VP"][i] = note(42, 0, GRID, "vp_editorial", velocity=48, syllable="t")
                if vp_style == "fill" and bi == end-1 and len(cells["VP"]) >= 4:
                    for i, syllable in zip(range(len(cells["VP"])-4, len(cells["VP"])-1), ("dm", "ka", "pf")):
                        cells["VP"][i] = note(DRUMS[syllable], 0, GRID, "vp_editorial", velocity=70, syllable=syllable)
            # An audible release / inhalation before the next bar.
            if len(cells["VP"]) > 4:
                cells["VP"][-1] = None

        # Staggered breathing; don't remove an entire source onset.
        for index, p in enumerate(("Soprano", "Alto", "Tenor", "Bass")):
            if (bi+index) % 3 == 2 and len(cells[p]) > 1 and cells[p][-1] == cells[p][-2]:
                cells[p][-1] = None
        for p in PARTS:
            score["score"][p][bi] = events_from_cells(cells[p])
        if bi+1 not in score["arranged_bars"]:
            score["arranged_bars"].append(bi+1)
    score["decisions"].append(dict(tool="arrange_bars", start=start, end=end, texture=texture,
                                    backing=backing, vp_style=vp_style, density=density))
    return {"arranged": list(range(start, end+1))}


def replace_events(score, part, bar, events, reason):
    if part not in PARTS or not 1 <= bar <= len(score["bars"]):
        raise ValueError("Invalid part or bar")
    if not reason.strip():
        raise ValueError("Every edit needs a musical reason")
    allowed = {"pitch", "offset", "duration", "role", "source_ids", "confidence", "velocity", "syllable", "tie_start", "tie_stop"}
    for ev in events:
        if set(ev)-allowed:
            raise ValueError("Unknown event fields")
        for k in ("offset", "duration"):
            if type(ev.get(k)) is not int or ev[k] % GRID or ev[k] < (GRID if k == "duration" else 0):
                raise ValueError("Times must be integer multiples of 120 ticks; duration must be positive")
        if ev.get("pitch") is not None and (type(ev["pitch"]) is not int or not 0 <= ev["pitch"] <= 127):
            raise ValueError("Invalid MIDI pitch")
        if not isinstance(ev.get("source_ids", []), list):
            raise ValueError("source_ids must be a list")
        ev.setdefault("velocity", 64)
        ev.setdefault("syllable", "")
        ev.setdefault("source_ids", [])
        ev.setdefault("confidence", .5)
        ev.setdefault("role", "editorial")
    score["score"][part][bar-1] = fill_rests(deepcopy(events), score["bars"][bar-1]["duration_ticks"])
    score["decisions"].append(dict(tool="replace_events", part=part, bar=bar, reason=reason))
    return {"part": part, "bar": bar, "events": len(events)}


def lengthen_breath_releases(score, minimum_seconds=.12):
    """Enlarge intended short bar-end breaths without deleting a source onset.

    At 126 BPM a sixteenth is 0.119 s, below the phrase validator's threshold.
    Only shorten an untied preceding note that retains at least one grid cell.
    """
    changes = []
    for part in ("Soprano", "Alto", "Tenor", "Bass"):
        for bar, events in zip(score["bars"], score["score"][part]):
            if len(events) < 2:
                continue
            prev, rest = events[-2:]
            if rest["pitch"] is not None or prev["pitch"] is None or prev.get("tie_start"):
                continue
            end = bar["start_tick"] + bar["duration_ticks"]
            release = tick_to_seconds(score, end) - tick_to_seconds(score, end-rest["duration"])
            if release >= minimum_seconds:
                continue
            old = rest["duration"]
            while release < minimum_seconds and prev["duration"] >= 2*GRID:
                prev["duration"] -= GRID
                rest["offset"] -= GRID
                rest["duration"] += GRID
                release = tick_to_seconds(score, end) - tick_to_seconds(score, end-rest["duration"])
            if rest["duration"] != old:
                changes.append(dict(part=part, bar=bar["number"], old_ticks=old,
                                    new_ticks=rest["duration"], seconds=round(release, 4)))
    if changes:
        score["decisions"].append(dict(tool="lengthen_breath_releases", changes=changes,
                                      reason="Make existing breath releases meet the phrase threshold; retain every onset."))
    return changes
