from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import colors
R=Path(__file__).resolve().parents[1]
D=json.loads((R/'source/arrangement.json').read_text());V=json.loads((R/'source/validation.json').read_text());Q=json.loads((R/'source/cues.json').read_text())
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
C=canvas.Canvas(str(R/'EYKM_v2_Rehearsal_Guide_ZH.pdf'),pagesize=(595.28,841.89));C.setTitle('Everytime You Kissed Me - 完整结构阿卡贝拉第二版')
INK=colors.HexColor('#182b35');BLUE=colors.HexColor('#1b6977');MUTED=colors.HexColor('#62747c');PALE=colors.HexColor('#eef5f6')
def text(x,y,t,size=10,col=INK):C.setFillColor(col);C.setFont('STSong-Light',size);C.drawString(x,y,str(t))
def wrap(t,w,size=10):
 out=[];s=''
 import re
 for ch in re.findall(r'[A-Za-z0-9_/#:+.\-]+|.',t):
  if ch=='\n' or (pdfmetrics.stringWidth(s+ch,'STSong-Light',size)>w and ch not in '，。；：！？）》】、'):out.append(s);s='' if ch=='\n' else ch
  else:s+=ch
 if s:out.append(s)
 return out
def para(y,t,size=10,leading=17):
 for line in wrap(t,507,size):text(44,y,line,size);y-=leading
 return y
def head(n,subtitle):
 text(44,796,'everytime you kissed me',24);text(44,771,subtitle,13,BLUE)
 C.setStrokeColor(BLUE);C.line(44,757,551,757)
 text(44,28,'学生社团内部排练  ·  SATB + VP + 主唱 + 口哨  ·  v2.0',8,MUTED);text(542,28,n,9,MUTED)
def table(y,headers,rows,widths,rh=26):
 C.setFillColor(BLUE);C.rect(44,y-rh,sum(widths),rh,fill=1,stroke=0);x=44
 for t,w in zip(headers,widths):text(x+6,y-17,t,9.5,colors.white);x+=w
 y-=rh
 for ix,row in enumerate(rows):
  if ix%2==0:C.setFillColor(PALE);C.rect(44,y-rh,sum(widths),rh,fill=1,stroke=0)
  x=44
  for t,w in zip(row,widths):
   for k,line in enumerate(wrap(str(t),w-12,9.2)):text(x+6,y-16-k*12,line,9.2)
   x+=w
  y-=rh
 return y
