"""Per-bar drum events on the 16th grid: K=kick S=snare H=hat C=crash-like burst."""
import numpy as np, os, sys, librosa
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sr=22050; hop=128; fr=sr/hop
d=np.load(f'{R}/data/st_drums.npy')
S=np.abs(librosa.stft(d,n_fft=1024,hop_length=hop)); f=librosa.fft_frequencies(sr=sr,n_fft=1024)
def flux(lo,hi):
    L=np.log1p(100*S[(f>=lo)&(f<hi)]); return np.concatenate([[0],np.maximum(0,np.diff(L,axis=1)).sum(axis=0)])
def env(lo,hi): return np.log1p(100*S[(f>=lo)&(f<hi)]).sum(axis=0)
K=flux(35,110); SN=flux(1500,4500); H=flux(7000,11000); CR=env(4000,11000)
for x in (K,SN,H): x/= np.percentile(x,99.5)
CR=(CR-np.percentile(CR,50))/(np.percentile(CR,99.5)-np.percentile(CR,50))
P=60/126; T0=0.43; S16=P/4
lo,hi=int(sys.argv[1]),int(sys.argv[2])
for b in range(lo,hi):
    row=[]
    for k in range(12):
        i=int((T0+(b*12+k)*S16)*fr); w=slice(max(0,i-3),i+4)
        c=''
        if K[w].max()>0.45: c+='K'
        if SN[w].max()>0.45: c+='S'
        if H[w].max()>0.40: c+='h'
        if k==0 and CR[i:i+int(0.4*fr)].mean()>0.75: c+='C'
        row.append(c or '.')
    print(f'{b:3d}| '+' '.join(f'{c:4s}' for c in row[:4])+'| '+' '.join(f'{c:4s}' for c in row[4:8])+'| '+' '.join(f'{c:4s}' for c in row[8:]))
