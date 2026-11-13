"""Build a theme-based student a cappella arrangement from explicitly authored events.
Python 3 + numpy + scipy + reportlab. Source audio is NOT packaged or used at playback.
Pitches are concert MIDI values; tenor uses octave-transposing treble clef.
"""
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
PARTS=['Lead','Soprano','Alto','Tenor','Bass','VP','Whistle']
SHORT=['Ld.','S','A','T','B','VP','Wh.']
TITLE='everytime you kissed me'
NOTENAMES=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']

def N(s):
 if s=='r':return None
 import re
 m=re.match(r'([A-G])([b#]?)(\d)',s)
 return (int(m[3])+1)*12+dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[m[1]]+{'':0,'b':-1,'#':1}[m[2]]
def E(p,d,ly='',**kw):return dict(p=N(p) if isinstance(p,str) else p,d=float(d),ly=ly,**kw)
def line(s):
 return [E(a.split(':')[0],float(a.split(':')[1])) for a in s.split()]
def transpose(ms,delta):return [[dict(e,p=e['p']+delta if e['p'] is not None else None) for e in m] for m in ms]
# Theme A: deliberately regularized, singable phrasing; no claim of critical transcription.
A=[line(s) for s in [
 'Eb4:.5 D4:.5 C4:1 D4:.5 Eb4:.5',
 'D4:1.5 Eb4:.5 D4:1',
 'C4:.5 D4:.5 C4:1 Bb3:1',
 'Bb3:2.5 r:.5',
 'Eb4:.5 D4:.5 C4:1 D4:.5 Eb4:.5',
 'D4:2 D4:1',
 'C4:1 Eb4:1 F4:1',
 'Eb4:2.5 r:.5',
 'G4:.5 F4:.5 Eb4:1 D4:.5 Eb4:.5',
 'D4:1 D4:.5 Eb4:.5 D4:1',
 'C4:.5 D4:.5 C4:1 Bb3:1',
 'Bb3:2.5 r:.5',
 'C4:1 Eb4:1 F4:1',
 'D4:1.5 Eb4:.5 D4:1',
 'Bb3:1 C4:2',
 'C4:2.5 r:.5']]
B=[line(s) for s in [
 'Ab4:1 G4:1 F4:1', 'G4:1.5 Ab4:.5 G4:1',
 'F4:.5 G4:.5 F4:1 Eb4:1', 'Eb4:2.5 r:.5',
 'Ab4:1 G4:1 F4:1', 'Ab4:1 G4:1 F4:1',
 'F4:1 Ab4:1 Bb4:1', 'C5:1 Bb4:1 Ab4:.5 r:.5',
 'Ab4:.5 G4:.5 F4:1 G4:.5 Ab4:.5',
 'G4:1 Ab4:.5 G4:.5 Eb4:1',
 'F4:.5 G4:.5 F4:1 Eb4:.5 F4:.5', 'Eb4:2.5 r:.5',
 'F4:1 G4:1 Ab4:1', 'G4:1 Ab4:1 G4:1',
 'Eb4:1 F4:2', 'F4:2.5 r:.5']]
# New whistle obbligato, using the stepwise and falling-third vocabulary of the source.
W=[line(s) for s in [
 'F5:1 Ab5:.5 G5:.5 F5:1', 'Eb5:1 G5:1 C6:1',
 'Db6:1 C6:.5 Bb5:.5 Ab5:1', 'C6:2 r:1',
 'Ab5:.5 G5:.5 F5:1 Ab5:1', 'G5:1 Eb5:.5 F5:.5 G5:1',
 'Ab5:.5 Bb5:.5 Ab5:1 F5:1', 'Eb5:2 r:1',
 'F5:.5 G5:.5 Ab5:1 C6:1', 'Bb5:1 G5:1 Eb5:1',
 'Ab5:1 F5:.5 Eb5:.5 Db5:1', 'Eb5:2 r:1',
 'F5:1 Ab5:1 Bb5:1', 'G5:1 E5:.5 G5:.5 C6:1',
 'Ab5:1 G5:1 F5:1', 'F5:2 r:1']]
