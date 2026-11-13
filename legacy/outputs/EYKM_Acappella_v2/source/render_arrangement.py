"""Engrave and render the explicit v2 event score. No original audio embedded."""
from pathlib import Path
import json, math, itertools, struct, wave, subprocess, hashlib
from xml.etree.ElementTree import Element, SubElement, ElementTree
import numpy as np
from scipy import signal
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'source/arrangement.json').read_text())
PARTS=DATA['parts']; SHORT=['Ld.','S','A','T','B','VP','Wh.']
TITLE=DATA['title']; score=DATA['score'];meta=DATA['metadata']; RANGES=DATA['ranges']
CHORDS=DATA['chords']
KEYS={'Cm':-3,'Fm':-4,'Dm':-1,'Gm':-2,'Em':1,'Am':0,'C#m':4,'F#m':3,'Bm':2}
NOTENAMES=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
# MusicXML utilities.
def sub(el,tag,content=None,**attrs):
 q=SubElement(el,tag,{k.replace('_','-'):str(v) for k,v in attrs.items()})
 if content is not None:q.text=str(content)
 return q

def spell(n,key='Cm',chord=None):
 pc=n%12;octv=n//12-1
 scale=KEYS[key]
 names=(['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'] if scale>0 else NOTENAMES)
 if chord and chord in CHORDS:
  import re
  rn=re.match(r'([A-G])([#b]?)',chord);letter=rn[1];ralt={'':0,'#':1,'b':-1}[rn[2]]
  root,kind,tones=CHORDS[chord]
  ints=([0,3,7,10] if kind=='minor-seventh' else [0,3,7] if kind=='minor' else [0,5,7] if kind=='suspended-fourth' else [0,4,7,10] if kind=='dominant' else [0,4,7])
  steps=([0,3,4] if kind=='suspended-fourth' else [0,2,4,6])
  for semi,step in zip(ints,steps):
   if (root+semi)%12==pc:
    let='CDEFGAB'[('CDEFGAB'.index(letter)+step)%7];base=dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[let]
    alt=(pc-base+6)%12-6
    if abs(alt)<=1:return let,alt,(n-base-alt)//12-1
 leading={'Cm':(11,'B',0),'Fm':(4,'E',0),'Dm':(1,'C',1),'Gm':(6,'F',1),'Em':(3,'D',1),'Am':(8,'G',1),'C#m':(0,'B',1),'F#m':(5,'E',1),'Bm':(10,'A',1)}
 lp,ls,la=leading[key]
 if pc==lp:return ls,la,(n-dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[ls]-la)//12-1
 na=names[pc];return na[0],(-1 if 'b' in na else 1 if '#' in na else 0),octv

def fragments(e):
 d=e['d'];pieces=[]
 for value in [3,2,1.5,1,.75,.5,.25]:
  while d>=value-1e-7:
   pieces.append(value);d-=value
 assert abs(d)<1e-7
 out=[]
 for j,v in enumerate(pieces):
  x=dict(e,d=v)
  if j:x['ly']=''
  if e['p'] is not None:
   if j:x['tie_stop']=True
   if j<len(pieces)-1:x['tie_start']=True
  out.append(x)
 return out

