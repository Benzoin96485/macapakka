from pathlib import Path
import json,numpy as np
R=Path('outputs/EYKM_Acappella_v2/source');D=json.loads((R/'transcription.json').read_text());B=D['bars']
V=np.load('work/v2_analysis/vocals.npz');vt=V['t'];vr=V['rms']
lyrics=[
 (10,13,'Ev- er- y time you kissed me I trem- bled like a child'),
 (14,17,'Ga- ther- ing the ro- ses we sang for the hope'),
 (18,21,'Your ve- ry voice is in my heart- beat sweet- er than my dream'),
 (22,25,'We were there in ev- er- last- ing bloom'),
 (26,29,'Ro- ses die the se- cret is in- side the pain'),
 (30,33,'Winds are high up- on the hill I can- not hear you'),
 (34,37,"Come and hold me close I'm shiv- er- ing cold in the heart of rain"),
 (38,41,"Dark- ness falls I'm call- ing for the dawn"),
 (59,63,'Sil- ver dish- es for the mem- o- ries for the days gone by'),
 (64,67,'Sing- ing for the prom- is- es to- mor- row may bring'),
 (68,71,'I har- bour all the old af- fec- tion ro- ses of the past'),
 (72,75,'Dark- ness falls and sum- mer will be gone'),
 (75,79,'Joys of the day- light sha- dows of the star- light'),
 (80,83,'Ev- ery- thing was sweet by your side my love'),
 (84,87,'Ru- by tears have come to me for your last words'),
 (88,89,"I'm here just sing- ing my song of woe"),
 (90,91,'Wait- ing for you my love'),
 (92,95,'Now let my hap- pi- ness sing in- side my dream'),
 (145,149,'Ev- er- y time you kissed me my heart was in such pain'),
 (150,153,'Ga- ther- ing the ro- ses we sang of the grief'),
 (154,157,'Your ve- ry voice is in my heart- beat sweet- er than des- pair'),
 (158,161,'We were there in ev- er- last- ing bloom'),
 (161,165,'Un- der- neath the stars sha- ded by the flow- ers'),
 (166,169,'Kiss me in the sum- mer day gloom my love'),
 (170,173,'You are all my plea- sure my hope and my song'),
 (174,177,'I will be here dream- ing in the past'),
 (178,181,'Un- til you come'),
 (182,185,'Un- til we close our eyes'),
]
def evlist(a,b,unassigned=True):
 arr=[]
 for i in range(a-1,b):
  pos=0
  for j,e in enumerate(B[i]['Lead']):
   if e['p'] is not None and (not unassigned or not e.get('ly')) and not e.get('tie_stop'):arr.append((i,j,pos,e))
   pos+=e['d']
 return arr
for a,b,words in lyrics:
 sy=words.split();evs=evlist(a,b)
 # Recover repeated syllable attacks which pitch-only tracking naturally merges.
 while len(evs)<len(sy):
  choices=[]
  for i,j,pos,e in evs:
   if e['d']<.75:continue
   for split in np.arange(.5,e['d']-.24,.25):
    tm=B[i]['source_time']+(pos+split)/3*(B[i]['source_end']-B[i]['source_time'])
    amp=float(np.interp(tm,vt,vr));around=float(np.interp(tm-.09,vt,vr)+np.interp(tm+.09,vt,vr))/2
    # Favor an energy dip and balanced singable note durations.
    benefit=(around-amp)/(around+1e-8)+.12*min(split,e['d']-split)
    choices.append((benefit,i,j,float(split)))
  if not choices:break
  _,i,j,sp=max(choices);e=B[i]['Lead'][j]
  x=dict(e,d=sp);x.pop('tie_start',None);y=dict(e,d=e['d']-sp,ly='');y.pop('tie_stop',None)
  B[i]['Lead'][j:j+1]=[x,y];evs=evlist(a,b)
 if len(evs)<len(sy):
  print('UNDERLAY SHORT',a,b,len(evs),len(sy));continue
 # Extra attacks are melismas. Dynamic programming distributes syllables in
 # order and favors longer notes for word endings, retaining every pitch.
 n=len(evs);k=len(sy);dur=np.array([e[3]['d'] for e in evs]);positions=np.array([e[0]*3+e[2] for e in evs]);span=positions[-1]-positions[0]+1e-6
 weights=np.array([.7 if s.endswith('-') or s.lower() in ['the','a','of','in','for','and','my','to'] else 1.0 for s in sy]);weights[-1]=1.5
 target=np.r_[0,np.cumsum(weights)[:-1]]/(weights.sum()-weights[-1]+1e-6)
 if n==k:indices=list(range(n))
 else:
  cost=((positions[None,:]-positions[0])/span-target[:,None])**2*8
  cost-=np.minimum(dur[None,:],1.5)*.1
  dp=np.full((k,n),1e9);prev=np.zeros((k,n),int);dp[0,0]=0
  for z in range(1,k):
   for j in range(z,n-k+z+1):
    ix=np.argmin(dp[z-1,:j]);dp[z,j]=dp[z-1,ix]+cost[z,j];prev[z,j]=ix
  indices=[int(np.argmin(dp[-1]))]
  for z in range(k-1,0,-1):indices.append(int(prev[z,indices[-1]]))
  indices=indices[::-1]
 for ix,syl in zip(indices,sy):evs[ix][3]['ly']=syl
 print(a,b,len(evs),len(sy),words)
# Choral episodes use vowels rather than invented phonetic transcription.
for i in range(97,133):
 for e in B[i]['Lead']:
  if e['p'] is not None and not e.get('tie_stop'):e['ly']='ah'
D['lyric_phrases']=[dict(first_bar=a,last_bar=b,text=w) for a,b,w in lyrics]
(R/'transcription.json').write_text(json.dumps(D,indent=2))