INTRO=[line(s) for s in ['G5:1 C6:1 D6:1','Eb6:1 D6:1 Bb5:1','Ab5:2 G5:1','Eb5:2 r:1','F5:1 Ab5:1 C6:1','Bb5:1 Ab5:1 G5:1','F5:1 Ab5:1 G5:1','G5:2 r:1']]
# Newly composed wordless bridge in G minor, eight-bar question and response.
BR=[line(s) for s in ['G4:2 Bb4:1','A4:1 G4:1 F4:1','Eb4:2 G4:1','F4:2 r:1','D4:1 F4:1 G4:1','A4:2 G4:1','Gb4:1 A4:1 C5:1','Bb4:2 r:1']]
A2=transpose(A,2)
A2[1]=line('E4:.5 F4:.5 E4:1 E4:1')
A2[7]=line('F4:1 F4:1.5 r:.5')
LY_A1=['Ev- er- y time you kissed me I trem- bled like a child','Ga- ther- ing the ro- ses we sang for the hope','Your ve- ry voice is in my heart- beat sweet- er than my dream','We were there in ev- er- last- ing bloom']
LY_A2=['Sil- ver dish- es for the mem- o- ries for the days gone by','Sing- ing for the prom- is- es to- mor- row may bring','I har- bour all the old af- fec- tion ro- ses of the past','Dark- ness falls and sum- mer will be gone']
LY_A3=['Ev- er- y time you kissed me my heart was in such pain','Ga- ther- ing the ro- ses we sang of the grief','Your ve- ry voice is in my heart- beat sweet- er than des- pair','We were there in ev- er- last- ing bloom']
LY_B=['Ro- ses die the se- cret is in- side the pain','Winds are high up- on the hill I can- not hear you','Come and hold me close I\'m shiv- er- ing cold in the heart of rain','Dark- ness falls I\'m call- ing for the dawn']

def underlay(mel,lyrics):
 mel=transpose(mel,0)
 for j,phrase in enumerate(lyrics):
  ev=[e for m in mel[j*4:j*4+4] for e in m if e['p'] is not None]
  sy=phrase.split()
  assert len(ev)==len(sy),(j,len(ev),len(sy),phrase)
  for e,l in zip(ev,sy):e['ly']=l
 return mel
A1=underlay(A,LY_A1);A2=underlay(A2,LY_A2);A3=underlay(A,LY_A3);B1=underlay(B,LY_B)
# Chord plans: basic harmonic skeleton with original inner-voice writing.
HA=['Cm','Gm','Ab','Eb']*3+['Fm','Gm','Cm','Cm']
HB=['Fm','Cm','Db','Ab']*3+['Bbm','C7','Fm','Fm']
HC=['Dm','Am','Bb','F']*3+['Gm','A7','Dm','Dm']
HBR=['Gm','Dm','Eb','Bb','Cm','Am7b5','D7','Gm']*2
HBR[-2:]=['Ab','G7']
HCO=['Cm','Gm','Ab','Eb','Fm','G7','Cm','C7','Fm','Db','Bbm','C7','Fm','C7','Fm','Fm']
SECTIONS=[
 ('I','Introduction',8,'Cm',108,['Cm','Gm','Ab','Eb','Fm','Bb','Ab','G7'],'intro'),
 ('A','Verse 1',16,'Cm',126,HA,'verse'),
 ('B','Roses',16,'Fm',126,HB,'full'),
 ('C','Whistle interlude',16,'Fm',126,HB,'whistle'),
 ('D','Verse 2',16,'Dm',126,HC,'verse2'),
 ('E','Wordless bridge',16,'Gm',126,HBR,'bridge'),
 ('F','Verse 3',16,'Cm',126,HA,'reprise'),
 ('G','Wordless refrain',16,'Fm',126,HB,'climax'),
 ('H','Coda',16,'Fm',118,HCO,'coda')]
