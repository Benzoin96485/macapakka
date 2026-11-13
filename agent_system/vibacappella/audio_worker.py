"""Demucs / Basic Pitch / spectral evidence adapters. Run in the audio environment."""
import math
from pathlib import Path
import sys

from .music import TPQ, GRID, QUALITIES, NAMES, check_evidence, seconds_to_tick
from .storage import Store, command, read_json, sha256


def build_timing(y, sr, cfg):
    import librosa
    import numpy as np
    duration = len(y)/sr
    explicit = cfg["tempo"] > 0
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=512, units="time")
    tempo = float(np.asarray(tempo).reshape(-1)[0])
    if not np.isfinite(tempo) or tempo < 30:
        tempo = 120.0
    if explicit:
        tempo = cfg["tempo"]
    start = cfg["first_downbeat_seconds"]
    if not 0 <= start < duration:
        raise ValueError("first_downbeat_seconds lies outside the audio")
    meter = cfg["meter"]
    alerts = []
    if meter == "auto":
        # Accent periodicity is only a hypothesis, never a confident downbeat model.
        strength = librosa.onset.onset_strength(y=y, sr=sr)
        frames = np.clip(librosa.time_to_frames(beats, sr=sr), 0, len(strength)-1)
        accents = strength[frames]
        candidates = []
        for m in (3, 4):
            means = [float(accents[i::m].mean()) if len(accents[i::m]) else 0 for i in range(m)]
            candidates.append((max(means)/(sum(means)/m+1e-9), m))
        numerator, denominator = max(candidates)[1], 4
        alerts.append("Meter/downbeat estimated from accent periodicity; verify pickups, compound meter and rubato.")
    else:
        numerator, denominator = map(int, meter.split("/"))
    if denominator not in (2, 4, 8, 16) or not 1 <= numerator <= 12:
        raise ValueError("Unsupported meter")
    bar_ticks = int(numerator*4/denominator*TPQ)
    if explicit or len(beats) < 4:
        seconds = np.arange(start, duration, 60/tempo).tolist()
    else:
        seconds = [start] + [float(t) for t in beats if t > start + .2*60/tempo]
        # Preserve local beat timing; large gaps remain reviewable in the source map.
        alerts.append("Beat tracking is quarter-note oriented; verify half/double tempo before arranging.")
    if len(seconds) < 2:
        seconds = [start, duration]
    elif duration-seconds[-1] > .15*60/tempo:
        seconds.append(duration)
    else:
        seconds[-1] = duration
    total_ticks = (len(seconds)-1)*TPQ
    # The final partial beat is retained as a quarter of notated time, with its true duration.
    bars = []
    for n, tick in enumerate(range(0, total_ticks, bar_ticks), 1):
        bars.append(dict(number=n, start_tick=tick, duration_ticks=min(bar_ticks, total_ticks-tick),
                         numerator=numerator, denominator=denominator, section="auto"))
    return {"anchors": [{"tick": i*TPQ, "seconds": float(t)} for i, t in enumerate(seconds)]}, bars, alerts


def transcribe(path, source, backend):
    import librosa
    import numpy as np
    import scipy.signal
    if backend == "basic_pitch":
        # Basic Pitch 0.4 imports this former SciPy alias.
        if not hasattr(scipy.signal, "gaussian"):
            scipy.signal.gaussian = scipy.signal.windows.gaussian
        from basic_pitch.inference import Model, predict
        from basic_pitch import ICASSP_2022_MODEL_PATH
        onnx = Path(ICASSP_2022_MODEL_PATH).parent / "nmp.onnx"
        if not onnx.exists():
            raise FileNotFoundError("Install Basic Pitch ONNX model assets; nmp.onnx was not found")
        _, _, rows = predict(str(path), Model(str(onnx)), onset_threshold=.5, frame_threshold=.3,
                             minimum_note_length=90, minimum_frequency=30 if source == "bass" else 60,
                             maximum_frequency=2200, multiple_pitch_bends=False)
        data = [(float(a), float(b), int(p), float(c)) for a, b, p, c, *_ in rows]
    elif backend == "pyin":
        y, sr = librosa.load(path, sr=22050)
        f0, voiced, probability = librosa.pyin(y, sr=sr, fmin=35 if source == "bass" else 65,
                                             fmax=1200, frame_length=2048, hop_length=256)
        pitches = np.where(voiced, np.rint(librosa.hz_to_midi(np.nan_to_num(f0, nan=440))), -1).astype(int)
        data = []
        i = 0
        while i < len(pitches):
            j = i+1
            while j < len(pitches) and pitches[j] == pitches[i]:
                j += 1
            if pitches[i] >= 0 and (j-i)*256/sr >= .09:
                data.append((i*256/sr, min(len(y)/sr, j*256/sr), int(pitches[i]), float(np.mean(probability[i:j]))))
            i = j
    else:
        raise ValueError("transcriber must be basic_pitch or pyin")
    return [dict(id=f"{source}:{i}", source=source, start=a, end=b, pitch=p,
                 confidence=max(0.0, min(1.0, c)), instrument=source, role="candidate")
            for i, (a, b, p, c) in enumerate(sorted(data)) if b > a]


