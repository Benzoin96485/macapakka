"""Per-bar harmony report: bass line (bass stem or piano LH) + pitch-class weights per beat from piano/guitar/other notes."""
import numpy as np, os, sys
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P=60/126; T0=0.43; S16=P/4
FL=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
notes={n:np.load(f'{R}/bp/{n}.npy') for n in ['piano','guitar','other','bass']}
QUAL={'':[0,4,7],'m':[0,3,7],'7':[0,4,7,10],'m7':[0,3,7,10],'maj7':[0,4,7,11],'sus4':[0,5,7],'sus2':[0,2,7],
      'add9':[0,2,4,7],'madd9':[0,2,3,7],'6':[0,4,7,9],'m6':[0,3,7,9],'dim':[0,3,6],'aug':[0,4,8],'7sus4':[0,5,7,10],'m7b5':[0,3,6,10]}
def pcw(a,z,stems=('piano','guitar','other'),pmin=48,pmax=90):
    w=np.zeros(12)
    for n in stems:
        x=notes[n]; s,e,p,amp=x[:,0],x[:,1],x[:,2],x[:,3]
        ov=np.clip(np.minimum(e,z)-np.maximum(s,a),0,None)
        sel=(ov>0)&(p>=pmin)&(p<=pmax)
        for o,pp,am in zip(ov[sel],p[sel],amp[sel]): w[int(pp)%12]+=o*am
    return w
def bassline(a,z):
    x=notes['bass']; sel=(x[:,0]>=a-0.05)&(x[:,0]<z-0.05)&(x[:,3]>0.25)&(x[:,2]<57)
    out=[(int(round((s-a)/S16)),int(p)) for s,e,p,amp in x[sel]]
    if not out:  # fall back to piano left hand
        x=notes['piano']; sel=(x[:,0]>=a-0.05)&(x[:,0]<z-0.05)&(x[:,3]>0.25)&(x[:,2]<53)
        out=[(int(round((s-a)/S16)),int(p)) for s,e,p,amp in x[sel]]
    # dedupe octave doubles at same slot
    d={}
    for sl,p in out: d[sl]=min(p,d.get(sl,999))
    return sorted(d.items())
def best(w,bass_pc=None):
    if w.sum()<1e-6: return '-',0
    wn=w/np.linalg.norm(w); res=[]
    for r in range(12):
        for q,iv in QUAL.items():
            tv=np.zeros(12); tv[[(r+i)%12 for i in iv]]=1; tv/=np.linalg.norm(tv)
            sc=wn@tv - (0.03 if len(iv)>3 else 0) + (0.06 if bass_pc==r else 0)
            res.append((sc,FL[r]+q))
    res.sort(reverse=True); return res[0][1],res[0][0]
lo,hi=int(sys.argv[1]),int(sys.argv[2])
for b in range(lo,hi):
    a=T0+b*12*S16
    bl=bassline(a,a+12*S16)
    halves=[]
    for h0,h1 in ((0,6),(6,12)):
        w=pcw(a+h0*S16,a+h1*S16)
        bpc=None
        for sl,p in bl:
            if h0<=sl<h1: bpc=p%12; break
        ch,sc=best(w,bpc)
        top=' '.join(FL[i] for i in np.argsort(w)[::-1][:4] if w[i]>0.15*w.max())
        halves.append(f'{ch:7s}[{top:14s}]')
    bs=' '.join(f'{sl}:{FL[p%12]}{p//12-1}' for sl,p in bl)
    print(f'{b:3d} bass: {bs:34s} | '+' | '.join(halves))
