"""Vector rehearsal engraving, adapted from the project v2 engraver.
MusicXML is the editable master. This PDF is not exported by MuseScore.
"""
from pathlib import Path
import sys, json
import numpy as np
# Reuse the locally installed pure-Python ReportLab package if absent from music env.
try:
 from reportlab.pdfgen import canvas
except ImportError:
 sys.path.append('/Users/weiliangluo/miniconda3/envs/qmmm/lib/python3.11/site-packages')
 from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from mxl import Chord, NAT, P, split
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'source/arrangement.json').read_text())
PARTS=DATA['parts'];SHORT=['Ld.','S.','A.','T.','B.','VP','Wh.']
TITLE=DATA['title'];score=DATA['score'];meta=DATA['metadata']
KEYS={'Cm':-3,'Fm':-4,'Dm':-1,'Gm':-2,'Em':1,'C#m':4,'F#m':3,'F#':6}
FONT_DIR=Path('/Applications/MuseScore 4.app/Contents/Resources/fonts')
for name,fn in [('FS','FreeSerif.ttf'),('FSI','FreeSerifItalic.ttf'),('FSB','FreeSerifBold.ttf')]:
 pdfmetrics.registerFont(TTFont(name,str(FONT_DIR/fn)))
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
INK=colors.HexColor('#19242D');MUTED=colors.HexColor('#536772');ACCENT=colors.HexColor('#28667A')