# Four independent pitch lines, all within practical student ranges. S A T B.
VO={
 'Cm':[67,63,60,48], 'Gm':[67,62,58,43], 'Ab':[68,63,60,44], 'Eb':[67,63,58,51],
 'Fm':[68,65,60,41], 'Bb':[65,62,58,46], 'G7':[65,62,59,43],
 'Db':[68,65,61,49], 'Bbm':[70,65,61,46], 'C7':[67,64,58,48],
 'Dm':[69,65,62,50], 'Am':[69,64,60,45], 'F':[69,65,60,41],
 'A7':[67,64,61,45], 'Am7b5':[67,63,60,45], 'D7':[69,66,60,50]
}
CHORDS={
 'Cm':(0,'minor',[0,3,7]),'Gm':(7,'minor',[7,10,2]),'Ab':(8,'major',[8,0,3]),'Eb':(3,'major',[3,7,10]),
 'Fm':(5,'minor',[5,8,0]),'Bb':(10,'major',[10,2,5]),'G7':(7,'dominant',[7,11,2,5]),
 'Db':(1,'major',[1,5,8]),'Bbm':(10,'minor',[10,1,5]),'C7':(0,'dominant',[0,4,7,10]),
 'Dm':(2,'minor',[2,5,9]),'Am':(9,'minor',[9,0,4]),'F':(5,'major',[5,9,0]),
 'A7':(9,'dominant',[9,1,4,7]),'Am7b5':(9,'half-diminished',[9,0,3,7]),'D7':(2,'dominant',[2,6,9,0])}
KEYS={'Cm':-3,'Fm':-4,'Dm':-1,'Gm':-2}
score={p:[] for p in PARTS};meta=[]
def rest():return [E(None,3)]
def hum(p,d=3,vowel='oo'):return [E(p,d,vowel)]
def phrase_breath(evs,j,voice):
 # All sustained singers have a written release; not dependent on divisi or circular breathing.
 if j%4==(voice%4) and len(evs)==1 and evs[0]['d']==3 and evs[0]['p'] is not None:
  evs=[dict(evs[0],d=2.5),E(None,.5)]
 return evs

def backing(ch,style,j,offset):
 s,a,t,b=VO[ch]; root=CHORDS[ch][0]
 fifth=b+7
 if fifth>55:fifth-=12
 out={}
 if style=='intro':
  out['Soprano']=rest() if j<4 else hum(s,3,'mm')
  out['Alto']=hum(a,3,'mm');out['Tenor']=rest() if j<2 else hum(t,3,'mm')
  out['Bass']=hum(b,3,'dm');out['VP']=rest()
 elif style in ['verse','verse2','reprise']:
  out['Soprano']=rest() if style=='verse' and j<4 else hum(s,3,'oo')
  out['Alto']=hum(a,3,'oo')
  out['Tenor']=[E(None,1),E(t,1,'du'),E(t,1,'du')] if j<8 else [E(t,1.5,'du'),E(None,.5),E(t,1,'du')]
  out['Bass']=[E(b,1.5,'dm'),E(None,.5),E(fifth,1,'dm')]
  out['VP']=rest() if style=='verse' and j<8 else [E(42,.5,'t'),E(None,.5),E(38,.5,'pf'),E(None,.5),E(42,.5,'t'),E(None,.5)]
 else:
  out['Soprano']=[E(s,2,'ah'),E(s,1,'ah')]
  out['Alto']=[E(a,1.5,'oo'),E(None,.5),E(a,1,'oo')]
  out['Tenor']=[E(t,1,'du'),E(t,.5,'da'),E(None,.5),E(t,1,'du')]
  out['Bass']=[E(b,1,'dm'),E(fifth,1,'dn'),E(b,.5,'dm'),E(None,.5)]
  out['VP']=[E(36,.5,'B'),E(42,.5,'t'),E(38,.5,'pf'),E(42,.5,'t'),E(42,.5,'ts'),E(None if j%4==3 else 42,.5,'' if j%4==3 else 't')]
  if style=='whistle':
   out['Soprano']=hum(s,3,'oo');out['Alto']=hum(a,3,'oo')
  if style=='climax':
   out['Soprano']=hum({'Fm':72,'Cm':75,'Db':77,'Ab':75,'Bbm':77,'C7':76}[ch],3,'ah')
  if style=='bridge':
   out['Alto']=hum(a,3,'ah');out['Tenor']=hum(t,3,'oo')
   if j<8:
    out['Soprano']=transpose([BR[j]],0)[0]
    for e in out['Soprano']:
     if e['p'] is not None:e['ly']='ah'
    # Avoid soprano crossing the sustained alto in the new exposed melody.
    amin=min(e['p'] for e in out['Soprano'] if e['p'] is not None)
    if a>=amin:
     aa=max(x for x in range(55,amin) if x%12 in CHORDS[ch][2])
     out['Alto']=hum(aa,3,'oo')
     if t>=aa:
      tt=max(x for x in range(48,aa) if x%12 in CHORDS[ch][2])
      out['Tenor']=hum(tt,3,'oo')
   if j in [0,1,14,15]:out['VP']=rest()
 if style=='coda':
  out['Soprano']=hum(s,3,'oo');out['Alto']=hum(a,3,'oo');out['Tenor']=hum(t,3,'mm');out['Bass']=hum(b,3,'dm')
  if j>=8:out['VP']=rest()
  if j>=12:
   for p in ['Soprano','Alto','Tenor','Bass']:out[p]=hum({'Soprano':s,'Alto':a,'Tenor':t,'Bass':b}[p],3,'mm')
 for vi,p in enumerate(['Soprano','Alto','Tenor','Bass']):out[p]=phrase_breath(out[p],j,vi)
 return out

