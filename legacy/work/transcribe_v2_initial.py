from pathlib import Path
import numpy as np,json
from scipy.ndimage import median_filter,gaussian_filter1d
from scipy.signal import find_peaks
R=Path('outputs/EYKM_Acappella_v2/source');W=Path('work/v2_analysis')
def E(p,d,ly='',**k):return dict(p=None if p is None else int(p),d=float(d),ly=ly,**k)
def rest():return [E(None,3)]
# Nine-bar freely paced introduction, metrical body, eleven-bar rubato coda.
starts=[.18,2.16,3.86,5.44,7.21,8.87,10.79,12.85,17.51142857]
starts+=list(18.94+np.arange(177)*180/126)
# Starts now contain bars 1-186; the remaining coda attacks are editorially
# placed on the original piano's rubato attacks, with its final decay retained.
starts+= [271.80,273.23,274.66,276.10,277.56,279.05,280.62,282.24,285.05,289.50]
starts+=[296.40]
assert len(starts)==197,len(starts)
bars=[dict(source_time=float(starts[i]),source_end=float(starts[i+1]),Lead=rest(),Whistle=rest()) for i in range(196)]
yin=np.load(W/'yin.npz');yt=yin['t'];yf=yin['f0'];yq=yin['quality']
voc=np.load(W/'vocals.npz');vt=voc['t'];vr=voc['rms']
raw=np.fromfile('work/v2_stereo.f32',np.float32).reshape(-1,2).mean(axis=1)[::2]
def smooth_path(cost,pitches,transition=.55):
 trans=transition*(pitches[:,None]!=pitches[None,:])+.025*np.minimum(abs(pitches[:,None]-pitches[None,:]),12)
 dp=cost[0];back=[]
 for row in cost[1:]:
  v=dp[:,None]+trans;ix=v.argmin(axis=0);back.append(ix);dp=v[ix,np.arange(len(pitches))]+row
 out=[int(dp.argmin())]
 for b in back[::-1]:out.append(int(b[out[-1]]))
 return pitches[np.array(out[::-1])]
keys=[]
for n,key in [(9,0),(16,0),(18,5),(16,5),(16,2),(22,7),(16,7),(12,4),(8,7),(12,7),(16,1),(35,6)]:keys.extend([key]*n)
assert len(keys)==196
scales=[[x%12 for x in np.array([0,2,3,5,7,8,10,11])+k] for k in keys]
melody_intervals=[(18.86,64.42),(89.85,141.0),(144.45,196.1),(212.72,267.45)]
rows=[];tim=[];energy=[];conf=[]
for i in range(196):
 for k in range(12):
  st=starts[i]+(starts[i+1]-starts[i])*k/12;du=(starts[i+1]-starts[i])/12
  mid=st+min(.065,du*.45);mask=(yt>=mid)&(yt<st+du*.98)&(yq>.55)
  vals=yf[mask];med=float(np.median(vals)) if len(vals) else np.nan
  amp=float(np.interp(st+du*.55,vt,vr));rseg=raw[int(st*22050):int((st+du)*22050)];rms=np.sqrt(np.mean(rseg*rseg)+1e-10)
  q=float(np.mean(yq[(yt>=st)&(yt<st+du)]))
  active=any(a<=st+du*.5<=b for a,b in melody_intervals)
  # RMS from STFT is about sqrt(window energy scale) smaller than waveform RMS.
  voiced=active and amp>.0015 and q>.42 and (amp/(rms+1e-6)>.12)
  p=np.arange(57,80)
  if np.isnan(med):cost=np.ones(len(p))*2
  else:
   if med>79:med-=12
   if med<57:med+=12
   cost=np.minimum((p-med)**2,16)
  cost+=np.array([0 if x%12 in scales[i] else .8 for x in p])
  rows.append(cost);tim.append((i,k,st,du,voiced));energy.append(amp);conf.append(q)
path=smooth_path(np.array(rows),np.arange(57,80))
voiced=np.array([x[4] for x in tim]);voiced=median_filter(voiced.astype(float),size=3)>.5
for z,(i,k,st,du,act) in enumerate(tim):
 if not voiced[z]:path[z]=0
# The note states are reduced to attacks; vibrato and portamento are not
# misprinted as runs of chromatic sixteenth notes.
def cells_to_events(seq,unit=.25):
 out=[]
 for n in seq:
  p=int(n) if n else None
  if out and out[-1]['p']==p:out[-1]['d']+=unit
  else:out.append(E(p,unit))
 return out
for i in range(196):bars[i]['Lead']=cells_to_events(path[i*12:(i+1)*12])
# Tie genuine sustained sounds across barlines; underlay can later rearticulate.
for i in range(195):
 a=bars[i]['Lead'][-1];b=bars[i+1]['Lead'][0]
 if a['p'] is not None and a['p']==b['p']:
  a['tie_start']=True;b['tie_stop']=True
out=dict(bars=bars,method='YIN and spectral evidence on local separated vocals; editorial quantization and underlay',transcription_review='draft; requires singer-led checking against source')
(R/'transcription.json').write_text(json.dumps(out,indent=2))
np.savez_compressed(W/'lead_grid.npz',pitch=path,time=np.array([r[2] for r in tim]),energy=energy,confidence=conf)
names=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
for i,b in enumerate(bars):
 if any(e['p'] is not None for e in b['Lead']):
  print(f'{i+1:3} {b["source_time"]:7.2f}', ' '.join(('r' if e['p'] is None else names[e['p']%12]+str(e['p']//12-1))+':'+str(e['d']) for e in b['Lead']))