def mkxml(path,selected):
 root=Element('score-partwise',version='4.0')
 work=sub(root,'work');sub(work,'work-title',TITLE)
 sub(root,'movement-title',TITLE+' | Full-form a cappella v2')
 ident=sub(root,'identification');sub(ident,'creator','Yuki Kajiura',type='composer');sub(ident,'creator','Full-form a cappella arrangement v2 for student ensemble',type='arranger')
 sub(ident,'rights','Internal student rehearsal edition. Original composition rights remain with their holders.')
 enc=sub(ident,'encoding');sub(enc,'software','Explicit event score / MusicXML 4.0');sub(enc,'encoding-date','2026-11-02')
 defaults=sub(root,'defaults');sc=sub(defaults,'scaling');sub(sc,'millimeters',7);sub(sc,'tenths',40)
 page=sub(defaults,'page-layout');sub(page,'page-height',1697 if len(selected)>1 else 1697);sub(page,'page-width',1200)
 marg=sub(page,'page-margins',type='both')
 for k,v in [('left-margin',65),('right-margin',65),('top-margin',65),('bottom-margin',65)]:sub(marg,k,v)
 pl=sub(root,'part-list')
 progs={'Lead':54,'Soprano':53,'Alto':53,'Tenor':53,'Bass':53,'Whistle':79,'VP':1}
 for p in selected:
  idx=PARTS.index(p);pid='P'+str(idx+1);sp=sub(pl,'score-part',id=pid)
  sub(sp,'part-name',p);sub(sp,'part-abbreviation',SHORT[idx])
  instruments=[('K','Mouth kick',37),('S','Mouth snare',39),('H','Mouth hat',43)] if p=='VP' else [('I',p,None)]
  for suffix,name,unpitched in instruments:
   ins=sub(sp,'score-instrument',id=pid+'-'+suffix);sub(ins,'instrument-name',name)
  for suffix,name,unpitched in instruments:
   mi=sub(sp,'midi-instrument',id=pid+'-'+suffix);sub(mi,'midi-channel',10 if p=='VP' else idx+1);sub(mi,'midi-program',progs[p])
   if unpitched:sub(mi,'midi-unpitched',unpitched)
 for p in selected:
  idx=PARTS.index(p);part=sub(root,'part',id='P'+str(idx+1));prevkey=None;prevtempo=None;prev_hyphen=False
  for i,m in enumerate(score[p]):
   inf=meta[i];me=sub(part,'measure',number=i+1)
   if i==0 or inf['key']!=prevkey:
    at=sub(me,'attributes');sub(at,'divisions',8)
    if p!='VP':ks=sub(at,'key');sub(ks,'fifths',KEYS[inf['key']]);sub(ks,'mode','minor')
    if i==0:
     ts=sub(at,'time');sub(ts,'beats',3);sub(ts,'beat-type',4)
     clef=sub(at,'clef');sub(clef,'sign','percussion' if p=='VP' else ('F' if p=='Bass' else 'G'))
     if p!='VP':sub(clef,'line',4 if p=='Bass' else 2)
     if p=='Tenor':sub(clef,'clef-octave-change',-1)
     if p=='VP':sd=sub(at,'staff-details');sub(sd,'staff-lines',1)
   if inf['local']==1:
    dr=sub(me,'direction',placement='above');dt=sub(dr,'direction-type');sub(dt,'rehearsal',inf['section']+' - '+inf['label'])
    dr=sub(me,'direction',placement='above');dt=sub(dr,'direction-type');sub(dt,'words',{'Lead':'Keep text, melismas and phrase shape; breathe at marked rests','Soprano':'Sustain lightly; release at rests','Alto':'Keep vowel uniform','Tenor':'Concert sound, octave treble clef','Bass':'Rounded dm; avoid heavy attacks','VP':'B=kick, pf=snare, t/ts=hat; one-line mouth percussion','Whistle':'Natural whistle, sounding pitch; breathe at rests'}[p] if i==0 else inf.get('direction','cantabile'))
    dr=sub(me,'direction',placement='below');dt=sub(dr,'direction-type');dy=sub(dt,'dynamics');sub(dy,inf['dynamic'])
   if i and inf['dynamic']!=meta[i-1]['dynamic'] and inf['local']!=1:
    dr=sub(me,'direction',placement='below');dt=sub(dr,'direction-type');dy=sub(dt,'dynamics');sub(dy,inf['dynamic'])
   if inf['tempo']!=prevtempo:
    dr=sub(me,'direction',placement='above');dt=sub(dr,'direction-type');mt=sub(dt,'metronome');sub(mt,'beat-unit','quarter');sub(mt,'per-minute',inf['tempo']);sub(dr,'sound',tempo=inf['tempo'])
   if p==selected[0] or len(selected)==1:
    h=sub(me,'harmony');rt,kind,_=CHORDS[inf['chord']];st,al,oc=spell(60+rt,inf['key'],inf['chord']);rr=sub(h,'root');sub(rr,'root-step',st)
    if al:sub(rr,'root-alter',al)
    sub(h,'kind',kind,text=inf['chord'])
   for ev in m:
    for e in fragments(ev):
     n=sub(me,'note')
     if e['p'] is None:sub(n,'rest')
     elif p=='VP':
      u=sub(n,'unpitched');sub(u,'display-step','B');sub(u,'display-octave',4)
     else:
      pi=sub(n,'pitch');st,al,oc=spell(e['p'],inf['key'],inf['chord']);sub(pi,'step',st)
      if al:sub(pi,'alter',al)
      sub(pi,'octave',oc)
     sub(n,'duration',round(e['d']*8))
     for typ in ['stop','start']:
      if e.get('tie_'+typ):sub(n,'tie',type=typ)
     if p=='VP' and e['p'] is not None:sub(n,'instrument',id='P6-'+{36:'K',38:'S',42:'H'}[e['p']])
     typ={.25:'16th',.5:'eighth',.75:'eighth',1:'quarter',1.5:'quarter',2:'half',3:'half'}[e['d']];sub(n,'type',typ)
     if e['d'] in [.75,1.5,3]:sub(n,'dot')
     if p=='VP' and e['p'] is not None:sub(n,'notehead','x')
     if e.get('tie_start') or e.get('tie_stop'):
      no=sub(n,'notations')
      for typ in ['stop','start']:
       if e.get('tie_'+typ):sub(no,'tied',type=typ)
     if e.get('ly'):
      ly=sub(n,'lyric',number='1');hy=e['ly'].endswith('-');sub(ly,'syllabic',('middle' if prev_hyphen else 'begin') if hy else ('end' if prev_hyphen else 'single'));sub(ly,'text',e['ly'].rstrip('-'));prev_hyphen=hy
   if inf['local']==len([x for x in meta if x['section']==inf['section']]):
    bl=sub(me,'barline',location='right');sub(bl,'bar-style','light-heavy' if i==len(meta)-1 else 'light-light')
   prevkey=inf['key'];prevtempo=inf['tempo']
 ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
