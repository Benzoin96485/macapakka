from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import colors
R=Path(__file__).resolve().parents[1]
data=json.loads((R/'source/arrangement.json').read_text());cues=json.loads((R/'source/cues.json').read_text());val=json.loads((R/'source/validation.json').read_text())
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
C=canvas.Canvas(str(R/'EYKM_Rehearsal_Guide_ZH.pdf'),pagesize=(595.28,841.89))
C.setTitle('Everytime You Kissed Me - 中文排练说明')
blue=colors.HexColor('#176477');ink=colors.HexColor('#17212b');muted=colors.HexColor('#536879')
def text(x,y,t,size=10,col=ink):C.setFillColor(col);C.setFont('STSong-Light',size);C.drawString(x,y,t)
def wrap(t,width,size=10):
 lines=[];line=''
 for ch in t:
  if ch=='\n':lines.append(line);line='';continue
  if pdfmetrics.stringWidth(line+ch,'STSong-Light',size)>width:lines.append(line);line=ch
  else:line+=ch
 if line:lines.append(line)
 return lines
def para(y,t,size=10,leading=17):
 for ln in wrap(t,507,size):text(44,y,ln,size);y-=leading
 return y

def head(page,sub):
 C.setFillColor(colors.white);C.rect(0,0,595.28,841.89,fill=1,stroke=0)
 text(44,798,'everytime you kissed me',24,ink)
 text(44,774,sub,13,blue)
 C.setStrokeColor(blue);C.setLineWidth(.8);C.line(44,761,551,761)
 text(44,28,'学生社团内部排练版  ·  2026-11-02  ·  主题改编初稿 v1.0',8,muted)
 text(541,28,str(page),9,muted)
def table(y,headers,rows,widths,rowheight=24):
 C.setFillColor(blue);C.rect(44,y-rowheight,sum(widths),rowheight,fill=1,stroke=0)
 xx=44
 for s,w in zip(headers,widths):text(xx+7,y-16,s,9.4,colors.white);xx+=w
 y-=rowheight
 for ii,row in enumerate(rows):
  if ii%2==0:C.setFillColor(colors.HexColor('#eef4f5'));C.rect(44,y-rowheight,sum(widths),rowheight,fill=1,stroke=0)
  xx=44
  for s,w in zip(row,widths):
   lines=wrap(str(s),w-13,9.2)
   for j,line in enumerate(lines):text(xx+7,y-15-j*12,line,9.2)
   xx+=w
  y-=rowheight
 return y

def tm(sec):return f'{int(sec)//60}:{sec%60:04.1f}'
head(1,'SATB + VP + 主唱 + 口哨  |  作品与段落导览')
y=para(738,'本版以所提供的 EYKM.flac 为蓝本，保留主歌及“Roses”段的主题轮廓，重写 SATB 伴唱、口哨间奏与无词桥段。原曲约 4 分 59 秒，本版音乐本体约 3 分 20 秒，共 136 小节，3/4 拍。')
y=para(y-3,'这是主题精编版，未收入原曲所有歌词和器乐段落。主唱音高与节奏作适唱改写；它与原录音不逐小节对应。最低配置为 7 人，SATB 也可各由多人演唱。')
text(44,y-9,'段落与定位',13,blue);y-=23
names={'I':'前奏','A':'主歌 1','B':'Roses 段','C':'口哨间奏','D':'主歌 2','E':'无词桥段','F':'主歌 3','G':'无词再现','H':'尾声'}
roles={'I':'口哨 + 哼鸣逐步加入','A':'主唱突出，VP 后半加入','B':'SATB 与轻 VP 展开','C':'口哨主导，主唱休息','D':'上移至 D 小调的主歌主题','E':'S 先唱主题，再交给主唱','F':'回到 C 小调，主歌再现','G':'主唱 ah，S 高声部展开','H':'逐层收束，末 8 小节停 VP'}
rows=[]
for i,q in enumerate(cues):
 end=cues[i+1]['bar']-1 if i+1<len(cues) else 136
 rows.append([q['section']+' '+names[q['section']],f"{q['bar']}-{end}",tm(q['mp3_time']),roles[q['section']]])