def tm(x):return f'{int(x)//60}:{x%60:04.1f}'
N=lambda n:['C','C#','D','Eb','E','F','F#','G','G#','A','Bb','B'][n%12]+str(n//12-1)
head(1,'完整结构改编第二版  |  全曲导航')
y=para(736,f'本版以用户提供的 EYKM.flac 为蓝本，按完整歌曲结构重新编排，共 {V["measures"]} 小节，3/4 拍，音乐本体约 {tm(V["musical_seconds"])}。编制为主唱、SATB、VP 和口哨七条独立声部，最低七人可演唱；SATB 可多人同声部。')
y=para(y-3,'相较第一版，恢复完整歌词段落、中段发展、钢琴回归和尾声，保留末段升半音、大小调交替与终止式的色彩。没有沿用第一版新写的简化无词桥段。器乐音区按人声与口哨重新分配，伴唱为本版新编。')
text(44,y-9,'谱面与录音定位',13,BLUE);y-=24
cn=['钢琴前奏','主歌一','Roses 段','器乐间奏','主歌二','Joys 段','无词发展一','无词发展二','钢琴回归','升调主歌','Underneath 段','钢琴尾声']
roles=['自由速度；内声接力','主唱与轻分解和弦','弦乐线条展开','口哨接器乐主线','D 小调；保留弱起','连续长句与渐强','G 小调层叠人声','E 小调后转回 G 区域','G 小调；VP 退出','C# 小调，升半音','F# 小调；逐层收束','保留大三度收束']
rows=[]
for j,q in enumerate(Q):
 end=Q[j+1]['bar']-1 if j+1<len(Q) else V['measures']
 rows.append([q['section']+' '+cn[j],f'{q["bar"]}-{end}',tm(q['source_time']),roles[j]])
y=table(y,['段落','小节','原录音','编排重点'],rows,[102,62,64,279],25)
y=para(y-19,'“原录音”列指段落起点，不一定是首个歌词音节的进入时刻；弱起可能位于前一小节。练习 MP3 另加两小节预备拍，MIDI 从谱面第 1 小节直接开始。精确试听定位见 source/cues.json。',9.4,15)
y=para(y-7,'自由速度处的速度标记服务于排练示范。现场由指挥保持句法与呼吸，避免机械追逐录音的毫秒位置；本包并非与原录音同步播放的伴奏。',9.4,15)
C.showPage()
head(2,'音色、音域与声部接力')
y=736
notes={'Lead':'原歌词与旋律主线；无词段按谱中 ah / ya 处理','Soprano':'弦乐长线、高潮顶声与旋律接力；不压住主唱','Alto':'钢琴中高区分解音、和声色彩与短回应','Tenor':'钢琴中低区流动音型；与 A 轮流补齐脉动','Bass':'保留根音走向与属音支点；dm / dn 保持圆润','Whistle':'器乐旋律与前后奏；实音记谱，按休止换气'}
rows=[]
for p in ['Lead','Soprano','Alto','Tenor','Bass','Whistle']:
 lo,hi=D['ranges'][p];rows.append([p,N(lo)+' - '+N(hi),notes[p]])
y=table(y,['声部','实声音域','任务'],rows,[80,94,333],38)
y=para(y-18,'中央 C 记为 C4。Tenor 用高音谱号下方小 8，实际发声低八度；其他有音高声部均为实音。个别器乐线条已作八度移置，以保持句子走向和七人编制的可唱性。',10,17)
for h,b in [
 ('钢琴的流动感来自声部接力','A、T 的短音需共享同一个拍点；一个声部休止时，另一个继续音型。先唱连续的八分音符，再加入 S 的长线。dn / du 稍带辅音，li / lu 轻而有弹性；不要把每个音唱成重拍。'),
 ('长音保持方向，短音保持轻巧','S 的 oo / ah 对应原曲铺展的音色，Bass 保持和声底部。谱中的同音延音线表示持续发声；换词或新音节才重新起音。休止处真正换气，长线交接时保持相同元音。'),
 ('口哨的进入与交接','口哨重点在前奏、器乐间奏、钢琴回归与尾声。连续乐句的末端留有呼吸空间，必要时由 S 在较低八度接住尾音。先检查口哨与主唱、S 的相对音量，再处理装饰音。')]:
 text(44,y-8,h,12,BLUE);y-=29;y=para(y,b,10,16);y-=5
C.showPage()
head(3,'VP 图例、合排路线与文件使用')
y=736
text(44,y-8,'VP 单线谱',12,BLUE);y-=22
y=table(y,['音节','声音','处理'],[['B','闭唇低鼓','第一拍有重心，避免拖尾'],['pf','唇齿军鼓气音','按谱中位置进入，不套固定四拍律动'],['t / ts','短镲 / 较长擦音','八分脉动与局部十六分推进'],['休止','停止发音','真实换气；回归段与尾声留白']],[65,140,302],23)

y-=18
for h,b in [
 ('1  先合钢琴织体，再放入主唱','选 A 段四小节循环，以每分钟 90 拍合 A、T、Bass，确认六个八分位置互相衔接，再加入 S 与主唱。熟练后回到谱面速度。'),
 ('2  把转调和终止式单独连接','重点练 B 到 C、C 到 D、E 到 F、F 到 G，以及 H 到 J。末段 J 保持 C# 小调，K 进入 F# 小调；尾声的大三度为有意保留的收束色彩。不要自动唱回第一版的 C 小调与 F 小调。'),
 ('3  中段保留层次与独立旋律','F、G 段先把主旋律、S 顶声与低音分开排，再加入内声和 VP。高潮的强度来自声部层次与元音统一，主线仍需清楚。'),
 ('4  最后校准歌词、自由速度与收音','主唱先跟 Lead 突出音轨学习谱面，再对照原录音检查英语重音、句末释放与装饰性滑音。前后奏用指挥统一带领；最后和弦共同收音，不让某个声部单独拖尾。')]:
 text(44,y,h,12,BLUE);y-=22;y=para(y,b,10,16);y-=16
text(44,y,'文件',12,BLUE);y-=19
y=para(y,'scores：A3 PDF 总谱与可编辑 MusicXML；parts：七份 A4 PDF 分谱及 MusicXML；audio：全曲、七个声部突出版本、去主唱 MP3；midi：全曲、七个单声部、去主唱 MIDI；source：音符、歌词、原录音时间索引及生成脚本。',10,16)
y=para(y-6,'合成试听只示范音高、节奏和声部关系，不会唱出英语歌词。Focus 音轨将目标声部居中并突出，其他声部保留较轻音量。所有试听均由本版谱面生成，没有混入原录音。',10,16)
text(44,y-13,'校订范围',12,BLUE);y-=34
y=para(y,'本版依据本地音源分离、音高与节拍分析，结合明确编写的和声及声部分工完成。已校验小节拍数、音域、声部关系、导出完整性与谱面排版；尚未经过真人逐音听审与试唱，不能作为原作逐音定本。',10,16)
y=para(y-5,'中段无词人声保留旋律线条，用 ah / ya 提供可排练的元音，不臆造原录音的无词音节拼写。旋律的细微滑音、歌词音节落点与器乐装饰仍应在首次合排时由主唱和指挥对照录音校订。',10,16)
y=para(y-5,'本版以完整结构与主要线条为目标，七人声部对管弦配器作必要的音区、音色和换气重分配。使用范围沿用用户说明的社团内部非营利授权；本包不包含原始歌曲文件。',9.5,15)
assert y>45,y
C.save()
readme=f'''EVERYTIME YOU KISSED ME — 完整结构阿卡贝拉 v2.0
原作：Yuki Kajiura / 梶浦由记
编制：SATB + VP + 主唱 + 口哨（七条独立声部）
196 小节，3/4 拍，音乐本体 {tm(V['musical_seconds'])}。

请先阅读 EYKM_v2_Rehearsal_Guide_ZH.pdf。
第二版独立于第一版；恢复完整歌曲段落、中段发展、升调主歌和尾声。
保留重要大小调色彩与终止式，伴唱与器乐人声化分工为本版新编。

scores/ 总谱 PDF（A3）与 MusicXML
parts/ 七个声部 PDF（A4）与 MusicXML
audio/ 全曲、七声部突出、去主唱 MP3（合成音色，不唱歌词）
midi/ 总 MIDI、七个单声部、去主唱 MIDI
source/ 显式音符数据、转写、时间索引、验证结果与生成代码

MP3 含两小节预备拍与末尾余响；MIDI 从谱面第一小节直接开始。
source/cues.json 同时列出原录音、音乐本体与 MP3 的段落起点。
Tenor 为八度低音高音谱号；口哨和其他有音高声部按实音。

完成度：本地分离音频与音高/节拍分析辅助转写，非官方原版谱。
未经真人逐音听审与试唱；歌词落点、细微装饰与无词音节仍需合排校订。
所有原录音和分析用分离音轨仅用于本地分析，没有放入此交付包。

生成：Python + numpy + scipy + reportlab；ffmpeg 用于 MP3。
使用本机 MuseScore 4 的 FreeSerif 字体；其他电脑需修改 FONT_DIR。
先运行 source/assemble_arrangement.py，再运行 source/render_arrangement.py。
--notation-only 只生成谱面与 MIDI。最后运行 source/build_guide.py。
修改旋律请编辑 source/transcription.json；修改和声和伴唱请编辑 assemble_arrangement.py。
'''
(R/'README_ZH.txt').write_text(readme)
print('Guide complete; final baseline',y)
