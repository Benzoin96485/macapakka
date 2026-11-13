"""Offline playback from the locally installed MS Basic SF3 recorded samples.

This is a small sample player, NOT MuseScore's audio engine. It implements the zones,
key/velocity layers, tuning, volume envelope, loop, attenuation and pan used here.
MuseScore-specific effects/modulators are not replicated. No oscillator/voice synthesis.
The soundfont is read locally and is not redistributed with this project.
"""
from pathlib import Path
import io, json, struct, math, subprocess, hashlib
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt
import mido

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parents[1]
DATA=json.loads((ROOT/'source/arrangement.json').read_text())
SF=Path('/Applications/MuseScore 4.app/Contents/Resources/sound/MS Basic.sf3')
SR=44100

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

STARTS=np.array([m['source_time'] for m in DATA['metadata']]+[DATA['metadata'][-1]['source_end']])
STARTS-=STARTS[0]
def btime(beat):
    i=min(len(STARTS)-2,int(beat//3));return STARTS[i]+(beat-i*3)/3*(STARTS[i+1]-STARTS[i])
def events(part):
    result=[]
    for bi,bar in enumerate(DATA['score'][part]):
        pos=bi*3
        for e in bar:
            if e['p'] is not None:
                if e.get('tie_stop') and result and result[-1]['p']==e['p'] and abs(result[-1]['end']-pos)<1e-8:
                    result[-1]['end']=pos+e['d']
                else:result.append(dict(e,start=pos,end=pos+e['d'],bar=bi))
            pos+=e['d']
    return result
def midi(path,selected):
    f=mido.MidiFile(ticks_per_beat=480);mt=mido.MidiTrack();f.tracks.append(mt);prev=0
    for i,m in enumerate(DATA['metadata']):
        tick=i*1440;mt.append(mido.MetaMessage('set_tempo',tempo=round(60e6/m['tempo']),time=tick-prev));prev=tick
    mt.append(mido.MetaMessage('end_of_track',time=1440))
    for part in selected:
        tr=mido.MidiTrack();f.tracks.append(tr);channel=9 if part=='VP' else DATA['parts'].index(part)
        tr.append(mido.MetaMessage('track_name',name=part));tr.append(mido.Message('program_change',channel=channel,program=73 if part=='Whistle' else 0))
        track=[]
        for e in events(part):
            v=int(np.clip(e.get('velocity',72 if part=='Lead' else 62),1,127))
            track += [(round(e['start']*480),1,mido.Message('note_on',channel=channel,note=e['p'],velocity=v)),
                      (round(e['end']*480),0,mido.Message('note_off',channel=channel,note=e['p'],velocity=0))]
        prev=0
        for tick,order,msg in sorted(track,key=lambda x:x[:2]):msg.time=tick-prev;tr.append(msg);prev=tick
        tr.append(mido.MetaMessage('end_of_track',time=len(DATA['metadata'])*1440-prev))
    f.save(path)

def main():
    bank=SampleBank(SF);outdir=PROJECT/'work/v3/rendered_stems';outdir.mkdir(exist_ok=True)
    length=int((STARTS[-1]+2.5)*SR);stems={}
    for part in DATA['parts']:
        y=np.zeros((length,2),np.float32)
        for e in events(part):
            start=btime(e['start']);duration=btime(e['end'])-start
            duration=max(.06,duration-(.035 if e['role'] in ('piano','piano_theme') else .012))
            vel=int(np.clip(e.get('velocity',76 if part=='Lead' else 68 if part=='Whistle' else 60),25,112))
            z=bank.tone(128 if part=='VP' else 0,73 if part=='Whistle' else 0,e['p'],vel,duration)
            ix=round(start*SR);n=min(len(z),len(y)-ix);y[ix:ix+n]+=z[:n]
        # Short room reflection of the sampled sound, fixed for reproducibility.
        for delay,gain in ((.037,.07),(.067,.045)):
            off=int(SR*delay);y[off:]+=y[:-off].copy()*gain
        y *= .32 if part=='VP' else .80 if part=='Whistle' else 12.0
        sf.write(outdir/f'{part}.wav',y,SR,subtype='FLOAT');stems[part]=y
        midi(ROOT/f'midi/EYKM_v3_{part}.mid',[part])
        print('sample rendered',part,'peak',float(abs(y).max()),flush=True)
    midi(ROOT/'midi/EYKM_v3_All_Parts.mid',DATA['parts'])
    gains={'Lead':1.,'Soprano':.75,'Alto':.7,'Tenor':.7,'Bass':.95,'VP':.6,'Whistle':.95}
    panning={'Lead':0,'Soprano':-.38,'Alto':-.16,'Tenor':.2,'Bass':0,'VP':.08,'Whistle':.38}
    def mix(name,focus=None,omit=()):
        y=np.zeros((length,2),np.float32)
        for p,z in stems.items():
            if p in omit:continue
            gain=gains[p]*(1.7 if focus==p else .30 if focus else 1.)
            pan=0 if focus==p else panning[p]
            zz=z.copy();zz[:,0]*=math.sqrt(1-pan);zz[:,1]*=math.sqrt(1+pan)
            y+=zz*gain
        peak=float(abs(y).max());scale=.91/max(peak,1e-8);y*=scale
        path=outdir/f'{name}.wav';sf.write(path,y,SR,subtype='PCM_24')
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(path),'-c:a','libmp3lame','-b:a','192k',str(ROOT/f'audio/{name}.mp3')],check=True)
        return dict(peak_before=peak,normalization=scale,peak_after=float(abs(y).max()))
    metrics={'full':mix('EYKM_v3_Full_Mix')}
    for p in DATA['parts']:metrics[p]=mix('EYKM_v3_Focus_'+p,focus=p)
    metrics['without_lead']=mix('EYKM_v3_Without_Lead',omit=('Lead',))
    # Direct stem exports reveal the actual VP and backing without masking.
    for p in ('VP','Alto','Tenor','Whistle'):
        metrics['solo_'+p]=mix('EYKM_v3_Solo_'+p,omit=tuple(x for x in DATA['parts'] if x!=p))
    report=dict(engine='local SF3 sample playback, not MuseScore engine',soundfont=str(SF),soundfont_sha256=bank.hash,
        presets={'voices':'bank 0 / program 0 Grand Piano','whistle':'bank 0 / program 73 Flute','VP':'bank 128 / program 0 Standard'},
        instrument_calibration={'piano':12.0,'flute':.8,'drums':.32},seconds=length/SR,count_in=0,sample_rate=SR,original_audio_mixed_in=False,samples=bank.used,metrics=metrics)
    (ROOT/'source/audio_render.json').write_text(json.dumps(report,indent=2))
    excerpts=ROOT/'audio/excerpts';excerpts.mkdir(exist_ok=True)
    for name,input_name,start,duration in [
        ('Piano_Texture','EYKM_v3_Without_Lead',0,42),
        ('Flute_Only_Whistle','EYKM_v3_Full_Mix',67.39,22.86),
        ('VP','EYKM_v3_Solo_VP',113.1,24)]:
        subprocess.run(['ffmpeg','-v','error','-y','-ss',str(start),'-i',str(ROOT/f'audio/{input_name}.mp3'),
                        '-t',str(duration),'-c:a','libmp3lame','-b:a','192k',str(excerpts/f'EYKM_v3_{name}_Example.mp3')],check=True)
    subprocess.run(['ffmpeg','-v','error','-y','-ss','144.53','-i',str(outdir/'Alto.wav'),
                    '-ss','144.53','-i',str(outdir/'Tenor.wav'),'-filter_complex',
                    '[0:a][1:a]amix=inputs=2:normalize=0,volume=3[a]','-map','[a]','-t','40',
                    '-c:a','libmp3lame','-b:a','192k',str(excerpts/'EYKM_v3_Backing_Vocals_Example.mp3')],check=True)
    print('Finished sampled audio and MIDI',length/SR,flush=True)

if __name__=='__main__':main()
