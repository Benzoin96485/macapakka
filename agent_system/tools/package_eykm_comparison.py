"""Link immutable exports and build a local, synchronized A/B listening page."""
from pathlib import Path
import json,hashlib,shutil,os
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]
base=ROOT/'outputs/EYKM_Sonnet55'
runs=ROOT/'agent_system/runs'
old=runs/'eykm-sonnet55-original';new=runs/'eykm-sonnet55-01'
state=json.loads((new/'state.json').read_text())
assert state['status']=='exported_draft_needs_review'
for name,run in [('original',old),('reviewed',new)]:
 export=run/json.loads((run/'state.json').read_text())['export']
 link=base/name
 if link.is_symlink() or not link.exists():
  temporary=base/(name+"-files")
  shutil.copytree(export,temporary,copy_function=os.link)
  if link.is_symlink():link.unlink()
  temporary.rename(link)
for name,run,pattern in [('original',old,'arranger-*.json'),('reviewed',new,'reviewer-*.json')]:
 audit=base/name/'audit';audit.mkdir(exist_ok=True)
 dialogs=audit/'model_dialogues';dialogs.mkdir(exist_ok=True)
 for source in (run/'agent').glob(pattern):
  target=dialogs/source.name
  if not target.exists():shutil.copy2(source,target)
 for filename in (['events-first-pass.jsonl','stage.json'] if name=='original' else ['events.jsonl','breath_releases.json','config.json','budget.json']):
  if (run/filename).exists():shutil.copy2(run/filename,audit/filename)
a=json.loads((old/'score.json').read_text());b=json.loads((new/'score.json').read_text())
assert a['timing']==b['timing'] and len(a['bars'])==len(b['bars'])==198
changes={part:[i+1 for i,(x,y) in enumerate(zip(a['score'][part],b['score'][part])) if x!=y] for part in a['parts']}
versions={}
for name,run in [('original',old),('reviewed',new)]:
 v=json.loads((run/'validation.json').read_text());assert v['passed']
 versions[name]={'errors':len(v['errors']),'warnings':len(v['warnings']),'warning_types':dict(Counter(x['code'] for x in v['warnings'])),'score_sha256':hashlib.sha256((run/'score.json').read_bytes()).hexdigest()}
summary={'model':'claude-sonnet-5-5','bars':198,'versions':versions,'changed_bars_by_part':changes,'original_definition':'Completed first arranging pass, before breath extension and independent reviewer. Includes original model decisions and tool-driven corrections.','reviewed_definition':'First pass plus 65 deterministic breath extensions, then an independent Sonnet 5.5 review. No human auditory sign-off.','original_model_conversations':str(base/'original/audit/model_dialogues'),'original_event_log':str(base/'original/audit/events-first-pass.jsonl'),'reviewed_run':str(new)}
(base/'comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
meta=json.loads((ROOT/'outputs/EYKM_Acappella_v3/source/arrangement.json').read_text())['metadata']
sections=[];last=None
for m in meta:
 if m['label']!=last:sections.append((m['source_time']-.18,m['bar'],m['label']));last=m['label']
options=''.join(f'<option value="{t:.6f}">第 {bar} 小节 · {label}</option>' for t,bar,label in sections)
rows=''.join(f'<tr><td>{part}</td><td>{len(bars)}</td><td>{", ".join(map(str,bars)) or "无"}</td></tr>' for part,bars in changes.items())
html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EYKM · 两版对比</title>
<style>body{font:17px system-ui;line-height:1.6;max-width:1100px;margin:40px auto;padding:0 24px;background:#f7f5ef;color:#203735}h1{font-size:36px}section{background:white;border:1px solid #d9ddd4;border-radius:18px;padding:24px;margin:20px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}audio{width:100%}button,select{font:inherit;padding:9px 16px;border:1px solid #7e9790;border-radius:8px;background:#edf4ef;color:#203735;cursor:pointer}a{color:#166c62}table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #ddd;padding:10px;text-align:left;vertical-align:top}td:last-child{font-size:14px}small{color:#536761}@media(max-width:700px){.grid{grid-template-columns:1fr}}</style>
<h1>EYKM · Sonnet 5.5 两版对比</h1><p>198 小节 · Lead + SATB + VP + Whistle · 全曲编配草稿</p><p>两版使用同一时间轴和采样音源。五个人声以钢琴代奏，口哨以长笛代奏，VP 以鼓组代奏；没有混入原录音。</p>
<section><label>跳转段落 <select id="section">OPTIONS</select></label><p><button onclick="switchTo('a')">同位置听原始版</button> <button onclick="switchTo('b')">同位置听审校版</button></p><div class="grid"><div><h2>系统原始版</h2><p>第一轮完整输出。保留原始修订与警告，未加入后续呼吸修正和独立审校。</p><audio id="a" controls preload="metadata" src="original/audio/Full_Mix.mp3"></audio><p><a href="original/review.html">全部分谱与排练音轨</a> · <a href="original/scores/Full_Score.pdf">总谱 PDF</a> · <a href="original/scores/Full_Score.musicxml">MusicXML</a></p><small>零结构错误 · OLDWARN 条音乐性警告</small></div><div><h2>审校后版本</h2><p>延长 65 处预留呼吸，并由独立 Sonnet 5.5 审校上下文复查全曲。尚未真人听审。</p><audio id="b" controls preload="metadata" src="reviewed/audio/Full_Mix.mp3"></audio><p><a href="reviewed/review.html">全部分谱与排练音轨</a> · <a href="reviewed/scores/Full_Score.pdf">总谱 PDF</a> · <a href="reviewed/scores/Full_Score.musicxml">MusicXML</a></p><small>零结构错误 · NEWWARN 条音乐性警告</small></div></div></section>
<section><h2>哪些小节发生了变化</h2><table><tr><th>声部</th><th>小节数</th><th>小节编号</th></tr>ROWS</table><p><a href="comparison.json">完整对比记录与原始日志位置</a></p><small>检查通过不等于原曲逐音准确或真人可演唱性已确认。来源转写、歌词位置、复杂节奏和最终音色仍需听审。</small></section>
<script>const a=document.getElementById('a'),b=document.getElementById('b');let last=a;for(const x of [a,b]){x.addEventListener('play',()=>{(x===a?b:a).pause();last=x;});}function switchTo(id){const target=document.getElementById(id),t=last.currentTime;last.pause();target.currentTime=t;last=target;target.play().catch(()=>{});}document.getElementById('section').addEventListener('change',e=>{const t=Number(e.target.value);a.currentTime=t;b.currentTime=t;});</script></html>'''
html=html.replace('OPTIONS',options).replace('OLDWARN',str(versions['original']['warnings'])).replace('NEWWARN',str(versions['reviewed']['warnings'])).replace('ROWS',rows)
(base/'index.html').write_text(html)
print(json.dumps(summary,ensure_ascii=False))
