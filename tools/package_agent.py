"""Package reusable agent source without recordings, credentials, caches or models."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "agent_system"
FILES = [PACKAGE / "pyproject.toml", PACKAGE / "README.md", PACKAGE / ".gitignore"]
for directory, pattern in (("vibacappella", "*.py"), ("tests", "*.py"),
                           ("examples", "*.toml"), ("docs", "*.md")):
    FILES.extend(sorted((PACKAGE / directory).glob(pattern)))
manifest = {str(p.relative_to(PACKAGE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in FILES}
archive = ROOT / "outputs/Vibacappella_Agent_0.1_Source.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
    for path in FILES:
        z.write(path, "vibacappella-agent/" + str(path.relative_to(PACKAGE)))
    z.writestr("vibacappella-agent/SOURCE_MANIFEST.json", json.dumps(manifest, indent=2))
with zipfile.ZipFile(archive) as z:
    bad = z.testzip()
    if bad:
        raise RuntimeError("Corrupt archive member: " + bad)
print(archive)
print(f"{len(FILES)} source/config/doc files; {archive.stat().st_size} bytes")