y=table(y,['段落','小节','MP3 时间','编制重点'],rows,[85,62,72,288],24)
y=para(y-18,'MP3 开头有两小节 3/4 预备拍（四分音符 = 108），约 3.33 秒；音乐结束后约 2 秒余响。MIDI 与乐谱均从第 1 小节直接开始，没有预备拍。',9.5,15)
text(44,y-10,'实声音域（中央 C = C4）',13,blue);y-=24
nr=lambda n:['C','Db','D','Eb','E','F','F#','G','Ab','A','Bb','B'][n%12]+str(n//12-1)
rs=[]
label={'Lead':'主唱','Soprano':'S 女高','Alto':'A 女低','Tenor':'T 男高','Bass':'B 男低','Whistle':'口哨'}
for p in ['Lead','Soprano','Alto','Tenor','Bass','Whistle']:
 lo,hi=data['ranges'][p];note={'Lead':'三段主歌带英文歌词；其余标明无词音节','Soprano':'桥段有独立旋律；高潮最高 F5','Alto':'保持共同音，避免盖过主唱','Tenor':'八度低音高音谱号，实际低八度发声','Bass':'最低 F2；长音用 dm / mm','Whistle':'实音记谱，不另行升高八度'}[p]
 rs.append([label[p],nr(lo)+' - '+nr(hi),note])
y=table(y,['声部','实声音域','提示'],rs,[85,92,330],23)
C.showPage()
head(2,'排练顺序、发音图例与文件使用')
y=738
for heading,body in [
 ('先建立三拍脉动','从 A 段第 9-24 小节开始，先合 Bass 与 Tenor，再加入 Alto 和 Soprano。可先以每分钟 90 拍排练，最后回到标注速度；第 1 拍有支点，第 2、3 拍保持流动。'),
 ('让主唱的字义保持清楚','伴唱的 oo / mm 比主唱轻一个动态层级。ah 用于桥段与高潮。连线连接同音时不要重发音；休止处真实换气。主唱低音 Bb3 较多，按实际音区选择演唱者。'),
 ('把转调单独排熟','第 25 小节转 F 小调，第 57 小节转 D 小调，第 73 小节转 G 小调，第 89 小节回 C 小调。第 88 小节 G7 中的 B 为还原 B；第 128 小节 C7 引向第 129 小节 F 小调。'),
 ('口哨以完整短句回应','前奏、C 段和尾声是口哨重点。按写出的休止换气；桥段中的短句须等前一句旋律让出空间。第 136 小节口哨休止，由 SATB 的 F 小调和弦结束。'),
 ('渐慢由指挥统一带领','前奏四分音符 = 108；A-G 段 = 126；H 段 = 118。第 129 小节 = 112，第 133-136 小节依次为 106、100、92、80。末和弦按谱面三拍收完，不额外增加延长。')]:
 text(44,y,heading,12,blue);y-=21;y=para(y,body,10,16);y-=11
text(44,y,'VP 单线谱与口腔音节',12,blue);y-=14
y=table(y,['谱下音节','动作 / 音色','节奏角色'],[
 ['B','闭唇低鼓音，短而圆','主要支点落在第 1 拍'],['pf','唇齿气音军鼓','第 2 拍轻点'],['t / ts','闭镲 / 稍长的擦音','填充八分脉动'],['休止','完全停音并换气','每四小节常留最后半拍']],[82,215,210],22)
y=para(y-17,'展开段的基本一小节为 B t pf t ts t，对应 1 & 2 & 3 &。这些音由一位 VP 顺次完成，不要求同时发两个音。',9.5,15)
text(44,y-4,'文件使用与完成度',12,blue);y-=24
y=para(y,'scores 内有 A3 总谱与可编辑 MusicXML；parts 内有 7 份 A4 分谱及对应 MusicXML。audio 内含全曲合成试听、7 个声部突出版本和去主唱版本；midi 内有总 MIDI、7 个单声部 MIDI 和去主唱 MIDI。',9.5,15)
y=para(y-5,'MusicXML 可用 MuseScore 打开并重新排版。MP3 只示范音高、节奏和声部分配，不会唱出英文歌词；其中“人声”与 VP 均为合成音色。Focus 文件将目标声部居中并提高音量，其他声部保留较低音量。',9.5,15)
y=para(y-5,'本稿已校验每小节拍数、实声音域、SATB 同时发声时的交叉，以及歌词音节数；尚未经过真人听审或试唱。首次合排应由主唱对照原录音校准旋律细节、英语重音与咬字，尤其不要把本版的节奏简化误认为原曲逐音定本。',9.5,15)
print('guide last y',y)
C.save()
readme=f'''EVERYTIME YOU KISSED ME - 学生社团阿卡贝拉主题精编版 v1.0

原作：Yuki Kajiura / 梶浦由记
参考：用户提供的 EYKM.flac（约 4:59）
编制：主唱 + SATB + VP + 口哨，七条独立声部，不分 divisi。
长度：136 小节，3/4 拍，音乐约 3:20；MP3 含预备拍与余响，约 3:25。
请先阅读 EYKM_Rehearsal_Guide_ZH.pdf。

版本范围
这是根据音频主题重新编排的精编稿，包含新写的 SATB、口哨和桥段。
未收入原曲所有歌词、器乐段落和转调；不要与原录音同步伴唱。
主唱旋律作了适唱改写，尚未经过真人听审与试唱，首次合排需要校订。
所有音频均为合成示范，不含原始录音，也不唱出歌词。

目录
scores/   PDF 总谱（A3 竖版，建议按原尺寸打印）及 MusicXML
parts/    七声部 PDF 分谱（A4）及 MusicXML
midi/     总谱、七个单声部、去主唱 MIDI
 audio/   全曲、七个声部突出、去主唱 MP3
source/   音符事件 JSON、时间索引、验证结果、可重复生成的 Python 源码

MP3 的两小节预备拍为每分钟 108 拍，约 3.33 秒；MIDI 不含预备拍。
Tenor 采用高音谱号下方小 8，实音比谱面低八度；其余声部按实音。

制作记录
音频经过频谱与音高轮廓分析辅助判断；声部音符为显式编写的主题改编。
不是分离人声后完成的逐音听写，也不是原版官方乐谱。
原曲使用范围沿用用户已取得的授权；本包为社团内部排练准备。

生成脚本的依赖：Python、numpy、scipy、reportlab，以及用于 MP3 编码的 ffmpeg。
脚本默认使用本机 MuseScore 4 的 FreeSerif 字体，换电脑需调整 FONT_DIR。
修改后运行 build_arrangement.py 会重新生成乐谱与合成音轨；
添加 --notation-only 只更新乐谱和 MIDI。build_guide.py 生成中文说明。
本包未包含或修改源音频。
'''
(R/'README_ZH.txt').write_text(readme)
