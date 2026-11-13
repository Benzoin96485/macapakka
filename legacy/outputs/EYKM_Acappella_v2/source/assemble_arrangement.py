"""Assemble the full-form seven-part version from an edited transcription.
The transcription and harmony plan are explicit editable data, not generated at playback.
"""
from pathlib import Path
import json,itertools,math
R=Path(__file__).resolve().parents[1]
P=['Lead','Soprano','Alto','Tenor','Bass','VP','Whistle']
def E(p,d,ly='',**kw):return dict(p=p,d=d,ly=ly,**kw)
def rest():return [E(None,3)]
def sustain(n,v='oo',breath=False):return [E(n,2.5,v),E(None,.5)] if breath else [E(n,3,v)]
chords={}
pcs={'C':0,'C#':1,'D':2,'Eb':3,'E':4,'F':5,'F#':6,'G':7,'G#':8,'Ab':8,'A':9,'Bb':10,'B':11,'Db':1}
for r,pc in pcs.items():
 for suf,kind,ints in [('', 'major',[0,4,7]),('m','minor',[0,3,7]),('7','dominant',[0,4,7,10]),('m7','minor-seventh',[0,3,7,10]),('sus4','suspended-fourth',[0,5,7])]:chords[r+suf]=[pc,kind,[(pc+x)%12 for x in ints]]
plan=[
 ('I','Piano prologue','Cm',['Cm','Gm','Ab','Eb','Fm','Bb7','Fm','G','G'],'intro','pp','Rubato; interlocking piano figure'),
 ('A','Everytime you kissed me','Cm',['Cm','Gm','Ab','Eb','Cm','Gm','Ab','Eb','Cm','Gm','Ab','Eb','Fm','Gm','C','C7'],'verse','p','Intimate; let the text lead'),
 ('B','Roses die','Fm',['Fm','Cm','Db','Ab']*3+['Bbm','C7','F','F','F','F'],'refrain','mp','Broaden the string line; keep the pulse light'),
 ('C','Instrumental answer','Fm',['Fm','Cm','Db','Ab']*3+['Bbm','C7','F','F'],'interlude','mf','Whistle leads; SATB carry the piano motion'),
 ('D','Silver dishes','Dm',['Dm','Am','Bb','F']*3+['Gm','A7','D','D7'],'verse2','mp','Flowing; retain the pickup'),
 ('E','Joys of the daylight','Gm',['Gm','Dm','Eb','Bb','Cm','F7','Bb','D7','Gm','Dm','Eb','Bb','A7','A7','D','D','C7','D7','G','G','G','G'],'bridge','mf','Build through the long vocal sentence'),
 ('F','Vocalise I','Gm',['Gm','Gm','Dm','Dm','Eb','F','Bb','D7','Gm','Gm','Dm','Dm','Cm','F','Bb','D7'],'vocalise','f','Layered ah; soaring line above the ostinato'),
 ('G','Vocalise II','Em',['Em','Em','Bm','Bm','Am','D7','G','B7','Em','Em','Bm','Bm','Cm','F','Eb','D7','Gm','Gm','D7','D7'],'development','f','Keep the harmonic sequence and the inner counterline'),
 ('H','Piano return','Gm',['G','G','G','G','Gm','Dm','Eb','Bb','Gm','Dm','Cm','D7'],'return','p','Withdraw to the piano texture; no percussion'),
 ('J','Everytime - raised reprise','C#m',['C#m','G#m','A','E']*3+['F#m','G#m','C#','C#7'],'reprise','mp','A semitone above the opening; do not transpose back'),
 ('K','Underneath the stars','F#m',['F#m','C#m','D','A','Bm','E7','A','C#7','F#m','C#m','D','A','G#7','G#7','C#','C#','Bm','Bm','C#m','C#m','F#sus4','F#','Bm','Bm'],'finale','mf','One continuous arc; release into the coda'),
 ('L','Piano epilogue','F#m',['Bm','Bm','D','C#m','C#m','C#m','Bm','C#7','F#','F#','F#'],'coda','p','Rubato; final major third, then a shared release'),
]
tr=json.loads((R/'source/transcription.json').read_text())
meta=[];score={p:[] for p in P};prev=[72,65,57,48]
def choosevoicing(ch,prev):
 root,kind,tones=chords[ch]
 bass=min([n for n in range(40,53) if n%12==root],key=lambda n:abs(n-prev[3])*.35+abs(n-46)*.1)
 cand=[]
 for s,a,t in itertools.product([n for n in range(65,78) if n%12 in tones],[n for n in range(57,71) if n%12 in tones],[n for n in range(48,65) if n%12 in tones]):
  if not(s>=a+2>=t+5 and t>=bass+3 and s-a<=12 and a-t<=12):continue
  cover=len({s%12,a%12,t%12,bass%12}.intersection(tones))
  cost=sum(abs(n-old)**1.3*w for n,old,w in zip([s,a,t],prev,[1,1.1,1.1]))+max(0,len(tones)-cover)*8
  cost+=abs(s-70)*.9+abs(a-63)*.6+abs(t-56)*.4+max(0,s-74)*3
  cand.append((cost,[s,a,t,bass]))
 return min(cand)[1]
