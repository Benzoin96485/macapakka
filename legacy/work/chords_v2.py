import numpy as np
from scipy.ndimage import gaussian_filter1d
import json
t=np.load('work/times.npy');ch=np.load('work/chroma.npy');ba=np.load('work/bass_chroma.npy')
names=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
chords=[];profiles=[]
for r in range(12):
 for suffix,ints in [('',[0,4,7]),('m',[0,3,7]),('7',[0,4,7,10])]:
  a=np.full(12,-.15);a[(np.array(ints)+r)%12]=1/len(ints)
  chords.append(names[r]+suffix);profiles.append(a)
profiles=np.array(profiles)
start=18.94;beat=60/126
out=[]
for bar in range(-13,197):
 st=start+bar*3*beat;en=st+3*beat;m=(t>=max(0,st)+.1)&(t<en-.1)
 if not np.any(m):continue
 c=ch[:,m].mean(axis=1);c/=np.linalg.norm(c)+1e-9
 b=ba[:,m].mean(axis=1);b/=b.max()+1e-9
 s=profiles@c+.1*np.repeat(b,3)
 ix=np.argsort(s)[-4:][::-1]
 out.append({'bar_rel':bar,'time':round(st,3),'chords':[(chords[i],round(float(s[i]),3)) for i in ix]})
for r in out:print(r)
json.dump(out,open('work/v2_chord_candidates.json','w'),indent=2)
