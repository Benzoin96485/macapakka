import numpy as np
from scipy.ndimage import maximum_filter1d,median_filter
import json
p='work/';t=np.load(p+'times.npy');s=np.load(p+'center_salience.npy');ns=np.load(p+'center_notes.npy')
q=60/126
names=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
sections=[('A',18.94,16,57,65,[0,2,3,5,7,8,10,11]),('B',41.80,16,60,73,[0,1,3,5,7,8,10,4]),('C',89.95,16,59,67,[0,1,2,4,5,7,9,10]),('D',112.81,20,60,74,[0,2,3,5,6,7,9,10]),('A2',212.90,16,58,68,[1,3,4,6,8,9,11,0]),('E',235.76,20,59,74,[1,2,4,6,8,9,11,5])]
out={}
for name,start,bars,low,high,scale in sections:
 pitches=np.arange(low,high+1);raw=[]
 for i in range(bars*6):
  mask=(t>=start+i*q/2+.045)&(t<start+(i+.92)*q/2)
  rr=[]
  for n in pitches:
   m=abs(ns-n)<=.5
   rr.append(np.mean(s[m][:,mask].max(axis=0)))
  raw.append(rr)
 raw=np.asarray(raw)
 # reward salience, mild pitch continuity, constrain key; no assumed exact sung octave
 score=np.log(raw+1e-5);score-=np.max(score,axis=1,keepdims=True)
 score-=np.array([0 if n%12 in scale else .6 for n in pitches])[None,:]
 trans=-.045*np.abs(pitches[:,None]-pitches[None,:])-.10*(pitches[:,None]!=pitches[None,:])
 dp=score[0];back=[]
 for r in score[1:]:
  mat=dp[:,None]+trans;ix=mat.argmax(axis=0);back.append(ix);dp=mat[ix,np.arange(len(pitches))]+r
 seq=[int(dp.argmax())]
 for b in back[::-1]:seq.append(int(b[seq[-1]]))
 seq=pitches[np.array(seq[::-1])].tolist()
 out[name]={'start':start,'bars':bars,'eighth_notes':seq}
 print('\n'+name,start)
 for i in range(bars):print(f'{i+1:2}', ' '.join(names[n%12]+str(n//12-1) for n in seq[i*6:(i+1)*6]))
json.dump(out,open(p+'quantized.json','w'),indent=2)
