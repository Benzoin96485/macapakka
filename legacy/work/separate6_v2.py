from pathlib import Path
import sys, types, functools, json, struct, time
import numpy as np
import torch
sys.path.insert(0,str(Path(__file__).parent/'v2_deps'))
# Inference uses CaC, no resampling, and dense attention; these training/Wiener
# optional packages are not called by this cached HTDemucs model.
for name in ['openunmix','openunmix.filtering','julius','omegaconf','dora','dora.log']:
    sys.modules[name]=types.ModuleType(name)
def unavailable(*a,**k): raise RuntimeError('Unused optional inference path')
sys.modules['openunmix.filtering'].wiener=unavailable
sys.modules['omegaconf'].OmegaConf=None
sys.modules['dora.log'].fatal=unavailable
def rearrange(x,pattern,**kw):
    p=pattern.replace(' ','')
    if p=='bcft->bc(ft)': return x.flatten(2)
    if p=='bc(ft)->bcft': return x.reshape(x.shape[0],x.shape[1],kw['f'],-1)
    if p=='bcfrt1->b(t1fr)c': return x.permute(0,3,2,1).flatten(1,2)
    if p=='b(t1fr)c->bcfrt1': return x.reshape(x.shape[0],kw['t1'],-1,x.shape[2]).permute(0,3,2,1)
    if p in ['bct2->bt2c','bt2c->bct2']: return x.permute(0,2,1)
    if p=='t2bc->bt2c': return x.permute(1,0,2)
    raise ValueError(pattern)
sys.modules['einops']=types.ModuleType('einops')
sys.modules['einops'].rearrange=rearrange
from demucs.htdemucs import HTDemucs
torch.set_num_threads(3)
modelpath=Path('/Users/weiliangluo/.cache/huggingface/hub/models--adefossez--HTDemucs-6s/snapshots/cbc8a9b1a87023b7fd74e7b3412c0eab003/5c90dfd2.safetensors')
if not modelpath.exists():
    modelpath=next(Path('/Users/weiliangluo/.cache/huggingface/hub/models--adefossez--HTDemucs-6s/snapshots').glob('*/5c90dfd2.safetensors'))
with open(modelpath,'rb') as f:
    headerlen=struct.unpack('<Q',f.read(8))[0]
    header=json.loads(f.read(headerlen)); raw=f.read()
meta=header.pop('__metadata__')
print('metadata',meta.keys(),flush=True)
kwargs=json.loads(meta['kwargs']); kwargs['segment']=7.8
model=HTDemucs(**kwargs)
state={}
for k,v in header.items():
    a,b=v['data_offsets'];dtype={'F16':'<f2','F32':'<f4','I64':'<i8'}[v['dtype']]
    state[k]=torch.from_numpy(np.frombuffer(raw[a:b],dtype=dtype).copy().reshape(v['shape'])).float()
print(model.load_state_dict(state,strict=True),flush=True)
model.eval(); del state,raw
device='cpu'
model.to(device)
audio=np.fromfile('work/v2_stereo.f32',dtype='<f4').reshape(-1,2).T
regions=[(64,90)]
audio=np.concatenate([audio[:,int(a*44100):int(b*44100)] for a,b in regions],axis=1)
N=audio.shape[1]; sr=44100
if '--test' in sys.argv:audio=audio[:,sr*18:sr*26];N=audio.shape[1]
seg=int(7.8*sr);stride=int(seg*.75)
result=np.zeros((6,2,N),np.float32); weights=np.zeros(N,np.float32)
weight=np.minimum(np.arange(1,seg+1),np.arange(seg,0,-1)).astype(np.float32);weight/=weight.max()
t0=time.time()
with torch.inference_mode():
    for i,start in enumerate(range(0,N,stride)):
        end=min(start+seg,N);chunk=audio[:,start:end]
        ref=chunk.mean(axis=0); mu=ref.mean();sd=ref.std()
        x=torch.from_numpy((chunk-mu)/(sd+1e-8))[None].to(device)
        y=model(x)[0].cpu().numpy()*(sd+1e-8)+mu
        w=weight[:end-start];result[:,:,start:end]+=y[:,:,:end-start]*w;weights[start:end]+=w
        print(f'{i+1}/{len(range(0,N,stride))} {end/sr:.1f}s elapsed {time.time()-t0:.1f}s',flush=True)
result/=weights[None,None]
out=Path('work/v2_stems6_test' if '--test' in sys.argv else 'work/v2_stems6');out.mkdir(exist_ok=True)
(out/'regions.json').write_text(json.dumps(regions))
for name,y in zip(model.sources,result):
    y.T.tofile(out/f'{name}.f32')
print('DONE',flush=True)