mkxml(ROOT/'scores'/'EYKM_Full_Score.musicxml',PARTS)
for p in PARTS:mkxml(ROOT/'parts'/('EYKM_'+p+'.musicxml'),[p])

# Standard MIDI file writer, separate tracks, GM percussion channel 10.
def vlq(x):
 x=int(x);b=[x&127];x>>=7
 while x:b.insert(0,(x&127)|128);x>>=7
 return bytes(b)
def track(events):
 out=b'';last=0
 for tm,order,msg in sorted(events,key=lambda e:(e[0],e[1])):out+=vlq(tm-last)+msg;last=tm
 out+=vlq(max(0,len(meta)*3*TPQ-last))+b'\xff\x2f\x00'
 return b'MTrk'+struct.pack('>I',len(out))+out
TPQ=480
DYN={'pp':42,'p':52,'mp':63,'mf':76,'f':88}
def sounding_events(part):
 events=[]
 for i,measure in enumerate(score[part]):
  offset=0
  for e in measure:
   if e['p'] is not None:
    if e.get('tie_stop') and events and events[-1]['p']==e['p'] and abs(events[-1]['end']-(i*3+offset))<1e-7:
     events[-1]['end']+=e['d']
    else:events.append(dict(p=e['p'],start=i*3+offset,end=i*3+offset+e['d'],ly=e.get('ly',''),bar=i))
   offset+=e['d']
 return events

def writemidi(path,selected):
 ev=[(0,0,b'\xff\x58\x04\x03\x02\x18\x08')];old=None
 for i,inf in enumerate(meta):
  if inf['tempo']!=old:
   us=int(60_000_000/inf['tempo']);ev.append((i*3*TPQ,0,b'\xff\x51\x03'+us.to_bytes(3,'big')));old=inf['tempo']
  if inf['local']==1:
   t=(inf['section']+' '+inf['label']).encode();ev.append((i*3*TPQ,1,b'\xff\x06'+vlq(len(t))+t))
 tracks=[track(ev)]
 for p in selected:
  idx=PARTS.index(p);ch=9 if p=='VP' else idx
  prog={'Lead':53,'Soprano':52,'Alto':52,'Tenor':52,'Bass':52,'Whistle':78,'VP':0}[p]
  ev=[(0,0,b'\xff\x03'+vlq(len(p))+p.encode()),(0,1,bytes([0xC0|ch,prog])),(0,2,bytes([0xB0|ch,7,100]))]
  for e in sounding_events(p):
   st=round(e['start']*TPQ);en=round((e['end']-.035)*TPQ)
   vel=DYN[meta[e['bar']]['dynamic']]+(8 if p=='Lead' else (-15 if p=='VP' else -5 if p=='Whistle' else 0))
   ev.extend([(st,3,bytes([0x90|ch,e['p'],max(25,min(110,vel))])),(en,2,bytes([0x80|ch,e['p'],0]))])
  tracks.append(track(ev))
 path.write_bytes(b'MThd'+struct.pack('>IHHH',6,1,len(tracks),TPQ)+b''.join(tracks))
