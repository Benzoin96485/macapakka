"""Render an actual seven-part rehearsal package; missing backends fail explicitly."""
from pathlib import Path
import sys

from .music import PARTS, sound_events, tick_to_seconds
from .storage import Store, command, sha256, write_json


def render_audio(score, root, cfg):
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    rc = cfg["render"]
    sr = rc["sample_rate"]
    duration = score["timing"]["anchors"][-1]["seconds"]-score["timing"]["anchors"][0]["seconds"]+2.5
    length = round(duration*sr)
    stems, provenance = {}, {"backend": rc["audio_backend"], "sample_rate": sr,
        "seconds": duration, "original_audio_mixed_in": False, "voices": "Grand Piano",
        "whistle": "Flute", "VP": "GM drum channel 10", "human_listening_review": False}
    bank = None
    if rc["audio_backend"] == "samples":
        from .samples import SampleBank, SR
        if sr != SR:
            raise ValueError("The local sample backend requires sample_rate = 44100")
        if not rc["soundfont"] or not Path(rc["soundfont"]).is_file():
            raise ValueError("Configure render.soundfont with a local SF2/SF3 file")
        bank = SampleBank(Path(rc["soundfont"]))
        provenance.update(soundfont_sha256=bank.hash, engine_note="Local recorded-sample renderer, NOT the MuseScore engine; SF modulators are approximate")
    for p in PARTS:
        print("Rendering", p, flush=True)
        target = root/"audio"/(p+".wav")
        if bank is not None:
            y = np.zeros((length, 2), np.float32)
            origin = score["timing"]["anchors"][0]["seconds"]
            for ev in sound_events(score, p):
                a = tick_to_seconds(score, ev["start"])-origin
                b = tick_to_seconds(score, ev["end"])-origin
                z = bank.tone(128 if p == "VP" else 0, 73 if p == "Whistle" else 0,
                              ev["pitch"], ev["velocity"], max(.04, b-a-.025))
                offset = round(a*sr)
                n = min(len(z), length-offset)
                y[offset:offset+n] += z[:n]
            y *= .32 if p == "VP" else .8 if p == "Whistle" else 12.0
        else:
            temp = root/"audio"/(p+".render.wav")
            if rc["audio_backend"] == "musescore":
                if not rc["musescore"]:
                    raise ValueError("Configure render.musescore executable")
                argv = [rc["musescore"], "-o", temp, root/"scores"/(p+".musicxml")]
            else:
                if not Path(rc["soundfont"]).is_file():
                    raise ValueError("FluidSynth needs render.soundfont")
                argv = [rc["fluidsynth"], "-ni", "-r", str(sr), "-F", temp,
                        rc["soundfont"], root/"midi"/(p+".mid")]
            command(argv, root/"logs"/(p+"-audio.log"), rc["timeout_seconds"])
            z, rate = sf.read(temp, dtype="float32", always_2d=True)
            if rate != sr:
                from math import gcd
                divisor = gcd(sr, rate)
                z = resample_poly(z, sr//divisor, rate//divisor, axis=0)
            if z.shape[1] == 1:
                z = np.repeat(z, 2, axis=1)
            y = np.zeros((length, 2), np.float32)
            y[:min(length, len(z))] = z[:length, :2]
            temp.unlink()
        if not np.isfinite(y).all():
            raise ValueError("Non-finite samples in "+p)
        if sound_events(score, p) and np.max(np.abs(y)) < 1e-8:
            raise ValueError("Unexpected silent render in "+p)
        stems[p] = y
    gains = {"Lead": 1., "Soprano": .75, "Alto": .7, "Tenor": .7, "Bass": .95, "VP": .6, "Whistle": .95}
    mixes = {"Full_Mix": sum(stems[p]*gains[p] for p in PARTS),
             "Without_Lead": sum(stems[p]*gains[p] for p in PARTS if p != "Lead")}
    mixes.update({p: y for p, y in stems.items()})
    for focus in PARTS:
        mixes["Focus_"+focus] = sum(stems[p]*gains[p]*(1.7 if p == focus else .3) for p in PARTS)
    metrics = {}
    # Use a common gain for all solo stems so they remain aligned and remixable.
    common = .91/max(1e-8, max(float(np.max(np.abs(y))) for y in mixes.values()))
    for name, y in mixes.items():
        scale = common if name in PARTS else .91/max(1e-8, float(np.max(np.abs(y))))
        y = y*scale
        target = root/"audio"/(name+".wav")
        sf.write(target, y, sr, subtype="PCM_24")
        metrics[name] = {"peak": float(np.max(np.abs(y))), "gain": scale, "frames": len(y),
                         "rms": float(np.sqrt(np.mean(y*y)))}
        if rc["mp3"]:
            command([rc["ffmpeg"], "-nostdin", "-v", "error", "-y", "-i", target,
                     "-c:a", "libmp3lame", "-b:a", "192k", target.with_suffix(".mp3")],
                    root/"logs"/(name+"-mp3.log"), rc["timeout_seconds"])
    provenance.update(metrics=metrics, sample_ids=bank.used if bank else None, stem_common_gain=common)
    write_json(root/"audio_render.json", provenance)
    return provenance


def main():
    store = Store(sys.argv[1])
    root = store.path(sys.argv[2])
    score, cfg = store.read("score.json"), store.read("config.json")
    render_audio(score, root, cfg)
    if cfg["render"]["pdf_backend"] == "musescore":
        binary = cfg["render"]["musescore"]
        if not binary:
            raise ValueError("Configure render.musescore, or choose the explicit proof PDF backend")
        for label in ["Full_Score"]+list(PARTS):
            output = root/"scores"/(label+".pdf")
            command([binary, "-o", output, root/"scores"/(label+".musicxml")],
                    root/"logs"/(label+"-pdf.log"), cfg["render"]["timeout_seconds"])
            if not output.is_file() or output.stat().st_size < 100:
                raise RuntimeError("MuseScore did not generate "+label)
    else:
        from .storage import worker_env
        command([cfg["render"]["pdf_python"] or sys.executable, "-m", "vibacappella.proof", str(store.root), str(root)],
                root/"logs/proof-pdf.log", cfg["render"]["timeout_seconds"], worker_env())
    # Inspect produced audio rather than assuming an encoder succeeded.
    import soundfile as sf
    expected = score["timing"]["anchors"][-1]["seconds"]-score["timing"]["anchors"][0]["seconds"]+2.5
    for p in (root/"audio").glob("*.wav"):
        if abs(sf.info(p).duration-expected) > .01:
            raise RuntimeError("Rendered audio duration mismatch: "+p.name)
    import json
    for p in (root/"audio").glob("*.mp3"):
        log = root/"logs"/(p.stem+"-probe.json")
        command([cfg["render"]["ffprobe"], "-v", "error", "-show_entries", "format=duration", "-of", "json", p], log, 30)
        if abs(float(json.loads(log.read_text())["format"]["duration"])-expected) > .12:
            raise RuntimeError("Encoded MP3 duration mismatch: "+p.name)
    write_json(root/"render_validation.json", {"passed": True, "wav_files": len(list((root/"audio").glob("*.wav"))),
        "pdf_files": len(list((root/"scores").glob("*.pdf"))), "pdf_backend": cfg["render"]["pdf_backend"],
        "mp3_files": len(list((root/"audio").glob("*.mp3"))),
        "audio_backend": cfg["render"]["audio_backend"], "human_listening_review": False})


if __name__ == "__main__":
    main()