def nearest(pcset,low,high,target):
 ns=[n for n in range(low,high+1) if n%12 in pcset]
 return min(ns,key=lambda n:abs(n-target))
def accomp(ch,style,j,vo):
 s,a,t,b=vo;tones=chords[ch][2]
 tl=nearest(tones,48,min(63,a-3),t-4);th=nearest(tones,48,min(64,a-2),t+2)
 al=nearest(tones,max(57,th+2),min(72,s-2),a-2)
 fs=[n for n in range(40,min(55,th)+1) if n%12==(b+7)%12];fifth=min(fs,key=lambda n:abs(n-b-5)) if fs else b
 v={p:rest() for p in P}
 # The piano's six-eighth-note flow is shared by two singers; every phrase
 # has alternating breath slots while the composite figure continues.
 v['Tenor']=[E(tl,.5,'dn'),E(th,.5,'du'),E(None,1),E(th,.5,'du'),E(None,.5)]
 v['Alto']=[E(None,1),E(al,.5,'li'),E(a,.5,'lu'),E(None,.5),E(a,.5,'li')]
 v['Soprano']=sustain(s,'oo',j%4==3)
 v['Bass']=[E(b,1.5,'dm'),E(None,.5),E(fifth,.75,'dn'),E(None,.25)]
 if style in ['intro','return','coda']:
  v['Bass']=sustain(b,'mm',j%3==2 or j==7)
  v['Soprano']=rest() if (style=='intro' and j<4) or (style=='return' and j<4) else sustain(s,'mm',j%4==3 or j%3==2)
 elif style in ['refrain','interlude','verse2','reprise']:
  if j%4==2:
   v['Alto']=[E(al,1.5,'oo'),E(a,.5,'ya'),E(al,.5,'lu'),E(None,.5)]
  if j%4==3:
   v['Tenor']=[E(t,1.5,'dm'),E(th,.5,'du'),E(tl,.5,'dn'),E(None,.5)]
 elif style in ['bridge','vocalise','development','finale']:
  v['Soprano']=[E(s,1.5,'ah'),E(s,.5,''),E(nearest(tones,max(65,a+2),79,s+2),.5,'ya'),E(None,.5)]
  v['Alto']=[E(a,1,'ah'),E(al,.5,'du'),E(a,.5,'li'),E(al,.5,'lu'),E(None,.5)]
  v['Tenor']=[E(t,1,'dm'),E(th,.5,'du'),E(tl,.5,'dn'),E(th,.5,'du'),E(None,.5)]
  v['Bass']=[E(b,1,'dm'),E(fifth,.5,'dn'),E(b,.5,'dm'),E(fifth,.5,'dn'),E(None,.5)]
 if style=='verse' and j<8:v['Soprano']=rest() if j<4 else sustain(s,'mm',j%4==3 or j%3==2)
 if style in ['intro','return','coda'] or style=='verse':v['VP']=rest()
 else:
  pattern=[(36,.5,'B'),(42,.5,'t'),(42,.5,'t'),(38,.5,'pf'),(42,.5,'ts'),(42,.5,'t')]
  if style in ['vocalise','development','finale'] and j%4==3:
   pattern=[(36,.5,'B'),(42,.5,'t'),(38,.5,'pf'),(42,.5,'t'),(38,.25,'pf'),(42,.25,'t'),(None,.5,'')]
  elif j%4==3:pattern[-1]=(None,.5,'')
  v['VP']=[E(*e) for e in pattern]
 if style=='intro' and j==7:
  v['Soprano']=sustain(71,'mm',True);v['Alto']=sustain(67,'mm');v['Tenor']=sustain(62,'mm');v['Bass']=sustain(43,'mm',True)
 if style=='intro' and j==8:
  v['Soprano']=[E(67,1,'du'),E(71,1,'du'),E(74,1,'du')];v['Alto']=sustain(62,'mm');v['Tenor']=sustain(55,'mm');v['Bass']=sustain(43,'mm')
 if style=='coda' and j>=8:
  for p,n in [('Soprano',73),('Alto',70),('Tenor',58),('Bass',42)]:v[p]=sustain(n,'mm')
  if j==9:
   v['Soprano']=[E(73,2,'mm'),E(None,.5),E(73,.5,'mm')]
   v['Alto']=[E(70,1.5,'mm'),E(None,.5),E(70,1,'mm')]
   v['Tenor']=[E(58,2.5,'mm'),E(None,.5)]
   v['Bass']=[E(42,2,'mm'),E(None,.5),E(42,.5,'mm')]
 return v

