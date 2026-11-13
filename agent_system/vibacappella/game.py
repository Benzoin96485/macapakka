"""Optional GAME 1.0.3 ONNX singing-note adapter, adapted from the Claude workflow.
Model files are supplied separately; no third-party weights are bundled.
"""
import json
from pathlib import Path
import numpy as np
import librosa
import onnxruntime as ort

def slice_on_silence(y, sr, thr_db=-40, min_sil=0.3, max_len=25.0):
    """Cut the stem at silent gaps (like GAME's slicer); long chunks are cut at their quietest frame."""
    hop = int(0.01 * sr)
    rms = librosa.feature.rms(y=y, frame_length=4 * hop, hop_length=hop)[0]
    db = 20 * np.log10(rms + 1e-9)
    loud = db > thr_db
    chunks, i, n = [], 0, len(loud)
    while i < n:
        while i < n and not loud[i]:
            i += 1
        if i >= n:
            break
        j = i
        while j < n:
            if not loud[j]:
                k = j
                while k < n and not loud[k]:
                    k += 1
                if (k - j) * 0.01 >= min_sil or k >= n:
                    break
                j = k
            else:
                j += 1
        a, b = max(0, i - 10), min(n, j + 10)
        while (b - a) * 0.01 > max_len:   # split long chunks at the quietest point of their middle half
            lo, hi = a + (b - a) // 4, a + 3 * (b - a) // 4
            cut = lo + int(np.argmin(db[lo:hi]))
            chunks.append((a, cut)); a = cut
        if (b - a) * 0.01 >= 0.3:
            chunks.append((a, b))
        i = j
    return [(a * hop, b * hop) for a, b in chunks]


def transcribe_chunk(w):
    dur = np.array([len(w) / SR], dtype=np.float32)
    x_seg, x_est, maskT = sess['encoder'].run(None, {'waveform': w[None].astype(np.float32), 'duration': dur})
    known = sess['dur2bd'].run(None, {'durations': dur[None], 'maskT': maskT})[0]
    prev = known
    for t in TS:
        prev = sess['segmenter'].run(None, {
            'x_seg': x_seg, 'language': np.array([LANG], dtype=np.int64), 'known_boundaries': known,
            'prev_boundaries': prev, 't': np.array([t], dtype=np.float32), 'maskT': maskT,
            'threshold': np.array(SEG_THR, dtype=np.float32), 'radius': np.array(RADIUS, dtype=np.int64)})[0]
    durations, maskN = sess['bd2dur'].run(None, {'boundaries': prev, 'maskT': maskT})
    presence, scores = sess['estimator'].run(None, {
        'x_est': x_est, 'boundaries': prev, 'maskT': maskT, 'maskN': maskN,
        'threshold': np.array(EST_THR, dtype=np.float32)})
    m = maskN[0]
    return durations[0][m], presence[0][m], scores[0][m]


def transcribe_game(wav, model_dir, language="en"):
    global SR, STEP, sess, TS, SEG_THR, RADIUS, EST_THR, LANG
    md = Path(model_dir)
    if not model_dir or not (md / "config.json").is_file():
        raise ValueError("game_model_dir must contain the GAME ONNX models and config.json")
    cfg = json.loads((md / "config.json").read_text())
    SR, STEP = cfg["samplerate"], cfg["timestep"]
    sess = {n: ort.InferenceSession(str(md / (n + ".onnx")), providers=["CPUExecutionProvider"])
            for n in ("encoder", "dur2bd", "segmenter", "bd2dur", "estimator")}
    TS, SEG_THR, RADIUS, EST_THR = [i / 8 for i in range(8)], .2, 2, .2
    LANG = cfg["languages"][language]
    y, _ = librosa.load(wav, sr=SR, mono=True)
    result = []
    for a, b in slice_on_silence(y, SR):
        durations, presence, scores = transcribe_chunk(y[a:b])
        t = a / SR
        for duration, present, pitch in zip(durations, presence, scores):
            end = min(len(y)/SR, t + float(duration))
            if present and end > t and np.isfinite(pitch):
                result.append(dict(id=f"game:{len(result)}", source="lead", role="lead",
                    instrument="vocals", start=float(t), end=float(end), pitch=int(round(float(pitch))),
                    confidence=.7, confidence_note="Provisional, not a calibrated model probability"))
            t += float(duration)
    return result
