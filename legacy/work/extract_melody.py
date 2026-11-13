from pathlib import Path
import numpy as np
from scipy import signal,ndimage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).parent;sr=22050;nfft=8192;hop=220
mid=np.fromfile(p/'audio.f32',np.float32);side=np.fromfile(p/'side.f32',np.float32)
f,t,z=signal.stft(mid,sr,nperseg=nfft,noverlap=nfft-hop)
a=np.abs(z).astype(np.float32);del z
_,_,z=signal.stft(side,sr,nperseg=nfft,noverlap=nfft-hop)
b=np.abs(z).astype(np.float32);del z
# suppress sources panned away from center; retain harmonics with mid/side advantage
v=np.maximum(0,a-1.5*b);del b
v=v/(ndimage.maximum_filter1d(v,size=71,axis=0)+.0008)**.6
notes=np.arange(50,85,.25);s=np.zeros((len(notes),len(t)),np.float32)
for h in range(1,8):
 for j,n in enumerate(notes):
  x=440*2**((n-69)/12)*h/(sr/nfft);lo=int(x);w=x-lo
  s[j]+=(v[lo]*(1-w)+v[lo+1]*w)/h**.7
s=ndimage.gaussian_filter1d(s,1,axis=1)
np.save(p/'center_salience.npy',s);np.save(p/'center_notes.npy',notes)
for start in range(0,300,30):
 mask=(t>=start)&(t<start+30); ss=s[:,mask];ss/=ss.max(axis=0,keepdims=True)+1e-8
 fig,ax=plt.subplots(figsize=(18,6))
 ax.imshow(ss,origin='lower',aspect='auto',extent=[t[mask][0],t[mask][-1],notes[0],notes[-1]],cmap='magma',vmin=.3,vmax=1)
 ax.set_yticks(range(53,85));ax.set_yticklabels([['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'][n%12]+str(n//12-1) for n in range(53,85)],fontsize=8)
 ax.grid(axis='y',alpha=.2);ax.set_ylim(55,82);ax.set_xticks(np.arange(start,start+30,1));ax.grid(axis='x',alpha=.2)
 fig.tight_layout();fig.savefig(p/f'center_{start//30:02}.png',dpi=130);plt.close(fig)
print('done')