for sec,label,bars,key,bpm,chs,style in SECTIONS:
 for j,ch in enumerate(chs):
  k=len(meta);tempo=bpm
  if style=='coda':tempo=118 if j<8 else (112 if j<12 else [106,100,92,80][j-12])
  dyn={'intro':'pp','verse':'p','full':'mf','whistle':'mp','verse2':'mp','bridge':'mp','reprise':'mf','climax':'f','coda':'p'}[style]
  if style=='coda' and j>=12:dyn='pp'
  if style=='verse' and j>=8:dyn='mp'
  if style=='bridge' and j>=8:dyn='mf'
  info=dict(bar=k+1,section=sec,label=label,local=j+1,key=('Cm' if style=='coda' and j<8 else key),tempo=tempo,chord=ch,style=style,dynamic=dyn)
  meta.append(info)
  ev=backing(ch,style,j,k)
  lead=rest();wh=rest()
  if sec=='I':wh=INTRO[j]
  elif sec=='A':lead=A1[j]
  elif sec=='B':lead=B1[j]
  elif sec=='C':wh=W[j]
  elif sec=='D':lead=A2[j]
  elif sec=='E':
   if j>=8:
    lead=transpose([BR[j-8]],0)[0]
    for e in lead:
     if e['p'] is not None:e['ly']='ah'
    if j in [14,15]:lead=[E(67,2,'ah'),E(None,1)]
   if j in [3,7,11,15]:wh=[E(None,1),E(79,.5),E(77,.5),E(75,1)]
  elif sec=='F':lead=A3[j]
  elif sec=='G':
   lead=transpose([B[j]],0)[0]
   for e in lead:
    if e['p'] is not None:e['ly']='ah'
   if j in [3,7,11]:wh=[E(None,1),E(84,1),E(80,1)]
  elif sec=='H':
   if j<8:wh=transpose([A[j]],12)[0]
   elif j<12:wh=transpose([B[j-8]],12)[0]
   elif j==12:wh=line('Ab5:1 G5:1 F5:1')
   elif j==13:wh=line('E5:2 r:1')
   elif j==14:wh=line('F5:2 r:1')
   else:wh=rest()
   if j>=8:lead=[E(65,2.5,'mm'),E(None,.5)] if j in [8,10,12,14] else rest()
  ev['Lead']=lead;ev['Whistle']=wh
  for p in PARTS:score[p].append([dict(x) for x in ev[p]])
# Define a common final release; no synthetic hold beyond the notated last measure.
for p in ['Soprano','Alto','Tenor','Bass']:score[p][-1]=hum(VO['Fm'][['Soprano','Alto','Tenor','Bass'].index(p)],3,'mm')

# Normalize and validate all measures, lyric counts, and sensible concert ranges.
for p in PARTS:
 for i,m in enumerate(score[p]):
  assert abs(sum(e['d'] for e in m)-3)<1e-8,(p,i,m)
  for e in m:assert e['d']>0 and e['d']*2==int(e['d']*2)
