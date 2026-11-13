"""Local SF2/SF3 sample player extracted from this project's v3 renderer.
Recorded samples only; this is NOT MuseScore's engine. Soundfonts are not bundled.
Supports zones, tuning, loops, envelopes and pan, but not every SF modulator.
"""
import io
import math
import struct
import hashlib
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt
SR = 44100

def chunks(data,start,end):
    while start+8<=end:
        tag=data[start:start+4].decode();n=struct.unpack_from('<I',data,start+4)[0];p=start+8
        if tag=='LIST':yield from chunks(data,p+4,p+n)
        else:yield tag,data[p:p+n]
        start=p+n+(n%2)
def records(data,fmt):
    n=struct.calcsize(fmt)
    return [struct.unpack_from(fmt,data,i) for i in range(0,len(data),n)]

class SampleBank:
    def __init__(self,path):
        data=path.read_bytes();self.hash=hashlib.sha256(data).hexdigest()
        d=dict(chunks(data,12,len(data)));self.raw=d['smpl']
        self.ph=records(d['phdr'],'<20sHHHIII');self.pb=records(d['pbag'],'<HH');self.pg=records(d['pgen'],'<HH')
        self.inst=records(d['inst'],'<20sH');self.ib=records(d['ibag'],'<HH');self.ig=records(d['igen'],'<HH')
        self.sh=records(d['shdr'],'<20sIIIIIBbHH');self.cache={};self.zcache={};self.used={}
    def zones(self,bags,gens,start,end,link):
        global_gen={};out=[]
        for b in range(start,end):
            g=dict(gens[bags[b][0]:bags[b+1][0]])
            if link not in g:global_gen.update(g)
            else:out.append(global_gen|g)
        return out
    def preset(self,bank,program):
        key=(bank,program)
        if key in self.zcache:return self.zcache[key]
        ix=next(i for i,p in enumerate(self.ph[:-1]) if p[1:3]==(program,bank))
        ps=self.zones(self.pb,self.pg,self.ph[ix][3],self.ph[ix+1][3],41)
        out=[]
        for p in ps:
            inst=p[41]
            for q in self.zones(self.ib,self.ig,self.inst[inst][1],self.inst[inst+1][1],53):
                out.append((p,q))
        self.zcache[key]=out
        return out
    def load(self,sid):
        if sid in self.cache:return self.cache[sid]
        sh=self.sh[sid];name,start,end,ls,le,rate,root,correction,link,typ=sh
        if typ&16:y,fs=sf.read(io.BytesIO(self.raw[start:end]),dtype='float32')
        else:y=np.frombuffer(self.raw[start*2:end*2],dtype='<i2').astype(np.float32)/32768;fs=rate
        if y.ndim>1:y=y.mean(axis=1)
        self.cache[sid]=(y,fs,ls,le,root,correction,typ)
        self.used[sid]=dict(name=name.rstrip(b'\0').decode(errors='replace'),sample_rate=fs,frames=len(y))
        return self.cache[sid]
    @staticmethod
    def signed(v):return v if v<32768 else v-65536
    def tone(self,bank,program,key,vel,duration):
        result=np.zeros((int((duration+2.0)*SR)+1,2),np.float32)
        found=0
        for p,q in self.preset(bank,program):
            if any(not (g.get(43,0x7f00)&255)<=key<=(g.get(43,0x7f00)>>8) or
                   not (g.get(44,0x7f00)&255)<=vel<=(g.get(44,0x7f00)>>8) for g in (p,q)):continue
            found+=1
            def gen(n,default=0):return self.signed(q.get(n,default))+self.signed(p.get(n,0))
            y,fs,ls,le,root,corr,typ=self.load(q[53])
            root=q.get(58,root);tuning=(key-root)*gen(56,100)/100+gen(51)+gen(52)/100+corr/100
            rate=fs/SR*2**(tuning/12)
            release=min(1.8,max(.025,2**(gen(38,-12000%65536)/1200)))
            if bank==128:duration=min(duration,.16)
            n=int((duration+release)*SR);n=min(n,len(result));t=np.arange(n)/SR
            ix=np.arange(n)*rate
            startoff=gen(0)+gen(4)*32768;endoff=gen(1)+gen(12)*32768
            ix+=startoff;ls+=gen(2)+gen(45)*32768;le+=gen(3)+gen(50)*32768
            loop=q.get(54,0)&3
            if loop and le>ls+1:
                mask=ix>=le
                # Both loop modes sustain through the release envelope. This avoids
                # a discontinuity when an offline note-off falls between sample frames.
                ix[mask]=ls+(ix[mask]-ls)%(le-ls)
            sig=np.interp(ix,np.arange(len(y)),y,left=0,right=0).astype(np.float32)
            attack=max(.001,2**(gen(34,-12000%65536)/1200))
            hold=max(0,2**((gen(35,-12000%65536)+gen(39)*(60-key))/1200))
            decay=max(.001,2**((gen(36,-12000%65536)+gen(40)*(60-key))/1200))
            sustain=10**(-max(0,gen(37))/200)
            env=np.minimum(1,t/attack)
            dec=t>attack+hold
            env[dec]=np.maximum(sustain,np.exp(-np.log(1/max(sustain,1e-5))*np.minimum(1,(t[dec]-attack-hold)/decay)))
            rel=t>duration
            env[rel]*=np.maximum(0,1-(t[rel]-duration)/release)**2
            sig*=env*(vel/100)**1.5*10**(-max(0,gen(48))/200)
            cutoff=8.176*2**(gen(8,13500)/1200)
            if cutoff<SR*.42 and cutoff>100:sig=sosfilt(butter(2,cutoff,fs=SR,output='sos'),sig).astype(np.float32)
            pan=np.clip(gen(17)/500,-1,1)
            result[:n,0]+=sig*math.sqrt((1-pan)/2)
            result[:n,1]+=sig*math.sqrt((1+pan)/2)
        if not found:raise ValueError(('No sample zone',bank,program,key,vel))
        return result