writemidi(ROOT/'midi'/'EYKM_All_Parts.mid',PARTS)
for p in PARTS:writemidi(ROOT/'midi'/('EYKM_'+p+'.mid'),[p])
writemidi(ROOT/'midi'/'EYKM_Without_Lead.mid',[p for p in PARTS if p!='Lead'])

# Portable vector engraving. Keep it intentionally simple: no ornamental ambiguity.
FONT_DIR=Path('/Applications/MuseScore 4.app/Contents/Resources/fonts')
pdfmetrics.registerFont(TTFont('FS',str(FONT_DIR/'FreeSerif.ttf')))
pdfmetrics.registerFont(TTFont('FSI',str(FONT_DIR/'FreeSerifItalic.ttf')))
pdfmetrics.registerFont(TTFont('FSB',str(FONT_DIR/'FreeSerifBold.ttf')))
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
INK=colors.HexColor('#17212b');MUTED=colors.HexColor('#536879');ACCENT=colors.HexColor('#176477')

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
 txt(c,38,h-57,'SATB + vocal percussion + lead + whistle | Full-form arrangement v2 / rehearsal edition',9,'FS',MUTED)
 if part:txt(c,38,h-78,part.upper()+'  /  CONCERT PITCH' + (' - treble clef sounds 8vb' if part=='Tenor' else ''),11,'FSB',ACCENT)
 else:txt(c,38,h-78,'CONDUCTOR SCORE  /  A3 PORTRAIT',11,'FSB',ACCENT)
 rule(c,38,h-90,w-38,h-90,.8,ACCENT)
 txt(c,38,25,'Student ensemble internal rehearsal edition | Synth demo is a pitch/rhythm guide',8,'FS',MUTED)
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
 expanded=[e for ev in evs for e in fragments(ev)]
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
 c=canvas.Canvas(str(path),pagesize=(w,h));c.setTitle(TITLE+' - '+(part or 'Full score'));c.setAuthor('Music: Yuki Kajiura; full-form student a cappella v2')
 barsper=3 if part in ['Lead','Whistle','Tenor','Alto'] else 4
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
    txt(c,xx+3,top-1,inf['chord'],9.5,'FSB')
    txt(c,xx+1,top+(36 if part=='Whistle' else -13),str(i+1),7,'FS',MUTED)
   for pi,p in enumerate(selected):
    bottom=top-49-pi*(62 if not part else 0)
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
    if not part:rule(c,xleft,top-49,xleft,top-49-(len(selected)-1)*62+4*sp,.7)
  c.showPage()
 c.save()
scorepdf(ROOT/'scores'/'EYKM_Full_Score.pdf')
for p in PARTS:scorepdf(ROOT/'parts'/('EYKM_'+p+'.pdf'),p)

import sys
if '--notation-only' in sys.argv:
 print('Notation exports complete',flush=True)
 sys.exit(0)

# Synthetic rehearsal renderer: additive vowels, whistle, and procedural mouth-percussion proxy.
SR=22050;COUNT=6*60/meta[0]['tempo']
starts=[COUNT]
for inf in meta:starts.append(starts[-1]+3*60/inf['tempo'])
length=int((starts[-1]+2)*SR)
rng=np.random.default_rng(241102)
def synth(n,d,p,ly):
 Nn=max(1,int(d*SR));t=np.arange(Nn)/SR
 if p=='VP':
  noise=rng.normal(0,1,Nn)
  if n==36:
   ph=2*np.pi*(45*t+(100-45)*.035*(1-np.exp(-t/.035)));z=np.sin(ph)*np.exp(-t*20)+.1*noise*np.exp(-t*80)
  elif n==38:z=.7*np.concatenate(([0],np.diff(noise)))*np.exp(-t*35)+.25*np.sin(2*np.pi*170*t)*np.exp(-t*24)
  else:z=np.concatenate(([0],np.diff(noise)))*np.exp(-t*65)*.28
  return z.astype(np.float32)
 f=440*2**((n-69)/12)
 vib=(.0025 if p!='Whistle' else .0012)*np.minimum(1,t/.3)*np.sin(2*np.pi*(4.8 if p=='Whistle' else 5.4)*t)
 phase=2*np.pi*f*np.cumsum(1+vib)/SR
 if p=='Whistle':z=np.sin(phase)+.06*np.sin(2*phase)
 else:
  # Resonant additive vowels approximate choir timbre; no synthesized words or sampled singer.
  vowels=(700,1200,2600) if ly=='ah' or p=='Lead' else (350,900,2300)
  z=np.zeros(Nn)
  for h in range(1,min(28,int(9000/f))):
   hf=f*h;form=sum(np.exp(-.5*((hf-v)/(130+v*.10))**2) for v in vowels)
   weight=(.22+.9*form)/h**1.05
   z+=weight*np.sin(h*phase+.07*h)
  z/=max(.5,np.max(np.abs(z)))
 attack=.035 if p=='Whistle' else .055;release=.075
 env=np.minimum(1,t/attack)*np.minimum(1,np.maximum(0,(d-t)/release))
 return (z*env).astype(np.float32)
