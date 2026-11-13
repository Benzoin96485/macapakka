"""Package the v3 deliverables and refresh project checksums after validation."""
from pathlib import Path
import hashlib, json, zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/EYKM_Acappella_v3'
validation=json.loads((OUT/'source/validation.json').read_text())
if not validation['pass_all']:raise SystemExit('Validation is not passing; no release packaged.')
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
files=[p for p in sorted(OUT.rglob('*')) if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and not p.name.startswith('.') and p.name!='MANIFEST.sha256']
(OUT/'MANIFEST.sha256').write_text(''.join(f'{digest(p)}  {p.relative_to(OUT)}\n' for p in files))
archive=ROOT/'outputs/EYKM_Acappella_Rehearsal_v3.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files+[OUT/'MANIFEST.sha256']:z.write(p,p.relative_to(OUT.parent))
with zipfile.ZipFile(archive) as z:
    bad=z.testzip()
    if bad:raise RuntimeError('Bad ZIP member '+bad)
historical=ROOT/'docs/MANIFEST_v2_ARCHIVED.sha256'
if not historical.exists():historical.write_bytes((ROOT/'MANIFEST.sha256').read_bytes())
files=[p for p in sorted(ROOT.rglob('*')) if p.is_file() and not p.is_symlink()
       and p!=ROOT/'MANIFEST.sha256' and '__pycache__' not in p.parts
       and not any(s.startswith('.') for s in p.relative_to(ROOT).parts)]
(ROOT/'MANIFEST.sha256').write_text(''.join(f'{digest(p)}  {p.relative_to(ROOT)}\n' for p in files))
print('Release package:',archive,archive.stat().st_size,'bytes')
print('Project checksum files:',len(files))