RANGES={p:(min(e['p'] for m in score[p] for e in m if e['p'] is not None),max(e['p'] for m in score[p] for e in m if e['p'] is not None)) for p in PARTS if p!='VP'}
for p,(lo,hi) in RANGES.items():
 assert {'Lead':(55,77),'Soprano':(60,79),'Alto':(55,72),'Tenor':(48,65),'Bass':(40,55),'Whistle':(70,87)}[p][0]<=lo
 assert hi<={'Lead':77,'Soprano':79,'Alto':72,'Tenor':65,'Bass':55,'Whistle':87}[p]
for i in range(len(meta)):
 # active SATB voices may touch but may not cross at any event boundary.
 boundaries=sorted(set([0]+[sum(x['d'] for x in score[p][i][:j]) for p in PARTS[1:5] for j in range(len(score[p][i]))]))
 for tm in boundaries:
  vals=[]
  for p in PARTS[1:5]:
   cur=0;v=None
   for e in score[p][i]:
    if cur<=tm<cur+e['d']:v=e['p'];break
    cur+=e['d']
   vals.append(v)
  sounding=[v for v in vals if v is not None]
  if sounding!=sorted(sounding,reverse=True):raise AssertionError(('crossing',i+1,tm,vals))
DATA=dict(title=TITLE,version='1.0 - theme-based rehearsal arrangement',parts=PARTS,metadata=meta,score=score,ranges=RANGES,reference='EYKM.flac supplied by user; no original audio is embedded',source_sha256='cd778800ffa27af355596d968563eba26520a95cd367935b2f0952778505b2db')
(ROOT/'source'/'arrangement.json').write_text(json.dumps(DATA,ensure_ascii=False,indent=2))

# MusicXML utilities.
def sub(el,tag,content=None,**attrs):
 q=SubElement(el,tag,{k.replace('_','-'):str(v) for k,v in attrs.items()})
 if content is not None:q.text=str(content)
 return q

def spell(n,key='Cm',chord=None):
 pc=n%12; octv=n//12-1
 # Leading tones are written as sharps in sharp-side minor harmonies.
 if pc==6 and (key=='Gm' or chord=='D7'):return 'F',1,octv
 if pc==1 and (key=='Dm' or chord=='A7'):return 'C',1,octv
 na=NOTENAMES[pc]
 return na[0],(-1 if len(na)>1 else 0),octv

def fragments(e):
 if e['d']==2.5:
  a=dict(e,d=2,tie_start=True);b=dict(e,d=.5,ly='',tie_stop=True)
  return [a,b]
 return [dict(e)]

def mkxml(path,selected):
 root=Element('score-partwise',version='4.0')
 work=sub(root,'work');sub(work,'work-title',TITLE)
 sub(root,'movement-title',TITLE+' | Student chamber a cappella')
 ident=sub(root,'identification');sub(ident,'creator','Yuki Kajiura',type='composer');sub(ident,'creator','Theme arrangement prepared with ChatGPT for student rehearsal',type='arranger')
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
    dr=sub(me,'direction',placement='above');dt=sub(dr,'direction-type');sub(dt,'words',{'Lead':'Theme phrasing; original ornaments optional','Soprano':'Sustain lightly; release at rests','Alto':'Keep vowel uniform','Tenor':'Concert sound, octave treble clef','Bass':'Rounded dm; avoid heavy attacks','VP':'B=kick, pf=snare, t/ts=hat; one-line mouth percussion','Whistle':'Natural whistle, sounding pitch; breathe at rests'}[p] if i==0 else {'intro':'dolce','verse':'sotto voce','full':'cantabile','whistle':'leggero','verse2':'flowing','bridge':'wordless; conversational','reprise':'espressivo','climax':'open ah; lead remains clear','coda':'diminuendo; no added hold'}[inf['style']])
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
     typ={.5:'eighth',1:'quarter',1.5:'quarter',2:'half',3:'half'}[e['d']];sub(n,'type',typ)
     if e['d'] in [1.5,3]:sub(n,'dot')
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
  for i,m in enumerate(score[p]):
   pos=i*3
   for e in m:
    if e['p'] is not None:
     st=round(pos*TPQ);en=round((pos+e['d']-(.05 if e['d']<=1 else .09))*TPQ)
     vel=DYN[meta[i]['dynamic']]+(8 if p=='Lead' else (-15 if p=='VP' else -5 if p=='Whistle' else 0))
     ev.extend([(st,3,bytes([0x90|ch,e['p'],max(25,min(110,vel))])),(en,2,bytes([0x80|ch,e['p'],0]))])
    pos+=e['d']
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
 txt(c,38,h-57,'SATB + vocal percussion + lead + whistle | Theme arrangement / rehearsal draft 1',9,'FS',MUTED)
 if part:txt(c,38,h-78,part.upper()+'  /  CONCERT PITCH' + (' - treble clef sounds 8vb' if part=='Tenor' else ''),11,'FSB',ACCENT)
 else:txt(c,38,h-78,'CONDUCTOR SCORE  /  A3 PORTRAIT',11,'FSB',ACCENT)
 rule(c,38,h-90,w-38,h-90,.8,ACCENT)
 txt(c,38,25,'Student ensemble internal rehearsal edition | Synth demo is a pitch/rhythm guide',8,'FS',MUTED)
 right(c,w-38,25,str(page),9)

