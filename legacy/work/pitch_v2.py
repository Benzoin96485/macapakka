from pathlib import Path
import numpy as np
from scipy import signal,ndimage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json,sys
root=Path('work/v2_stems_test' if '--test' in sys.argv else 'work/v2_stems')
out=Path('work/v2_analysis');out.mkdir(exist_ok=True)
sr=22050;hop=220;nfft=4096
names=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
for stem in ['vocals','bass','other']:
 y=np.fromfile(root/(stem+'.f32'),np.float32).reshape(-1,2).mean(axis=1)[::2]
 f,t,z=signal.stft(y,sr,nperseg=nfft,noverlap=nfft-hop)
 a=np.abs(z).astype(np.float32);del z
 notes=np.arange(33 if stem=='bass' else 53,73 if stem=='bass' else 90,.25)
 wh=a/(ndimage.maximum_filter1d(a,size=31,axis=0)+.00005)**.35
 sal=np.zeros((len(notes),len(t)),np.float32)
 for h in range(1,7):
  fq=440*2**((notes-69)/12)*h;ix=fq/(sr/nfft)
  for j,q in enumerate(ix):
   lo=int(q);w=q-lo
   if lo+1<len(f):sal[j]+=(wh[lo]*(1-w)+wh[lo+1]*w)/(h**.85)
 # suppress candidates whose energy is explained by their octave above
 sal[:-48]-=.4*sal[48:]
 sal=np.maximum(sal,0)
 np.savez_compressed(out/(stem+('_test' if '--test' in sys.argv else '')+'.npz'),t=t,notes=notes,sal=sal,rms=np.sqrt((a*a).sum(axis=0)))
 if stem=='vocals':
  # YIN difference normalized by running mean; first local minimum below .2.
  win=2048;minlag=int(sr/850);maxlag=int(sr/125)
  frames=np.lib.stride_tricks.sliding_window_view(np.pad(y,(win//2,win//2)),win)[::hop]
  f0=[];quality=[]
  for fr in frames:
   ac=signal.fftconvolve(fr,fr[::-1],mode='full')[win-1:win+maxlag]
   cs=np.r_[0,np.cumsum(fr*fr)];lags=np.arange(maxlag+1)
   dif=cs[win-lags]+cs[win]-cs[lags]-2*ac
   dn=dif[1:]/(np.cumsum(dif[1:])/np.arange(1,maxlag+1)+1e-12)
   peaks,_=signal.find_peaks(-dn[minlag-1:]);peaks+=minlag-1
   good=peaks[dn[peaks]<.25]
   q=good[0] if len(good) else (peaks[np.argmin(dn[peaks])] if len(peaks) else minlag)
   if 0<q<len(dn)-1:
    shift=.5*(dn[q-1]-dn[q+1])/(dn[q-1]-2*dn[q]+dn[q+1]+1e-12)
   else:shift=0
   f0.append(69+12*np.log2(sr/(q+1+shift)/440));quality.append(1-dn[q])
  np.savez_compressed(out/('yin_test.npz' if '--test' in sys.argv else 'yin.npz'),t=np.arange(len(f0))*hop/sr,f0=f0,quality=quality)
 for start in np.arange(0,len(y)/sr,24):
  m=(t>=start)&(t<start+24);s=sal[:,m];s=s/(s.max(axis=0,keepdims=True)+1e-8)
  fig,ax=plt.subplots(figsize=(20,6))
  ax.imshow(s,origin='lower',aspect='auto',extent=[t[m][0],t[m][-1],notes[0],notes[-1]],cmap='magma',vmin=.15,vmax=1)
  if stem=='vocals':
   tx=np.arange(len(f0))*hop/sr;ff=np.array(f0);qq=np.array(quality);mm=(tx>=start)&(tx<start+24)&(qq>.7)
   ax.plot(tx[mm],ff[mm],'.',color='cyan',markersize=1.5,alpha=.8)
  ax.set_yticks(np.arange(int(notes[0]),int(notes[-1]+1)));ax.set_yticklabels([names[n%12]+str(n//12-1) for n in range(int(notes[0]),int(notes[-1]+1))],fontsize=7)
  ax.set_xticks(np.arange(start,start+24,1));ax.grid(alpha=.2);ax.set_title(stem+' '+str(start))
  fig.tight_layout();fig.savefig(out/(stem+('_test' if '--test' in sys.argv else '')+f'_{start:03.0f}.png'),dpi=110);plt.close(fig)
 print(stem,'done',flush=True)