def classify_vocals(notes):
    """Provisional monophonic lead, then non-unison sustained backing candidates."""
    vocals = [n for n in notes if n["source"] == "vocals"]
    previous = 67
    chosen = []
    for n in sorted(vocals, key=lambda n: (round(n["start"]/.1), -n["confidence"])):
        near = [v for v in vocals if abs(v["start"]-n["start"]) < .09 and 48 <= v["pitch"] <= 84]
        if not near:
            continue
        best = max(near, key=lambda v: v["confidence"]-.015*abs(v["pitch"]-previous))
        if best["id"] not in chosen:
            best["role"] = "lead"
            chosen.append(best["id"])
            previous = best["pitch"]
    lead = [n for n in vocals if n["role"] == "lead"]
    for n in vocals:
        if n["role"] != "lead" and n["end"]-n["start"] >= .35:
            overlaps = [v for v in lead if v["start"] < n["end"] and v["end"] > n["start"]]
            if not any((n["pitch"]-v["pitch"]) % 12 == 0 or n["pitch"]-v["pitch"] in (19, 28) for v in overlaps):
                n["role"] = "backing_candidate"


def drum_evidence(path):
    import librosa
    import numpy as np
    from scipy.signal import find_peaks
    y, sr = librosa.load(path, sr=22050)
    spec = np.abs(librosa.stft(y, n_fft=1024, hop_length=128))
    f = librosa.fft_frequencies(sr=sr, n_fft=1024)
    result = []
    for kind, lo, hi in (("K", 30, 130), ("pf", 180, 1600), ("t", 5000, 11000)):
        flux = np.r_[0, np.maximum(0, np.diff(np.log1p(100*spec[(f>=lo)&(f<hi)]), axis=1)).sum(axis=0)]
        scale = float(np.percentile(flux, 98))
        if scale < 1e-5:
            continue
        peaks, _ = find_peaks(flux, height=scale*.3, prominence=scale*.2, distance=int(.09*sr/128))
        for i in peaks:
            result.append(dict(id=f"drums:{kind}:{int(i)}", time=float(i*128/sr), kind=kind,
                               strength=float(min(1, flux[i]/scale))))
    return sorted(result, key=lambda x: x["time"])


def harmonic_candidates(e):
    from .music import tick_to_seconds
    result = []
    pitched = [n for n in e["notes"] if n["source"] not in ("vocals", "lead", "drums")]
    for bar in e["bars"]:
        # Half-bar segments retain within-bar harmonic rhythm and inversions.
        half = max(GRID, round(bar["duration_ticks"]/2/GRID)*GRID)
        for start in range(bar["start_tick"], bar["start_tick"]+bar["duration_ticks"], half):
            end = min(start+half, bar["start_tick"]+bar["duration_ticks"])
            a, b = tick_to_seconds(e, start), tick_to_seconds(e, end)
            weights, bass = [0.0]*12, [0.0]*12
            for n in pitched:
                overlap = max(0, min(b, n["end"])-max(a, n["start"])) * n["confidence"]
                weights[n["pitch"] % 12] += overlap
                if n["source"] == "bass":
                    bass[n["pitch"] % 12] += overlap
            total = sum(weights)
            bass_pc = max(range(12), key=lambda p: bass[p]) if sum(bass) else None
            candidates = []
            for root in range(12):
                for quality, intervals in QUALITIES.items():
                    pcs = [(root+d) % 12 for d in intervals]
                    present = sum(weights[p] for p in pcs)/(total+1e-9)
                    absent = sum(weights[p] < .04*max(total, .01) for p in pcs)
                    score = present-.06*absent-.025*max(0, len(pcs)-3)
                    if bass_pc is not None:
                        score += .1 if bass_pc == root else .05 if bass_pc in pcs else -.08
                    color = [(root+d) % 12 for d in intervals if d not in (0, 7)]
                    symbol = NAMES[root]+quality
                    if bass_pc is not None and bass_pc != root and bass_pc in pcs:
                        symbol += "/"+NAMES[bass_pc]
                    candidates.append(dict(symbol=symbol, pcs=pcs, required_pcs=color,
                                           bass_pc=bass_pc if bass_pc in pcs else root, score=round(score, 4)))
            candidates.sort(key=lambda c: c["score"], reverse=True)
            result.append(dict(id=f"h:{start}", start_tick=start, end_tick=end, locked=False,
                               confidence="low" if total < .08 else "provisional",
                               chroma=[round(v, 4) for v in weights], candidates=candidates[:5]))
    return result