def keyglyphs(c,x,bottom,space,key,clef):
 # flats in B E A D G order; bass placements one diatonic step lower.
 vals=[4,7,3,6,2] if clef!='bass' else [2,5,1,4,0]
 for i in range(-KEYS[key]):txt(c,x+i*space*1.25,bottom+vals[i]*space/2-1,'\u266d',space*3.1)
 return x+(-KEYS[key])*space*1.25

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
 flat_steps=set('BEADG'[:max(0,-KEYS[inf['key']])]);acc_state={}
 pos=0;previous_tie=None
 layout=[]
 for e in expanded:
  nx=x+pad+usable*(pos/3)
  if e['p'] is None:
   if e['d']==3:
    c.setFillColor(INK);c.rect(x+w/2-space*.75,bottom+space*2.5,space*1.5,space*.5,fill=1,stroke=0)
   elif e['d']==2:
    c.setFillColor(INK);c.rect(nx-space*.75,bottom+space*2,space*1.5,space*.5,fill=1,stroke=0)
   else:
    cp='\U0001d13d' if e['d']>=1 else '\U0001d13e'
    txt(c,nx-4,bottom+space*.7,cp,space*3.7)
    if e['d']==1.5:c.circle(nx+space*1.3,bottom+space*2.5,space*.18,fill=1,stroke=0)
   layout.append((e,nx,None,None));pos+=e['d'];continue
  if part=='VP':ny=bottom+2*space;di=4
  else:
   di,al,st,oc=diatonic(e['p'],inf['key'],inf['chord'],part)
   base=2*7+4 if part=='Bass' else 4*7+2
   ny=bottom+(di-base)*space/2
   expected=acc_state.get((st,oc),-1 if st in flat_steps else 0)
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
  up=(ny<bottom+2*space) or part=='VP'
  stemx=nx+(space*.65 if up else -space*.65);stemy=ny+(space*3.3 if up else -space*3.3)
  rule(c,stemx,ny,stemx,stemy,.8)
  if e['d']==.5:
   # Individual flags are unambiguous and avoid collisions across lyrics.
   pth=c.beginPath();pth.moveTo(stemx,stemy);sgn=1 if up else -1
   pth.curveTo(stemx+space*2.0,stemy-sgn*space*.6,stemx+space*1.6,stemy-sgn*space*2.0,stemx+space*.5,stemy-sgn*space*2.3)
   c.setLineWidth(1.3);c.drawPath(pth)
  if e['d'] in [1.5,3]:
   dy=space*.5 if abs((ny-bottom)/space-round((ny-bottom)/space))<.05 else 0
   c.setFillColor(INK);c.circle(nx+space*1.2,ny+dy,space*.18,fill=1,stroke=0)
  if e.get('ly'):center(c,nx,bottom-space*(2.7 if part=='VP' else 5.3),e['ly'],lyric_size)
  if e.get('tie_stop') and previous_tie:
   px,py=previous_tie;pth=c.beginPath();yy=min(py,ny)-space*1.15
   pth.moveTo(px+space*.7,py-space*.75);pth.curveTo(px+(nx-px)*.3,yy-space*.75,px+(nx-px)*.7,yy-space*.75,nx-space*.7,ny-space*.75)
   c.setLineWidth(.65);c.drawPath(pth)
  previous_tie=(nx,ny) if e.get('tie_start') else None
  layout.append((e,nx,ny,up));pos+=e['d']
 # Barline at the right edge. End of section is a double bar.
 rule(c,x+w,bottom if part!='VP' else bottom+space,x+w,bottom+4*space if part!='VP' else bottom+3*space,.55)
 nextsec=meta[inf['bar']]['section'] if inf['bar']<len(meta) else None
 if nextsec!=inf['section']:rule(c,x+w-3,bottom if part!='VP' else bottom+space,x+w-3,bottom+4*space if part!='VP' else bottom+3*space,.55)