def spell(n,key='Cm',chord=None):
 if chord:
  ch=Chord(chord)
  for p,role in ch.tones:
   if p.midi%12==n%12:return p.step,p.alter,(n-NAT[p.step]-p.alter)//12-1
 names=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'] if KEYS[key]>0 else ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
 na=names[n%12];p=P(na+str(n//12-1));return p.step,p.alter,p.octave

def fragments(e,pos=0):
 segs=split(round(pos*4),round(e['d']*4),e['p'] is None);out=[]
 for i,d in enumerate(segs):
  x=dict(e,d=d/4)
  if i:x['ly']=''
  if e['p'] is not None:
   if i:x['tie_stop']=True
   if i<len(segs)-1:x['tie_start']=True
  out.append(x)
 return out

def txt(c,x,y,t,size=9,font='FS',color=INK):
 c.setFillColor(color);c.setFont(font,size);c.drawString(x,y,t)

def center(c,x,y,t,size=9,font='FS',color=INK):
 c.setFillColor(color);c.setFont(font,size);c.drawCentredString(x,y,t)

def right(c,x,y,t,size=9,font='FS',color=INK):
 c.setFillColor(color);c.setFont(font,size);c.drawRightString(x,y,t)

def rule(c,x1,y1,x2,y2,w=.5,color=INK):
 c.setStrokeColor(color);c.setLineWidth(w);c.line(x1,y1,x2,y2)

def title(c,w,h,page,part=None):
 c.setFillColor(colors.white);c.rect(0,0,w,h,fill=1,stroke=0)
 txt(c,38,h-39,TITLE,22,'FSB');right(c,w-38,h-36,'Yuki Kajiura',11)
 txt(c,38,h-57,'SATB + vocal percussion + lead + whistle | v3 / source-led rehearsal arrangement',9,'FS',MUTED)
 if part:txt(c,38,h-78,part.upper()+'  /  CONCERT PITCH' + (' - treble clef sounds 8vb' if part=='Tenor' else ''),11,'FSB',ACCENT)
 else:txt(c,38,h-78,'CONDUCTOR SCORE  /  A3 PORTRAIT',11,'FSB',ACCENT)
 rule(c,38,h-90,w-38,h-90,.8,ACCENT)
 txt(c,38,25,'Internal student rehearsal edition | v3 | K/B=kick, pf=snare, ka=rim, t/ts=hat, ksh=cymbal, dm=tom',8,'FS',MUTED)
 right(c,w-38,25,str(page),9)

def keyglyphs(c,x,bottom,space,key,clef):
 # flats in B E A D G order; bass placements one diatonic step lower.
 vals=([8,5,9,6,3,7,4] if clef!='bass' else [6,3,7,4,1,5,2]) if KEYS[key]>0 else ([4,7,3,6,2,5,1] if clef!='bass' else [2,5,1,4,0,3,-1])
 for i in range(abs(KEYS[key])):txt(c,x+i*space*1.25,bottom+vals[i]*space/2-1,('\u266f' if KEYS[key]>0 else '\u266d'),space*3.1)
 return x+abs(KEYS[key])*space*1.25

def staffhead(c,x,bottom,space,p,key,showtime=False):
 if p=='VP':
  rule(c,x,bottom+2*space,x+25,bottom+2*space)
  txt(c,x+3,bottom+space,'||',space*3)
 else:
  cl='bass' if p=='Bass' else 'treble'
  txt(c,x,bottom+(-.3 if cl=='treble' else .095)*space,'\U0001d122' if cl=='bass' else '\U0001d11e',space*(5.15 if cl=='bass' else 7))
  if p=='Tenor':center(c,x+space*1.5,bottom-space*1.8,'8',space*1.5)
  xx=keyglyphs(c,x+space*4.5,bottom,space,key,cl)
  if showtime:
   center(c,xx+space*1.6,bottom+2.0*space,'3',space*2.6,'FSB');center(c,xx+space*1.6,bottom-.0*space,'4',space*2.6,'FSB')

def diatonic(n,key,ch,p):
 if p=='Tenor':n+=12
 st,al,oc=spell(n,key,ch)
 return oc*7+'CDEFGAB'.index(st),al,st,oc

def engrave_measure(c,x,w,bottom,space,part,evs,inf,first_system=False,lyric_size=8.2):
 # All note events receive proportional time placement; initial padding permits accidentals.
 pad=12;usable=w-24
 expanded=[];ep=0
 for ev in evs:
  expanded.extend(fragments(ev,ep));ep+=ev['d']
 flat_steps=set('BEADGCF'[:max(0,-KEYS[inf['key']])]);sharp_steps=set('FCGDAEB'[:max(0,KEYS[inf['key']])]);acc_state={}
 pos=0;previous_tie=None
 layout=[]
 beamgroups=[];beamed={};positions=[];qpos=0
 for ev in expanded:positions.append(qpos);qpos+=ev['d']
 for beat in range(3):
  group=[]
  for j,ev in enumerate(expanded):
   if beat-1e-7<=positions[j]<beat+1-1e-7 and positions[j]+ev['d']<=beat+1+1e-7 and ev['p'] is not None and ev['d']<1:
    if group and abs(positions[j]-(positions[group[-1]]+expanded[group[-1]]['d']))>1e-7:
     if len(group)>1:beamgroups.append(group)
     group=[]
    group.append(j)
   elif group:
    if len(group)>1:beamgroups.append(group)
    group=[]
  if len(group)>1:beamgroups.append(group)
 for group in beamgroups:
  ys=[]
  for j in group:
   if part=='VP':ny=bottom+2*space
   else:
    dia,_,_,_=diatonic(expanded[j]['p'],inf['key'],inf['chord'],part)
    base=2*7+4 if part=='Bass' else 4*7+2;ny=bottom+(dia-base)*space/2
   ys.append(ny)
  up=np.mean(ys)<bottom+2*space or part=='VP'
  by=max(ys)+space*3.3 if up else min(ys)-space*3.3
  for j in group:beamed[j]=(up,by)
 for ei,e in enumerate(expanded):
  nx=x+pad+usable*(pos/3)
  if e['p'] is None:
   if e['d']==3:
    c.setFillColor(INK);c.rect(x+w/2-space*.75,bottom+space*2.5,space*1.5,space*.5,fill=1,stroke=0)
   elif e['d']==2:
    c.setFillColor(INK);c.rect(nx-space*.75,bottom+space*2,space*1.5,space*.5,fill=1,stroke=0)
   else:
    cp='\U0001d13d' if e['d']>=1 else ('\U0001d13f' if e['d']==.25 else '\U0001d13e')
    txt(c,nx-4,bottom+space*.7,cp,space*3.7)
    if e['d'] in [.75,1.5]:c.circle(nx+space*1.3,bottom+space*2.5,space*.18,fill=1,stroke=0)
   layout.append((e,nx,None,None));pos+=e['d'];continue
  if part=='VP':ny=bottom+2*space;di=4
  else:
   di,al,st,oc=diatonic(e['p'],inf['key'],inf['chord'],part)
   base=2*7+4 if part=='Bass' else 4*7+2
   ny=bottom+(di-base)*space/2
   expected=acc_state.get((st,oc),-1 if st in flat_steps else 1 if st in sharp_steps else 0)
   if al!=expected:
    txt(c,nx-space*2.0,ny-space*.55,{0:'\u266e',-1:'\u266d',1:'\u266f'}[al],space*3)
    acc_state[(st,oc)]=al
   for step in range(0,int((ny-bottom)/(space/2))-1,-2) if ny<bottom else []:pass
   if ny<bottom-space*.5:
    yy=bottom-space
    while yy>=ny-.2:rule(c,nx-space,yy,nx+space,yy,.6);yy-=space
   elif ny>bottom+space*4.5:
    yy=bottom+space*5
    while yy<=ny+.2:rule(c,nx-space,yy,nx+space,yy,.6);yy+=space
  if part=='VP':
   rule(c,nx-space*.55,ny-space*.45,nx+space*.55,ny+space*.45,1.0)
   rule(c,nx-space*.55,ny+space*.45,nx+space*.55,ny-space*.45,1.0)
  else:
   c.saveState();c.translate(nx,ny);c.rotate(18);c.setLineWidth(.8);c.setFillColor(INK);c.setStrokeColor(INK)
   c.ellipse(-space*.72,-space*.44,space*.72,space*.44,stroke=1,fill=0 if e['d']>=2 else 1);c.restoreState()
  up,stemy=beamed.get(ei,((ny<bottom+2*space) or part=='VP',None))
  stemx=nx+(space*.65 if up else -space*.65)
  if stemy is None:stemy=ny+(space*3.3 if up else -space*3.3)
  rule(c,stemx,ny,stemx,stemy,.8)
  if e['d'] in [.25,.5,.75] and ei not in beamed:
   # Individual flags are unambiguous and avoid collisions across lyrics.
   pth=c.beginPath();pth.moveTo(stemx,stemy);sgn=1 if up else -1
   pth.curveTo(stemx+space*2.0,stemy-sgn*space*.6,stemx+space*1.6,stemy-sgn*space*2.0,stemx+space*.5,stemy-sgn*space*2.3)
   c.setLineWidth(1.3);c.drawPath(pth)
   if e['d']==.25:
    p2=c.beginPath();p2.moveTo(stemx,stemy-sgn*space*.8);p2.curveTo(stemx+space*1.8,stemy-sgn*space*1.4,stemx+space*1.4,stemy-sgn*space*2.5,stemx+space*.5,stemy-sgn*space*2.8);c.drawPath(p2)
  if e['d'] in [.75,1.5,3]:
   dy=space*.5 if abs((ny-bottom)/space-round((ny-bottom)/space))<.05 else 0
   c.setFillColor(INK);c.circle(nx+space*1.2,ny+dy,space*.18,fill=1,stroke=0)
  if e.get('ly'):center(c,nx,bottom-space*(2.7 if part=='VP' else 5.3),e['ly'],lyric_size)
  if e.get('tie_stop') and previous_tie:
   px,py=previous_tie;pth=c.beginPath();yy=min(py,ny)-space*1.15
   pth.moveTo(px+space*.7,py-space*.75);pth.curveTo(px+(nx-px)*.3,yy-space*.75,px+(nx-px)*.7,yy-space*.75,nx-space*.7,ny-space*.75)
   c.setLineWidth(.65);c.drawPath(pth)
  if e.get('tie_stop') and not previous_tie:
   pth=c.beginPath();pth.moveTo(x+1,ny-space);pth.curveTo(x+4,ny-space*1.8,nx-space*1.2,ny-space*1.8,nx-space*.7,ny-space*.75);c.setLineWidth(.65);c.drawPath(pth)
  previous_tie=(nx,ny) if e.get('tie_start') else None
  layout.append((e,nx,ny,up));pos+=e['d']
 for group in beamgroups:
  up,by=beamed[group[0]];sgn=1 if up else -1
  xs=[layout[j][1]+(space*.65 if up else -space*.65) for j in group]
  rule(c,xs[0],by,xs[-1],by,space*.45)
  for k,j in enumerate(group):
   if expanded[j]['d']==.25:
    if k+1<len(group) and expanded[group[k+1]]['d']==.25:
     rule(c,xs[k],by-sgn*space*.8,xs[k+1],by-sgn*space*.8,space*.4)
    elif k==0 or expanded[group[k-1]]['d']!=.25:
     end=xs[k]+(space*1.1 if k==0 else -space*1.1)
     rule(c,xs[k],by-sgn*space*.8,end,by-sgn*space*.8,space*.4)
 if previous_tie:
  px,py=previous_tie;pth=c.beginPath();pth.moveTo(px+space*.7,py-space*.75);pth.curveTo(px+space*1.2,py-space*1.7,x+w-space*1.5,py-space*1.7,x+w-2,py-space);c.setLineWidth(.65);c.drawPath(pth)
 # Barline at the right edge. End of section is a double bar.
 rule(c,x+w,bottom if part!='VP' else bottom+space,x+w,bottom+4*space if part!='VP' else bottom+3*space,.55)
 nextsec=meta[inf['bar']]['section'] if inf['bar']<len(meta) else None
 if nextsec!=inf['section']:rule(c,x+w-3,bottom if part!='VP' else bottom+space,x+w-3,bottom+4*space if part!='VP' else bottom+3*space,.55)

def scorepdf(path,part=None):
 selected=[part] if part else PARTS
 w,h=(595.28,841.89) if part else (841.89,1190.55)
 c=canvas.Canvas(str(path),pagesize=(w,h));c.setTitle(TITLE+' - '+(part or 'Full score'));c.setAuthor('Music: Yuki Kajiura; student a cappella v3')
 barsper=2 if part=='Lead' else 3
 systemsper=6 if part else 2
 groups=[];pos=0
 while pos<len(meta):
  current_bars=barsper
  if part and all(e['p'] is None for e in score[part][pos]):
   current_bars=1
   while current_bars<8 and pos+current_bars<len(meta) and all(e['p'] is None for e in score[part][pos+current_bars]):current_bars+=1
  end=min(len(meta),pos+current_bars)
  for ix in range(pos+1,end):
   if meta[ix]['local']==1 or meta[ix]['key']!=meta[ix-1]['key']:end=ix;break
  groups.append(list(range(pos,end)));pos=end
 if len(groups)>1 and len(groups[-1])==1 and len(groups[-2])<=barsper:
  groups[-2].extend(groups.pop())
 for pg,gstart in enumerate(range(0,len(groups),systemsper),1):
  title(c,w,h,pg,part)
  for sysi in range(systemsper):
   if gstart+sysi>=len(groups):break
   idxs=groups[gstart+sysi];barstart=idxs[0]
   top=h-137-sysi*(110 if part else 505)
   sp=5.3 if part else 5.5
   gap=75 if not part else 70
   xleft=43 if part else 65;head=77 if part else 87
   xnotes=xleft+head;bw=(w-40-xnotes)/len(idxs)
   # bar starts and chord chart align with music across the entire system.
   for j,i in enumerate(idxs):
    inf=meta[i];xx=xnotes+j*bw
    if inf['local']==1:
     txt(c,xx,top+23,inf['section']+'  '+inf['label'],9.5,'FSB',ACCENT)
     txt(c,xx,top+10,'q = '+format(inf['tempo'],'.1f').rstrip('0').rstrip('.')+'  '+inf['dynamic'],8.5,'FSI',MUTED)
    elif i==barstart:txt(c,xx,top+23,inf['section']+' / continued',8.5,'FSI',MUTED)
    if inf['local']!=1 and i and (inf['tempo']!=meta[i-1]['tempo'] or inf['dynamic']!=meta[i-1]['dynamic']):
     txt(c,xx,top+10,'q = '+format(inf['tempo'],'.1f').rstrip('0').rstrip('.')+'  '+inf['dynamic'],8.5,'FSI',MUTED)
    
    for hh in inf['harmonies']:
     hx=xx+12+(bw-24)*hh['offset']/3
     txt(c,hx,top-1,hh['symbol'],8.5,'FSB')
    txt(c,xx+1,top+(36 if part=='Whistle' else -13),str(i+1),7,'FS',MUTED)
   for pi,p in enumerate(selected):
    bottom=top-49-pi*(68 if not part else 0)
    if not part: right(c,xleft-5,bottom+sp*1.5,SHORT[PARTS.index(p)],9,'FSB')
    if p=='VP':rule(c,xleft,bottom+2*sp,w-40,bottom+2*sp,.4)
    else:
     for l in range(5):rule(c,xleft,bottom+l*sp,w-40,bottom+l*sp,.35)
    staffhead(c,xleft,bottom,sp,p,meta[barstart]['key'],showtime=(barstart==0))
    for j,i in enumerate(idxs):
     inf=meta[i]
     if j and inf['key']!=meta[i-1]['key'] and p!='VP':
      txt(c,xnotes+j*bw+2,bottom+5*sp,'key: '+inf['key'],7,'FSI',MUTED)
     engrave_measure(c,xnotes+j*bw,bw,bottom,sp,p,score[p][i],inf,lyric_size=8.6 if part else 8.4)
    if not part:rule(c,xleft,top-49,xleft,top-49-(len(selected)-1)*68+4*sp,.7)
  c.showPage()
 c.save()
scorepdf(ROOT/'scores/EYKM_v3_Full_Score.pdf')
for p in PARTS:scorepdf(ROOT/f'parts/EYKM_v3_{p}.pdf',p)
print('Engraved full score and seven parts')
