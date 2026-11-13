"""Verify archive files without changing them; no third-party packages required."""
from pathlib import Path
import hashlib,json,os,sys

ROOT=Path(__file__).resolve().parents[1]
errors=[];checked=0
for line in (ROOT/'MANIFEST.sha256').read_text().splitlines():
    expected,name=line.split('  ',1);path=ROOT/name
    if not path.is_file() or path.is_symlink():errors.append(name+': missing or type changed');continue
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    if h.hexdigest()!=expected:errors.append(name+': SHA-256 mismatch')
    checked+=1
for item in json.loads((ROOT/'docs/ORIGINAL_FILES.json').read_text())['symlinks']:
    path=ROOT/item['path']
    if not path.is_symlink() or os.readlink(path)!=item['target']:errors.append(item['path']+': symlink mismatch')
if errors:
    print('\n'.join(errors));sys.exit(1)
print(f'PASS: {checked} file hashes and all recorded symlinks match.')
