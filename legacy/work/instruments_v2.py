from pathlib import Path
import json,re,numpy as np
from scipy import signal,ndimage
P=Path('outputs/EYKM_Acappella_v2/source/transcription.json');D=json.loads(P.read_text());B=D['bars']
def nn(s):
 if s=='r':return None
 m=re.fullmatch(r'([A-G])([b#]?)(\d)',s);return (int(m[3])+1)*12+dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[m[1]]+{'':0,'#':1,'b':-1}[m[2]]
def line(s):
 out=[dict(p=nn(x.split(':')[0]),d=float(x.split(':')[1]),ly='') for x in s.split()]
 assert sum(e['d'] for e in out)==3,s
 return out
W={
1:'G5:.5 C6:.25 Eb6:.25 D6:.5 C6:.5 Eb6:.5 G5:.5',
2:'Bb5:2.5 r:.5',
3:'Ab5:.5 Bb5:.5 Ab5:1 C6:1',
4:'Bb5:1 G5:1.5 r:.5',
5:'F5:.5 Ab5:.5 G5:.5 F5:.5 Ab5:1',
6:'Bb5:1 Ab5:1 F5:.5 r:.5',
7:'Ab5:.5 G5:.5 C6:1 D6:1',
8:'G5:2 r:1',9:'r:3',
43:'r:2 Ab5:.5 Bb5:.5',
44:'Bb5:1 C6:1.5 r:.5',
45:'C6:.5 Eb6:.5 Bb5:1.5 r:.5',
46:'Ab5:.5 Bb5:.5 Db6:.5 C6:1 Ab5:.5',
47:'C6:1 C6:.5 Db6:.5 Bb5:.5 C6:.5',
48:'Ab5:1 C6:1.5 r:.5',
49:'G5:1 Eb6:1 Db6:.5 r:.5',
50:'Db6:.5 Eb6:.5 Db6:.5 C6:.5 Bb5:.5 Db6:.5',
51:'Db6:1 C6:1 Bb5:1',
52:'C6:1.5 Ab5:1 r:.5',
53:'Eb6:1.5 C6:1 G5:.5',
54:'Db6:.5 C6:.5 Bb5:.5 Ab5:.5 Bb5:.5 Db6:.5',
55:'Db6:1 C6:1 Bb5:1',
56:'Ab5:1 G5:1 F5:.5 r:.5',
57:'Bb5:1.5 Ab5:1 G5:.5',
58:'G5:.5 F5:2.5',59:'F5:2.5 r:.5',
# The piano return retains its dominant pedal and eight-bar recollection.
134:'G5:1 B5:1 D6:1',135:'C6:.5 D6:.5 C6:1 A5:1',
136:'A5:1 Bb5:.5 A5:.5 G5:.5 r:.5',137:'G5:2 r:1',
138:'Bb5:.5 A5:.5 Bb5:.5 F6:.5 D6:.5 Bb5:.5',
139:'A5:2.5 r:.5',140:'Bb5:.5 A5:.5 Bb5:1 Eb6:1',
141:'D6:2.5 r:.5',142:'G5:.5 Bb5:.5 A5:.5 G5:.5 Bb5:1',
143:'D6:1 C6:1 Bb5:.5 r:.5',144:'Bb5:.5 A5:.5 C6:1 Eb6:.5 D6:.5',
145:'D6:2 r:1',
# Finale piano line, after the lead's held F#4.
186:'r:3',187:'B4:1 D5:1 F#5:1',188:'F#5:1 D5:1 B4:.5 r:.5',
189:'D5:.5 F#5:.5 D5:1 C#5:1',190:'C#5:2.5 r:.5',
191:'C#5:1 E5:1 F#5:1',192:'B4:1 D5:1 F#5:1',
193:'E#5:1 G#5:1 B5:.5 r:.5',194:'A#5:1 G#5:1 F#5:1',195:'F#5:2 r:1',196:'r:3'
}
# One piano peak is placed an octave lower to keep the whistle at E6 or below.
for bar,s in W.items():
 ev=line(s)
 for e in ev:
  if e['p'] is not None and e['p']>88:e['p']-=12
 B[bar-1]['Whistle']=ev
# Restore consistent ties only where there is no new instrumental attack.
for i in [39,40,41,92,93,181,182,183,184]:
 a=B[i]['Lead'][-1];b=B[i+1]['Lead'][0]
 if a['p'] is not None and a['p']==b['p'] and not b['ly']:a['tie_start']=True;b['tie_stop']=True
for i in [57]:
 a=B[i]['Whistle'][-1];b=B[i+1]['Whistle'][0]
 if a['p'] is not None and a['p']==b['p']:a['tie_start']=True;b['tie_stop']=True
# VP rhythm follows separated drum onsets. Below the threshold it stays silent.
sr=22050;y=np.fromfile('work/v2_stems/drums.f32',np.float32).reshape(-1,2).mean(axis=1)[::2]
bands=[]
for lo,hi in [(35,190),(220,2500),(3500,9500)]:
 sos=signal.butter(3,[lo,hi],btype='bandpass',fs=sr,output='sos');z=signal.sosfilt(sos,y)
 frames=z[:len(z)//220*220].reshape(-1,220);env=np.sqrt(np.mean(frames*frames,axis=1));bands.append(env)
env=np.array(bands);tt=(np.arange(env.shape[1])+.5)*220/sr
flux=np.maximum(0,env-ndimage.minimum_filter1d(env,size=9,axis=1))
norm=np.percentile(flux,97,axis=1);nf=flux/(norm[:,None]+1e-8)
aud=[]
for i in range(196):
 st=B[i]['source_time'];du=(B[i]['source_end']-st)/6;hits=[]
 for j in range(6):
  m=(tt>=st+j*du-.035)&(tt<st+j*du+.13)
  v=nf[:,m].max(axis=1) if np.any(m) else np.zeros(3)
  # One mouth sound per slot: combined kit hits become their salient attack.
  if max(v)<.20:n=None;sy=''
  elif v[0]>.48 and v[0]>=v[1]*.7:n=36;sy='B'
  elif v[1]>.36 and v[1]>=v[2]*.7:n=38;sy='pf'
  else:n=42;sy='t'
  hits.append(dict(p=n,d=.5,ly=sy))
 # Keep the exposed piano sections free of source-separation leakage.
 if i<25 or 133<=i<145 or i>=181:hits=[dict(p=None,d=3.,ly='')]
 if i%4==3 and len(hits)==6:hits[-1]=dict(p=None,d=.5,ly='')
 # Merge adjacent rests; do not merge repeated percussion strokes.
 merged=[]
 for e in hits:
  if merged and e['p'] is None and merged[-1]['p'] is None:merged[-1]['d']+=e['d']
  else:merged.append(e)
 B[i]['VP']=merged;aud.append((i+1,' '.join(e['ly'] or '-' for e in hits)))
P.write_text(json.dumps(D,indent=2))
Path('work/v2_vp_patterns.txt').write_text('\n'.join(f'{i} {s}' for i,s in aud))
print('Instrumental lines:',len(W),'measures; VP attacks drawn from the drum stem')
