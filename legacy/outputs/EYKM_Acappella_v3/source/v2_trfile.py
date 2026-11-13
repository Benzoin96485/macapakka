"""Read a transcription file ('BAR: tokens' lines, '#' only as line-start comment)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mxl import parse
def read_tr(path, drums=False):
    out = {}
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        bar, toks = line.split(':', 1)
        out[int(bar)] = parse(toks, drums=drums)[0]
    return out
if __name__ == '__main__':
    for p in sys.argv[1:]:
        d = read_tr(p); print(p, 'ok', len(d), 'bars', min(d), '-', max(d))
