"""A local listening/review entry point with honest provenance and unresolved issues."""
from collections import Counter
from html import escape
import json

from .storage import write_json
from .music import PARTS


def create_report(store, root):
    score, evidence, validation = store.read("score.json"), store.read("evidence.json"), store.read("validation.json")
    render = json.loads((root/"audio_render.json").read_text())
    counts = Counter(ev["role"] for bars in score["score"].values() for bar in bars for ev in bar if ev["pitch"] is not None)
    report = {"status": "exported_draft_needs_review", "human_listening_review": False,
              "bars": len(score["bars"]), "roles": dict(counts), "source_alerts": evidence.get("alerts", []),
              "validation": validation, "agent_reviews": score["review_notes"],
              "audio_backend": render["backend"], "input_sha256": score["source_sha256"]}
    write_json(root/"review.json", report)
    audio = "mp3" if (root/"audio/Full_Mix.mp3").exists() else "wav"
    rows = "".join(f'<tr><td>{p}</td><td><a href="scores/{p}.pdf">PDF</a> · <a href="scores/{p}.musicxml">MusicXML</a></td>'
                   f'<td><audio controls preload="none" src="audio/{p}.{audio}"></audio></td>'
                   f'<td><audio controls preload="none" src="audio/Focus_{p}.{audio}"></audio></td></tr>' for p in PARTS)
    warnings = "".join("<li>"+escape(a)+"</li>" for a in evidence.get("alerts", []))
    html = f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(score['title'])} · Review</title><style>body{{font:16px system-ui;max-width:1200px;margin:40px auto;padding:0 20px;color:#17313a;background:#f7f6f0}}table{{border-collapse:collapse;width:100%}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #cad6d8}}audio{{max-width:240px}}a{{color:#146677}}pre{{white-space:pre-wrap;font-size:13px}}header{{padding:24px;background:#e4edeb;border-radius:12px}}</style>
<header><h1>{escape(score['title'])}</h1><p>{len(score['bars'])} 小节 · Lead + SATB + VP + Whistle</p>
<p>自动编配草稿，尚未真人听审。结构检查通过不代表原曲逐音准确。</p>
<p>试听引擎：{escape(render['backend'])}。五个人声用钢琴，口哨用长笛，VP 用鼓组。</p>
<a href="scores/Full_Score.pdf">总谱 PDF</a> · <a href="scores/Full_Score.musicxml">可编辑总谱</a> · <a href="midi/Full_Score.mid">MIDI</a> · <a href="score.json">事件数据</a>
<p><audio controls preload="none" src="audio/Full_Mix.{audio}"></audio> 全混音</p>
<p><audio controls preload="none" src="audio/Without_Lead.{audio}"></audio> 去主唱</p></header>
<table><tr><th>声部</th><th>谱面</th><th>独听</th><th>突出声部练习</th></tr>{rows}</table>
<h2>需要核对的证据</h2><ul>{warnings}</ul><details><summary>自动检查与 agent 审校记录</summary><pre>{escape(json.dumps(report, ensure_ascii=False, indent=2))}</pre></details>
<p><a href="manifest.json">文件校验单</a> · <a href="review.json">完整审校记录</a></p></html>'''
    (root/"review.html").write_text(html, encoding="utf-8")
    (root/"README.txt").write_text("Open review.html for scores and rehearsal tracks.\n"
        "Automatic draft: human listening and score review still required.\n"
        "All WAV tracks share one timeline. Solo tracks use one common gain.\n"
        "No original recording is mixed into the rendered rehearsal audio.\n", encoding="utf-8")