def main():
    import librosa
    import soundfile as sf
    store = Store(sys.argv[1])
    cfg = store.read("config.json")
    ac = cfg["analysis"]
    inp = store.path("work/input.wav")
    info = sf.info(inp)
    if info.duration > ac["max_audio_seconds"]:
        raise ValueError("Audio exceeds configured maximum duration")
    alerts = []
    if ac["separation"] == "demucs":
        command([sys.executable, "-m", "demucs", "-n", ac["demucs_model"], "-d", ac["device"],
                 "--float32", "--out", store.path("work/separated"), inp],
                store.path("logs/demucs.log"), ac["timeout_seconds"])
        stems = store.path("work/separated") / ac["demucs_model"] / "input"
        paths = {p.stem: p for p in stems.glob("*.wav")}
    elif ac["separation"] == "provided":
        stems = Path(ac["stems_dir"]).expanduser().resolve()
        paths = {p.stem: p for p in stems.glob("*.wav") if p.stem in ("piano", "vocals", "bass", "other", "guitar", "drums", "flute", "lead", "backing")}
        if not paths:
            raise ValueError("No recognized .wav stems found in stems_dir")
    else:
        paths = {"mix": inp}
        alerts.append("No source separation: piano/backing/flute attribution is unavailable; transcription is a rough draft.")
    provenance = {}
    for name, p in paths.items():
        if abs(sf.info(p).duration-info.duration) > .1:
            raise ValueError(f"Stem duration differs from original: {name}. Supply stems with a shared zero-time origin.")
        provenance[name] = {"sha256": sha256(p), "duration": sf.info(p).duration}
    y, sr = librosa.load(inp, sr=22050)
    timing, bars, timing_alerts = build_timing(y, sr, ac)
    notes = []
    for name, path in paths.items():
        if name == "drums":
            continue
        cache = store.path(f"work/transcriptions/{name}.json")
        if cache.exists():
            rows = read_json(cache)
        else:
            print(f"Transcribing {name}", flush=True)
            rows = transcribe(path, name, ac["transcriber"])
            for n in rows:
                n["end"] = min(n["end"], info.duration)
                if name == "flute":
                    n.update(role="flute", instrument_confidence=1.0, attribution="provided_flute_stem")
                elif name in ("lead", "backing"):
                    n["role"] = name
            store.write(f"work/transcriptions/{name}.json", rows)
        notes += rows
    if ac["lead_backend"] == "game" and "vocals" in paths:
        from .game import transcribe_game
        lead = transcribe_game(paths["vocals"], ac["game_model_dir"], ac["game_language"])
        for n in notes:
            if n["source"] == "vocals":
                overlap = [v for v in lead if v["start"] < n["end"] and v["end"] > n["start"]]
                if n["end"]-n["start"] >= .35 and not any((n["pitch"]-v["pitch"]) % 12 == 0 or n["pitch"]-v["pitch"] in (19, 28) for v in overlap):
                    n["role"] = "backing_candidate"
        notes += lead
    elif "lead" not in paths:
        classify_vocals(notes)
        alerts.append("Lead and backing separation is provisional; a singing-specific model or corrected note evidence improves it.")
    drums = drum_evidence(paths["drums"]) if "drums" in paths else []
    if "flute" not in paths:
        alerts.append("No verified flute source. Whistle stays silent until flute note IDs are supplied in corrected evidence; 'other' is not assumed to be flute.")
    e = dict(schema_version=1, audio_sha256=store.read("state.json")["input_sha256"],
             duration_seconds=info.duration, timing=timing, bars=bars, notes=notes, drums=drums,
             alerts=alerts+timing_alerts, provenance={"stems": provenance, "transcriber": ac["transcriber"],
             "human_review": False, "separation": ac["separation"]})
    e["harmonies"] = harmonic_candidates(e)
    check_evidence(e)
    store.write("evidence.json", e)
    print(f"Evidence complete: {len(notes)} notes, {len(bars)} bars", flush=True)


if __name__ == "__main__":
    main()
