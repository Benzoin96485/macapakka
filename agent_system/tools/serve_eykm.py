"""Local-only preview server with HTTP byte ranges for audio seeking."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]/'outputs/EYKM_Sonnet55'
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**k):super().__init__(*a,directory=str(ROOT),**k)
    def send_head(self):
        self.remaining=None
        path=Path(self.translate_path(self.path));header=self.headers.get('Range')
        if not header or not path.is_file():return super().send_head()
        size=path.stat().st_size;m=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
        if not m or not any(m.groups()):self.send_error(416);return None
        start=int(m[1]) if m[1] else max(0,size-int(m[2]))
        end=min(size-1,int(m[2])) if m[1] and m[2] else size-1
        if start>end or start>=size:self.send_error(416);return None
        f=path.open('rb');f.seek(start);self.remaining=end-start+1
        self.send_response(206);self.send_header('Content-Type',self.guess_type(str(path)))
        self.send_header('Accept-Ranges','bytes');self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length',str(self.remaining));self.end_headers();return f
    def end_headers(self):
        self.send_header('Cache-Control','no-cache');super().end_headers()
    def copyfile(self,source,out):
        if self.remaining is None:return super().copyfile(source,out)
        remaining=self.remaining
        while remaining:
            chunk=source.read(min(65536,remaining))
            if not chunk:break
            out.write(chunk);remaining-=len(chunk)
ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
