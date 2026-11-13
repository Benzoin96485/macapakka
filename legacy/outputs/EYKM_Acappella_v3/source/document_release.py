"""Write the v3 rehearsal guide, provenance, cue table and project entry points."""
from pathlib import Path
import json,csv,hashlib,collections,html,importlib.metadata,re,sys
import numpy as np
from mxl import Chord
ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT.parents[1];REF=PROJECT/'work/v3/reference'
d=json.loads((ROOT/'source/arrangement.json').read_text());v=json.loads((ROOT/'source/validation.json').read_text())
a=json.loads((ROOT/'source/audio_render.json').read_text());meta=d['metadata']
def clock(t):return f'{int(t)//60:02}:{t%60:05.2f}'
cues=[dict(section=m['section'],name=m['label'],bar=m['bar'],mp3_seconds=m['source_time']-.18,
           original_seconds=m['source_time'],key=m['key']) for m in meta if m['local']==1]
(ROOT/'source/cues.json').write_text(json.dumps(cues,indent=2))
with (ROOT/'source/cues.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(cues[0]));w.writeheader();w.writerows(cues)

# Evidence weights are diagnostic, not calibrated probabilities. Keep the raw
# candidate chord chart separate from these summaries to avoid claiming certainty.
raw={n:np.load(REF/f'{n}.npy') for n in ('piano','guitar','other','bass')}
audit=[]
for m in meta:
    for h in m['harmonies']:
        t0=m['source_time']+h['offset']/3*(m['source_end']-m['source_time'])
        t1=t0+h['duration']/3*(m['source_end']-m['source_time'])
        weights=np.zeros(12)
        for stem,x in raw.items():
            overlap=np.maximum(0,np.minimum(x[:,1],t1)-np.maximum(x[:,0],t0))
            for row,ov in zip(x,overlap):
                if ov>0 and row[3]>.25:weights[int(row[2])%12]+=ov*row[3]*(.7 if stem=='other' else 1)
        ch=Chord(h['symbol']);pcs={p.midi%12 for p,_ in ch.tones}|{ch.bass.midi%12}
        support=sum(weights[p] for p in pcs)/(weights.sum()+1e-12)
        audit.append(dict(bar=m['bar'],reference_key=m['reference_key'],beat=h['offset']+1,chord=h['symbol'],
                         source_start=t0,source_end=t1,inside_chord_fraction=round(float(support),4),
                         strongest_pitch_classes=' '.join(str(int(p)) for p in np.argsort(weights)[::-1][:5]),
                         status='review' if support<.65 or weights.sum()<.12 else 'evidence-supported'))
with (PROJECT/'work/v3/analysis/harmony_evidence.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(audit[0]));w.writeheader();w.writerows(audit)
provenance=dict(source_sha256=d['source_sha256'],reference_project='/Users/weiliangluo/src/vibacappella-claude',
    reference_files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in REF.iterdir() if p.is_file()},
    soundfont_sha256=a['soundfont_sha256'],python=sys.version,
    dependencies={n:importlib.metadata.version(n) for n in ('numpy','scipy','soundfile','mido','Pillow')},
    reportlab_source='/Users/weiliangluo/miniconda3/envs/qmmm/lib/python3.11/site-packages',
    changes_to_reference_project=False,final_pdf_engine='ReportLab vector rehearsal engraver',
    audio_engine=a['engine'],musescore_gui_result='Computer Use was not approved to use MuseScore Studio',
    musescore_cli_result='Cocoa/pasteboard/XPC initialization failed in restricted execution environment',
    human_listening_review=False)
(ROOT/'source/provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2))
pdf_pages=len(re.findall(rb'/Type\s*/Page\b',(ROOT/'scores/EYKM_v3_Full_Score.pdf').read_bytes()))
colour_count=len(json.loads((PROJECT/'work/v3/analysis/colour_repairs.json').read_text()))
roles=collections.Counter(e['role'] for p in ('Soprano','Alto','Tenor') for b in d['score'][p] for e in b if e['p'] is not None)
table='\n'.join(f"| {x['section']} | {x['bar']} | {x['name']} | {clock(x['mp3_seconds'])} | {x['key']} |" for x in cues)
ranges={'Lead':'A3–G5','Soprano':'D4–A5','Alto':'G3–D5','Tenor':'C3–G4','Bass':'E2–G3','Whistle':'F4–A♭5'}
range_table='\n'.join(f"| {p} | {ranges[p]} | {v['parts'][p]['longest_unbroken_phrase_seconds']:.2f} 秒 |" for p in ranges)
guide=f'''# Everytime You Kissed Me · 阿卡贝拉 v3

编制：主唱 + SATB + 单人 VP + 口哨。198 小节，3/4 记谱，伴奏重音常为两个附点四分拍。试听约 4 分 59 秒，无预备拍。

## 打开文件

- 完整试听：`audio/EYKM_v3_Full_Mix.mp3`
- 总谱：`scores/EYKM_v3_Full_Score.pdf`（A3 纵向，{pdf_pages} 页）
- 可编辑总谱：`scores/EYKM_v3_Full_Score.musicxml`
- 七份分谱：`parts/`，含 PDF 和 MusicXML
- 练习音轨：`audio/EYKM_v3_Focus_<声部>.mp3`；去主唱：`audio/EYKM_v3_Without_Lead.mp3`
- 口哨、VP、Alto、Tenor 独奏：`audio/EYKM_v3_Solo_<声部>.mp3`
- 重点试听：`audio/excerpts/` 中的 Piano、Flute、Backing、VP 四个片段

## 本版对应的五项修改

| 问题 | v3 的处理 |
| --- | --- |
| 和弦色彩被改动 | 采用 Claude 项目的逐半小节和声记录，保留 71 处半小节变化、转位、sus、七音、六音及 add9；另检查色彩音是否落实到声部，不只写在和弦标记上。 |
| 口哨混入非长笛材料 | 口哨仅在第 44–59 小节奏原长笛线，其余全部休止。前奏及尾声的钢琴主题交给 Soprano。 |
| 钢琴变成固定柱状/琶音 | 使用分轨实际起音与音高分配运动线，各小节保留不同的节奏和填充，主歌主要由 S/T 交织，副歌由 A 承担部分运动线。 |
| 背景人声铺底缺失 | 在 vocalise/桥段设置独立 ah 持续线，区分分轨支持的背景音和编配补足音；与钢琴运动声部并行。 |
| VP 未设计 | 110 个有声小节，23 种实际节奏型；区分引入、轻律动、两拍组主律动、段尾填充和退出。每个时刻只有一个口技发声。 |

## 快速检查的段落

| 段落 | 小节 | 内容 | 试听起点 | 调性 |
| --- | --- | --- | --- | --- |
{table}

建议先听前 42 秒的钢琴织体示例，再听长笛间奏及 02:24 后的背景声部示例。VP 示例直接从有鼓的副歌开始，避免独奏音轨开头长时间休止造成误解。

## 演唱与 VP

`du/lu` 是钢琴运动线，要求轻而连贯；`oo/mm` 承担持续和声或弦乐支撑；`ah` 是背景人声线。钢琴采样会自然衰减，真人演唱应维持标记的长音气息。休止是实际释放/换气位置，各声部交错换气。

| VP 音节 | 动作 / 试听音色 | 演奏要求 |
| --- | --- | --- |
| B | 唇底鼓 / kick | 实而短，勿拖出有音高的尾巴 |
| pf | 唇军鼓 / snare | 主要反拍，避免盖过主唱 |
| ka | 舌侧击 / rim | 主歌和第三副歌的轻反拍 |
| t | 闭镲 | 可用吸气版本补气 |
| ts | 开镲 | 比 t 略长，控制嘶声 |
| ksh | 段首镲 | 仅在标记处突出；与底鼓错开一个十六分音符 |
| dm | 有声短击 / tom | 仅作短填充，不持续哼鸣 |

不要把重音唱成三拍华尔兹。主体重心在第 1 拍与第 2 拍后半；同一段里每两小节有变化，段尾再做短填充。原曲安静段保留停奏。

## 音域和必要的排练复核

中央 C 记为 C4；Tenor 八度高音谱号低八度发声。口哨全线比原长笛低一个八度，保持音程和轮廓，音域 F4–A♭5；没有逐个挪八度拼接。

| 声部 | 实声音域 | 谱中最长无休止乐句 |
| --- | --- | --- |
{range_table}

Soprano A5、主唱 G5、Bass E2 仍需结合成员能力分配。62 处新增短换气已记录；这些时长是统计值，并非人体气息能力保证。

主唱保留 Claude 的旋律底稿并迁移了旧 GPT 谱的 303 个歌词音节。为容纳同音多音节，部分音符被拆分重发；音高主干没有因此改调。歌词落点是时间对齐，仍应跟原唱核对。

## 试听的实际生成方式

人声使用本机 MuseScore `MS Basic.sf3` 的 Grand Piano 样本，口哨用 Flute 样本，VP 用 Standard 鼓组样本。由本项目离线采样播放器生成 MP3，没有把原录音混入，也没有沿用 v2 的正弦/噪声合成。

这不是 MuseScore 程序直接导出的音频或 PDF。界面操作未获工具权限，命令行图形组件也未启动成功；因此本版提供可导入 MuseScore 的 MusicXML，没有伪造 `.mscz`。采样播放器保留分层、音高、循环和包络，但不复刻 MuseScore 的全部效果器及调制器。

## 已核验与仍需听审

已核验：198 小节、每小节 3 拍、七声部、延音对应、SATB 顺序、全部 MusicXML 音符/时值、全部 MIDI 音符/时值、长笛来源限定、前奏钢琴主题轮廓、输入文件哈希。详情见 `source/validation.json`。

和声表及背景声部仍含听辨/算法推断。本版没有经过真人逐音听审，不能称为原录音的零误差复刻。多层 ah、桥段和较弱钢琴音的来源置信度已写进数据；请重点核对第 98–138 小节背景层，以及原曲人声与器乐互相泄漏的地方。
'''
(ROOT/'README_ZH.md').write_text(guide)
report=f'''# Everytime You Kissed Me v3 技术与改编记录

## 结果与边界

v3 已在 `/Users/weiliangluo/src/vibacappella-gpt/outputs/EYKM_Acappella_v3` 生成。主格式为显式事件 JSON、MusicXML、PDF、MIDI 和采样 MP3。原 GPT v1/v2 与 Claude 项目的文件未被覆盖。此记录描述实际执行的步骤，自动检查不等于逐音真人听审。

## 输入与借鉴

两项目的原始 `EYKM.flac` SHA-256 均为 `{d['source_sha256']}`，时长 299.106667 秒，确认分析的是同一录音。

从 Claude 项目复制至 `work/v3/reference/` 的材料包括四条文本转写（lead/chords/bass/whistle）、五组 Basic Pitch 音符数组、长笛音高分析、两份鼓组格点和参考脚本。复用了其 MusicXML 工具的基础对象/导出方式，修改了乐器配置；没有执行该项目的构建脚本去修改它。

本次未重跑 Demucs、GAME 或 Basic Pitch。使用已有分轨转写作为候选证据，并重新查看 vocalise 人声频谱；`work/v3/analysis/vocals_144_167.png` 保存了观察图。不能把“采用原曲分轨数据”写成“已人工核实每个分离音符”。

## 和声

旧 GPT 编曲器使用固定和弦列表，一小节只有一个和弦，伴奏音高又从和弦集合就近生成。这是 sus、转位及延伸色彩丢失的直接机制。

v3 使用 198 小节的新编号，与 Claude 的新版总谱一致；原参考文本 key = v3 小节号 + 3。显式和声共 {len(audit)} 段，其中 71 小节在中途换和弦。示例：第 28 小节 Db→Eb7sus4、第 92 小节 Cm7、第 118 小节 Am→B7/D#、第 145 小节 Cmadd9→Dbsus4、第 195–198 小节 F#add9。这些符号来自参考转写，不是已取得的原版出版总谱。

编配后再次统计三、四、七、六、九音是否在发声集合里，针对可编辑的和声支撑音执行了 {colour_count} 次补足；不把原钢琴、主唱或有分轨证据的背景音强制吸附到和弦音。`colour_repairs.json` 逐项保存这些编辑。

`harmony_evidence.csv` 根据 piano/guitar/other/bass 转写音符的时间重叠与振幅汇总候选证据。落在和弦音内的权重比例是诊断量，不是概率；共有 {sum(x['status']=='review' for x in audit)} 段因权重不足或比例低而标为 review。经过音、延留音、谐波误识别和分离泄漏都会影响这个比例，因此没有按最大相似度另换和弦。

## 器乐与背景层如何变成 SATB

钢琴候选以真实转写起点分组到八分网格，保留原音高类；极短、较弱及明显的人声泄漏候选会被过滤。根据声部音域分配为单声线，留出原有空隙和句尾填充，不再使用全曲统一六八分音符琶音模板。最终 S/A/T 中有 {roles['piano']} 个钢琴来源事件；候选分配表另含后来被人工主题覆盖的候选，不能直接把候选总数当作最终音符数。

前奏和尾声主题来自原参考“whistle”转写中的钢琴材料，改交 Soprano，整体降一个八度。前奏第 5 小节专门重配 A/T/B，避免为了声部排序把主题 F4 错抬为 F5。第 139–145 小节器乐过渡保留在 Alto。口哨仅第 44–59 小节奏长笛线，整体降八度，逐格比对与该参考长笛转写完全一致。

背景人声从 vocals 音符候选中选择持续的非主唱音，剔除主唱的明显高次谐波/同音类，加入平稳连接偏好。没有可靠候选时，使用显式标记为 editorial 的和声支撑。最终 S/A/T 含 {roles['vocal_backing']} 个 `vocal_backing` 事件和 {roles['harmonic_support']} 个 `harmonic_support` 事件；后者不能宣称为已经扒出的真实背景演唱。`background_decisions.json` 保留半小节选择和证据权重。

SATB 以每十六分格检查顺序。音域调整仅作八度放置，优先保护钢琴主题和器乐副旋律的轮廓；全部放置变更记录在 `register_changes.json`。62 处呼吸编辑缩短长音释放，不删除一个完整的旋律起音。

## VP

参考原曲鼓组的出现/退出区间和鼓组频带起音格点，重新编写单人口技。格点会把一次军鼓误报到多个频带，因此没有直接把 K+S+h 机械地全部同时抄入谱面。

成品 110 个有声小节、23 种实际小节音符序列，涵盖吸气闭镲、轻 rim 反拍、两组附点四分重心、追加底鼓、段首镲、不同句尾填充和退出。单人口技没有同时发出三个鼓件的要求。七种音节和鼓组对应见排练说明。

## 主唱与时间

Claude 的主唱转写作为音高底稿；旧 GPT 版本的 303 个歌词音节通过保持顺序的动态规划对齐至有声十六分格。必要时拆分同音长音承载不同音节。未丢失歌词音节，但算法对齐仍需主唱核对发音位置。比对表保存在 `lyric_underlay.json`。

前奏 9 小节采用原项目的自由速度边界；主体原参考 key 13 起沿用 126 BPM 网格；尾声最后和弦对准 282.8736517 秒的钢琴起音，并保留长收束。音乐起点对应原音频 0.18 秒，音乐本体 296.22 秒，另有 2.5 秒余响。MP3 没有预备拍。

## 导出及音源

总谱/分谱 MusicXML 声音设置为五条钢琴、长笛、GM 第 10 通道打击乐。总谱和七分谱用 ReportLab 矢量绘谱器生成，主要沿用本项目 v2 的谱头、连梁、延音和排版函数，改为实际半小节和弦、拍内时值拆分、A3 纵向双系统总谱与更疏的主唱分谱。总谱 {pdf_pages} 页，主唱分谱 16 页。

本机 MuseScore CLI 无法初始化 Cocoa/pasteboard/XPC；Computer Use 返回“Computer Use was not approved to use MuseScore Studio”。没有尝试更改系统权限。最终音频采用 `MS Basic.sf3` 本地采样，由 `render_samples.py` 读取预置、采样区、力度层、音高修正、循环、包络、衰减及声像。无原录音混入、无正弦波人声合成。

试听预置：Grand Piano（bank 0 / program 0）、Flute（bank 0 / program 73）、Standard kit（bank 128 / program 0），共使用 {len(a['samples'])} 个采样。按乐器作固定增益校准，避免鼓组淹没钢琴；成品峰值约 0.91，44.1 kHz、192 kb/s MP3。采样音高抽查四个音，基频与预期偏差均小于 4 cents，见 `sample_pitch_check.json`。这不是对全部音色调制器的完整 SoundFont 实现，也不是 MuseScore 本身的渲染。

## 验证与复现

`validate_v3.py` 实际检查了 JSON 每小节时值、延音前后音高、SATB 交叉、八份 MusicXML 的每个音高/休止格点、八份 MIDI 的每次 note-on/off 与总时长、口哨来源范围、钢琴主题轮廓及 MP3 时长；最终检查通过。PDF 已渲染为 PNG，检查了总谱总览和密集页、主唱歌词页与分谱页面。

从项目根目录按顺序运行：

```sh
tools/rebuild_v3.sh
```

该脚本依赖本机现有 music Python/Claude 依赖环境、ReportLab、FFmpeg 和 MuseScore 安装中的字体/音库，详见 `source/provenance.json`。最终打包的成品可直接使用；从头重建还需要项目的 `input/`、`work/v3/reference/`。本次没有捆绑第三方采样音库，也没有承诺在没有这些依赖的新机器上一条命令完成分离和扒谱。

## 文件位置与版本保护

`outputs/EYKM_Acappella_v3/` 保存成品与最终代码；`work/v3/` 保存复制的参考、候选决策、频谱、采样 WAV、运行日志和谱面渲染；`docs/TECHNICAL_REPORT_V3_ZH.md` 是本记录。旧版说明和旧校验单另存快照；项目根校验单更新为当前状态。原曲、原 GPT v1/v2 音乐成果及 Claude 文件保持原样。
'''
(PROJECT/'docs/TECHNICAL_REPORT_V3_ZH.md').write_text(report)
(ROOT/'TECHNICAL_REPORT_V3_ZH.md').write_text(report)
try:
    import markdown
    for p in (ROOT/'README_ZH.md',PROJECT/'docs/TECHNICAL_REPORT_V3_ZH.md'):
        body=markdown.markdown(p.read_text(),extensions=['tables','fenced_code'])
        page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+html.escape(p.stem)+'</title><style>body{max-width:1000px;margin:45px auto;padding:0 28px;color:#173342;font:16px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}h1{font-size:29px}h2{margin-top:38px;border-bottom:1px solid #b9ced7}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:9px 12px;border:1px solid #d9e3e8;text-align:left}th{background:#ecf3f6}pre,code{background:#f0f4f6;overflow-wrap:anywhere}pre{padding:20px;white-space:pre-wrap}a{color:#176477}</style>'+body+'</html>'
        p.with_suffix('.html').write_text(page)
except ImportError:pass
oldread=PROJECT/'docs/README_v2_ARCHIVED.md'
if not oldread.exists():oldread.write_bytes((PROJECT/'README.md').read_bytes())
(PROJECT/'README.md').write_text('''# Everytime You Kissed Me · 阿卡贝拉项目

最新版本为 **v3**：主唱 + SATB + VP + 口哨，198 小节。

- [v3 排练说明与文件入口](outputs/EYKM_Acappella_v3/README_ZH.md)
- [v3 完整试听](outputs/EYKM_Acappella_v3/audio/EYKM_v3_Full_Mix.mp3)
- [v3 总谱 PDF](outputs/EYKM_Acappella_v3/scores/EYKM_v3_Full_Score.pdf)
- [v3 可编辑 MusicXML](outputs/EYKM_Acappella_v3/scores/EYKM_v3_Full_Score.musicxml)
- [v3 技术记录](docs/TECHNICAL_REPORT_V3_ZH.md)
- [v3 检查结果](outputs/EYKM_Acappella_v3/source/validation.json)
- [v2 历史说明](docs/README_v2_ARCHIVED.md)

v3 恢复逐半小节和声色彩，口哨只保留长笛段，按源钢琴起音重分配 SATB，补入背景人声及单人 VP。当前试听使用 MuseScore 自带的钢琴/长笛/鼓组采样，通过项目离线播放器生成；不是 MuseScore 程序直接导出。尚未经过真人逐音听审。

成品在 `outputs/EYKM_Acappella_v3/`，过程与证据在 `work/v3/`。旧版保留。
''')
print('Wrote v3 guide, technical report, provenance and cues')
