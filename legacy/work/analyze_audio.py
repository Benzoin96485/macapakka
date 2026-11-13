from pathlib import Path
import numpy as np
from scipy import signal, ndimage
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=Path(__file__).parent
sr=22050
y=np.fromfile(p/'audio.f32',dtype=np.float32)
nfft=8192; hop=220
f,t,z=signal.stft(y,sr,nperseg=nfft,noverlap=nfft-hop,boundary='zeros')
a=np.abs(z).astype(np.float32)
np.save(p/'times.npy',t)
# spectral whitening retains transients and vibrato against stationary backing
base=ndimage.median_filter(a,size=(1,101))
whiten=a/(ndimage.maximum_filter1d(a,size=71,axis=0)+.001)**.65
notes=np.arange(45,90,.25)
sal=np.zeros((len(notes),len(t)),np.float32)
for hi,h in enumerate(range(1,7)):
 freqs=440*2**((notes-69)/12)*h
 ix=freqs/(sr/nfft)
 for j,x in enumerate(ix):
  lo=int(x); frac=x-lo
  if lo+1<len(f): sal[j]+=(whiten[lo]*(1-frac)+whiten[lo+1]*frac)/h**.8
sal=ndimage.gaussian_filter1d(sal,1,axis=1)
np.save(p/'salience.npy',sal)
np.save(p/'notes.npy',notes)
# broad 12 pitch chroma and low-bass chroma
ch=np.zeros((12,len(t))); bass=np.zeros((12,len(t)))
for i,fr in enumerate(f):
 if fr<50 or fr>2200:continue
 midi=69+12*np.log2(fr/440); n=round(midi)
 w=max(0,1-abs(midi-n)*2)
 ch[n%12]+=a[i]*w/(fr/200)**.4
 if fr<260:bass[n%12]+=a[i]*w
np.save(p/'chroma.npy',ch);np.save(p/'bass_chroma.npy',bass)
# percussive flux and beat-period autocorrelation
flux=np.maximum(0,np.diff(np.log1p(a*100),axis=1)).sum(axis=0)
ac=signal.correlate(flux-flux.mean(),flux-flux.mean(),mode='full',method='fft')[len(flux)-1:]
lo=int(.42*sr/hop);hi=int(.55*sr/hop)
peaks,_=signal.find_peaks(ac[lo:hi]); print('TEMPO candidates',[(round(60/(i+lo)/(hop/sr),3),round(float(ac[i+lo]),2)) for i in peaks])
print('chroma',dict(zip(['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'],np.round(ch.mean(axis=1),3).tolist())))
# inspect half-minute windows with salience and chroma
for k,start in enumerate(range(0,300,30)):
 mask=(t>=start)&(t<start+30)
 fig,axs=plt.subplots(2,1,figsize=(18,7),gridspec_kw={'height_ratios':[3,1]},sharex=True)
 s=sal[:,mask];s=s/(s.max(axis=0,keepdims=True)+1e-9)
 axs[0].imshow(s,origin='lower',aspect='auto',extent=[t[mask][0],t[mask][-1],notes[0],notes[-1]],cmap='magma',vmin=.25,vmax=1)
 axs[0].set_yticks(np.arange(48,90));axs[0].set_yticklabels([['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'][n%12]+str(n//12-1) for n in range(48,90)],fontsize=7)
 axs[0].grid(axis='y',alpha=.15);axs[0].set_ylim(55,87)
 axs[1].imshow(ch[:,mask],origin='lower',aspect='auto',extent=[t[mask][0],t[mask][-1],-.5,11.5],cmap='viridis')
 axs[1].set_yticks(range(12));axs[1].set_yticklabels(['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'],fontsize=7)
 axs[1].set_xticks(np.arange(start,start+30,.5),minor=True);axs[1].set_xticks(np.arange(start,start+30,2))
 fig.tight_layout();fig.savefig(p/f'analysis_{k:02}.png',dpi=130);plt.close(fig)
np.save(p/'flux.npy',flux)
print('done',len(y)/sr)
