"""Build all v2 deliverables: MusicXML -> MuseScore (.mscz, chord-symbol playback off) -> PDF / MIDI / MP3,
plus per-part practice MP3s."""
import os, subprocess, sys, time, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORK = f'{ROOT}/_work'
MS = '/Applications/MuseScore 4.app/Contents/MacOS/mscore'
PY = f'{WORK}/venv/bin/python'
GEN = f'{WORK}/scripts/arrange_v2.py'


def ms(out, src, tries=4):
    # MuseScore 4 CLI occasionally aborts when launched back-to-back; retry after a pause
    for i in range(tries):
        if os.path.exists(out):
            os.remove(out)
        r = subprocess.run([MS, '-o', out, src], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(out) and os.path.getsize(out) > 0:  # it sometimes aborts on exit after writing
            return
        time.sleep(3 + 2 * i)
    raise RuntimeError(f'MuseScore failed: {src} -> {out}')


def to_mscz(xml, mscz):
    """Import MusicXML into MuseScore and switch off chord-symbol playback."""
    tmpdir = f'{WORK}/tmp_mscz'
    os.makedirs(tmpdir, exist_ok=True)
    tmp = os.path.join(tmpdir, os.path.basename(mscz))
    ms(tmp, xml)
    with zipfile.ZipFile(tmp) as zin, zipfile.ZipFile(mscz, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith('.mscx'):
                data = data.replace(b'<Harmony>', b'<Harmony>\n            <play>0</play>')
            zout.writestr(item, data)
    os.remove(tmp)


def main():
    base = f'{ROOT}/v2/EYKM_acappella_v2'
    os.makedirs(f'{ROOT}/v2', exist_ok=True)
    subprocess.run([PY, GEN, base + '.musicxml'], check=True)
    to_mscz(base + '.musicxml', base + '.mscz')
    for ext in ('pdf', 'mid'):
        ms(f'{base}.{ext}', base + '.mscz')
    # audio: render every part alone, then mix with ffmpeg
    sdir = f'{WORK}/stems_v2'
    os.makedirs(sdir, exist_ok=True)
    subprocess.run([PY, GEN, sdir, 'stems'], check=True)
    for name in STEMS:
        ms(f'{sdir}/{name}.wav', f'{sdir}/stem_{name}.musicxml')
    mix(f'{base}_demo.mp3', DEMO_DB)
    if '--no-practice' in sys.argv:
        return
    pdir = f'{ROOT}/v2/practice'
    os.makedirs(pdir, exist_ok=True)
    for focus in STEMS:
        gains = {n: (6 if n == focus else (-6 if n == 'VP' else -9)) for n in STEMS}
        mix(f'{pdir}/EYKM_v2_practice_{focus}.mp3', gains)
        print('practice track', focus)
    for name in STEMS:  # rendered WAVs are large and reproducible
        os.remove(f'{sdir}/{name}.wav')


STEMS = ['Whistle', 'Lead', 'Soprano', 'Alto', 'Tenor', 'Bass', 'VP']
DEMO_DB = {'Whistle': -1, 'Lead': 0, 'Soprano': -4, 'Alto': -4, 'Tenor': -4, 'Bass': -2, 'VP': -5}


def mix(out, gains):
    sdir = f'{WORK}/stems_v2'
    cmd = ['ffmpeg', '-v', 'error', '-y']
    for n in STEMS:
        cmd += ['-i', f'{sdir}/{n}.wav']
    chains = [f'[{i}:a]volume={gains[n]}dB[a{i}]' for i, n in enumerate(STEMS)]
    ins = ''.join(f'[a{i}]' for i in range(len(STEMS)))
    flt = ';'.join(chains) + f';{ins}amix=inputs={len(STEMS)}:duration=longest:normalize=0,alimiter=limit=0.9[m]'
    cmd += ['-filter_complex', flt, '-map', '[m]', '-c:a', 'libmp3lame', '-b:a', '192k', out]
    subprocess.run(cmd, check=True)


if __name__ == '__main__':
    main()