index=0
for sec,label,key,chs,style,dyn,direction in plan:
 for j,ch in enumerate(chs):
  vo=choosevoicing(ch,prev);prev=vo
  v=accomp(ch,style,j,vo)
  item=tr['bars'][index]
  # Edited source lines take precedence over accompaniment presets.
  for part in P:
   if part in item:v[part]=item[part]
  source_time=item['source_time'];source_end=item['source_end']
  bpm=round(180/(source_end-source_time),5)
  actual_key=key
  if sec=='G' and j>=12:actual_key='Gm'
  mood=dyn
  if sec=='E' and j>=16:mood='f'
  if sec=='H' and j<4:mood='pp'
  if sec=='K' and j>=16:mood='mp' if j<20 else 'p'
  if sec=='L' and j>=8:mood='pp'
  meta.append(dict(bar=index+1,section=sec,label=label,local=j+1,key=actual_key,tempo=bpm,chord=ch,style=style,dynamic=mood,direction=direction,source_time=source_time,source_end=source_end))
  for part in P:score[part].append(v[part])
  index+=1
assert index==196,(index,len(tr['bars']))
# A final Picardy third is deliberate: retain the original bright resolution.
score['Lead'][-1]=rest();score['Whistle'][-1]=rest();score['VP'][-1]=rest()
for p,n in [('Soprano',73),('Alto',70),('Tenor',58),('Bass',42)]:score[p][-1]=sustain(n,'mm')
ranges={p:[min(e['p'] for bar in score[p] for e in bar if e['p'] is not None),max(e['p'] for bar in score[p] for e in bar if e['p'] is not None)] for p in P if p!='VP'}
for p in P:
 for i,bar in enumerate(score[p]):
  assert abs(sum(e['d'] for e in bar)-3)<1e-8,(p,i+1,bar)
  assert all(e['d']>0 and abs(e['d']*4-round(e['d']*4))<1e-8 for e in bar)
data=dict(title='everytime you kissed me',version='2.0 - full-form rehearsal arrangement',parts=P,metadata=meta,score=score,ranges=ranges,chords=chords,reference='User-supplied EYKM.flac; analysis-only local stems; no original recording in this package',source_sha256='cd778800ffa27af355596d968563eba26520a95cd367935b2f0952778505b2db')
(R/'source/arrangement.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
print('Assembled',index,'bars',ranges)