# Rendering each part once makes the full mix and emphasis tracks exactly consistent.
stems={}
for p in PARTS:
 arr=np.zeros(length,np.float32)
 def beattime(q):
  i=min(len(meta)-1,int(q//3));return starts[i]+(q-i*3)*60/meta[i]['tempo']
 for e in sounding_events(p):
  pos=beattime(e['start']);dur=beattime(e['end'])-pos
  amp=DYN[meta[e['bar']]['dynamic']]/100
  d=max(.05,dur-(.04 if p=='Whistle' else .025));z=synth(e['p'],d,p,e.get('ly',''))
  ix=int(pos*SR);arr[ix:ix+len(z)]+=z*amp
 stems[p]=arr
 print('Rendered',p,flush=True)
# Two 3/4 bars of count-in, then no click. Distinct high beat 1 / low beats 2 and 3.
click=np.zeros(length,np.float32)
for i in range(6):
 t=np.arange(int(.04*SR))/SR;z=np.sin(2*np.pi*(1300 if i%3==0 else 900)*t)*np.exp(-t*90)*.32
 st=int(i*60/meta[0]['tempo']*SR);click[st:st+len(z)]=z
PAN={'Lead':0,'Soprano':-.45,'Alto':-.2,'Tenor':.2,'Bass':0,'VP':.1,'Whistle':.45}
GAIN={'Lead':.53,'Soprano':.23,'Alto':.23,'Tenor':.26,'Bass':.38,'VP':.17,'Whistle':.35}
def render_mix(filename,focus=None,omit=None):
 mix=np.zeros((length,2),np.float32)
 for p,a in stems.items():
  if p==omit:continue
  gain=GAIN[p]*(2.3 if p==focus else .40 if focus else 1)
  pan=PAN[p] if not focus else (0 if p==focus else PAN[p])
  mix[:,0]+=a*gain*math.sqrt((1-pan)/2);mix[:,1]+=a*gain*math.sqrt((1+pan)/2)
 mix[:,0]+=click;mix[:,1]+=click
 # Gentle, fixed room response. No effect affects the time grid or note data.
 for delay,g in [(0.047,.10),(.081,.07),(.137,.035)]:
  n=int(delay*SR);mix[n:]+=mix[:-n].copy()*g
 peak=np.max(abs(mix));mix*=.88/max(1,peak)
 wav=ROOT/'audio'/(filename+'.wav')
 with wave.open(str(wav),'wb') as f:f.setnchannels(2);f.setsampwidth(2);f.setframerate(SR);f.writeframes((mix*32767).astype('<i2').tobytes())
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-codec:a','libmp3lame','-b:a','96k',str(wav.with_suffix('.mp3'))],check=True)
 wav.unlink()
render_mix('EYKM_Full_Mix')
for p in PARTS:render_mix('EYKM_Focus_'+p,focus=p)
render_mix('EYKM_Without_Lead',omit='Lead')
# Cue timings distinguish the musical start from the two-bar count-in.
cues=[]
for i,inf in enumerate(meta):
 if inf['local']==1:cues.append(dict(section=inf['section'],name=inf['label'],bar=i+1,mp3_time=starts[i],music_time=starts[i]-COUNT,key=inf['key'],source_time=inf.get('source_time')))
(ROOT/'source'/'cues.json').write_text(json.dumps(cues,indent=2))
(ROOT/'source'/'validation.json').write_text(json.dumps(dict(measures=len(meta),parts=len(PARTS),time_signature='3/4',musical_seconds=starts[-1]-COUNT,count_in_seconds=COUNT,audio_seconds=length/SR,concert_ranges=RANGES,measure_durations='all exactly 3 quarter notes',SATB_crossing='none at any event boundary',pitch_source='Local source separation and pitch/onset analysis, with editorial transcription and new SATB/VP orchestration',human_listening_review=False,version='2.0',source_seconds=299.106667),indent=2))
print('FINISHED',len(meta),starts[-1]-COUNT,RANGES,flush=True)