def scorepdf(path,part=None):
 selected=[part] if part else PARTS
 w,h=(595.28,841.89) if part else (841.89,1190.55)
 c=canvas.Canvas(str(path),pagesize=(w,h));c.setTitle(TITLE+' - '+(part or 'Full score'));c.setAuthor('Music: Yuki Kajiura; student theme arrangement')
 barsper=3 if part=='Lead' else 4
 systemsper=6 if part else 2
 groups=[];pos=0
 while pos<len(meta):
  end=min(len(meta),pos+barsper)
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
   xleft=43 if part else 65;head=65 if part else 77
   xnotes=xleft+head;bw=(w-40-xnotes)/len(idxs)
   # bar starts and chord chart align with music across the entire system.
   for j,i in enumerate(idxs):
    inf=meta[i];xx=xnotes+j*bw
    if inf['local']==1:
     txt(c,xx,top+23,inf['section']+'  '+inf['label'],9.5,'FSB',ACCENT)
     txt(c,xx,top+10,'q = '+str(inf['tempo'])+'  '+inf['dynamic'],8.5,'FSI',MUTED)
    elif i==barstart:txt(c,xx,top+23,inf['section']+' / continued',8.5,'FSI',MUTED)
    if inf['local']!=1 and i and (inf['tempo']!=meta[i-1]['tempo'] or inf['dynamic']!=meta[i-1]['dynamic']):
     txt(c,xx,top+10,'q = '+str(inf['tempo'])+'  '+inf['dynamic'],8.5,'FSI',MUTED)
    txt(c,xx+3,top-1,inf['chord'],9.5,'FSB')
    txt(c,xx+1,top-13,str(i+1),7,'FS',MUTED)
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
SR=22050;COUNT=6*60/108
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
 for i,m in enumerate(score[p]):
  sec=60/meta[i]['tempo'];pos=starts[i]
  amp=DYN[meta[i]['dynamic']]/100
  for e in m:
   dur=e['d']*sec
   if e['p'] is not None:
    d=max(.07,dur-(.04 if p=='Whistle' else .025));z=synth(e['p'],d,p,e.get('ly',''))
    ix=int(pos*SR);arr[ix:ix+len(z)]+=z*amp
   pos+=dur
 stems[p]=arr
 print('Rendered',p,flush=True)
# Two 3/4 bars of count-in, then no click. Distinct high beat 1 / low beats 2 and 3.
click=np.zeros(length,np.float32)
for i in range(6):
 t=np.arange(int(.04*SR))/SR;z=np.sin(2*np.pi*(1300 if i%3==0 else 900)*t)*np.exp(-t*90)*.32
 st=int(i*60/108*SR);click[st:st+len(z)]=z
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
 if inf['local']==1:cues.append(dict(section=inf['section'],name=inf['label'],bar=i+1,mp3_time=starts[i],music_time=starts[i]-COUNT,key=inf['key']))
(ROOT/'source'/'cues.json').write_text(json.dumps(cues,indent=2))
(ROOT/'source'/'validation.json').write_text(json.dumps(dict(measures=len(meta),parts=len(PARTS),time_signature='3/4',musical_seconds=starts[-1]-COUNT,count_in_seconds=COUNT,audio_seconds=length/SR,concert_ranges=RANGES,measure_durations='all exactly 3 quarter notes',SATB_crossing='none at any event boundary',pitch_source='hand-authored theme adaptation informed by supplied-audio spectral analysis; not a critical transcription',human_listening_review=False),indent=2))
print('FINISHED',len(meta),starts[-1]-COUNT,RANGES,flush=True)
