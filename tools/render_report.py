"""Render the archive's Markdown report to an offline HTML reading copy."""
from pathlib import Path
import html, re

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'docs/TECHNICAL_REPORT_ZH.md'
lines=source.read_text().splitlines()
def inline(s):
    return re.sub(r'`([^`]+)`',lambda m:'<code>'+m[1]+'</code>',html.escape(s))
out=[]; toc=[]; i=0; sec=0
while i<len(lines):
    line=lines[i]
    if not line.strip(): i+=1; continue
    if line.startswith('```'):
        buf=[];i+=1
        while i<len(lines) and not lines[i].startswith('```'):buf.append(lines[i]);i+=1
        out.append('<pre><code>'+html.escape('\n'.join(buf))+'</code></pre>');i+=1;continue
    m=re.match(r'^(#{1,3}) (.*)$',line)
    if m:
        level=len(m[1]);sec+=1;anchor='section-'+str(sec)
        out.append(f'<h{level} id="{anchor}">{inline(m[2])}</h{level}>')
        if level==2:toc.append(f'<a href="#{anchor}">{html.escape(m[2])}</a>')
        i+=1;continue
    if line.startswith('|'):
        rows=[]
        while i<len(lines) and lines[i].startswith('|'):
            cells=[x.strip() for x in lines[i].strip().strip('|').split('|')]
            if not all(re.fullmatch(r':?-+:?',x) for x in cells):rows.append(cells)
            i+=1
        table='<thead><tr>'+''.join('<th>'+inline(c)+'</th>' for c in rows[0])+'</tr></thead><tbody>'
        table+=''.join('<tr>'+''.join('<td>'+inline(c)+'</td>' for c in row)+'</tr>' for row in rows[1:])+'</tbody>'
        out.append('<div class="table"><table>'+table+'</table></div>');continue
    buf=[]
    while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','```')):
        buf.append(lines[i]);i+=1
    out.append('<p>'+inline(' '.join(buf))+'</p>')
css='''
:root{color-scheme:light;--ink:#173342;--muted:#536a77;--accent:#176477}
*{box-sizing:border-box}body{margin:0;background:#eef3f5;color:var(--ink);font:16px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
.layout{max-width:1320px;margin:auto;display:grid;grid-template-columns:250px minmax(0,1fr);gap:28px;padding:34px 26px}
nav{position:sticky;top:24px;align-self:start;max-height:92vh;overflow:auto;font-size:13px}nav strong{display:block;font-size:16px;margin-bottom:12px}nav a{display:block;padding:5px 0;color:var(--muted);text-decoration:none}nav a:hover{color:var(--accent)}
main{min-width:0;background:white;border-radius:12px;padding:44px 52px;box-shadow:0 5px 30px #1634410b}h1{font-size:29px;line-height:1.4;margin:0 0 24px}h2{font-size:23px;line-height:1.5;margin-top:48px;border-top:2px solid #d9e6eb;padding-top:22px;scroll-margin-top:20px}h3{font-size:18px;margin-top:30px}p{margin:16px 0}
code{font:13px/1.7 ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere;background:#eef3f5;padding:2px 4px;border-radius:3px}pre{background:#edf3f6;padding:18px;border-radius:8px;white-space:pre-wrap;overflow-wrap:anywhere}pre code{padding:0;background:none}
.table{overflow:auto;margin:24px 0}table{width:100%;border-collapse:collapse;font-size:13.5px;line-height:1.7}th{text-align:left;background:#176477;color:white;padding:10px 12px}td{padding:10px 12px;border-bottom:1px solid #dde7ec;vertical-align:top}tr:nth-child(even){background:#f5f8fa}td code{font-size:12px}
footer{margin-top:36px;color:var(--muted);font-size:13px}@media(max-width:900px){.layout{display:block;padding:12px}nav{position:static;max-height:none;margin:12px 8px 24px}main{padding:24px}h1{font-size:25px}}
@media print{body{background:white;font-size:10pt}.layout{display:block;padding:0;max-width:none}nav{display:none}main{padding:0;box-shadow:none}h1{font-size:22pt}h2{font-size:16pt;break-after:avoid}h3{break-after:avoid}table{font-size:9pt}tr{break-inside:avoid}pre{font-size:9pt}a{color:inherit}footer{display:none}@page{size:A4;margin:18mm}}
'''
page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Everytime You Kissed Me 第二版技术报告</title><style>'+css+'</style></head><body><div class="layout"><nav aria-label="目录"><strong>技术报告 · 2026.11.03</strong>'+''.join(toc)+'</nav><main>'+''.join(out)+'<footer>本页可离线阅读或使用浏览器打印。可编辑正文见同目录 TECHNICAL_REPORT_ZH.md。</footer></main></div></body></html>'
target=source.with_suffix('.html');target.write_text(page)
print(target)
