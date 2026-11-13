"""Import EYKM's existing transcription evidence, not its SATB arrangement."""
import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'agent_system'))
sys.path.insert(0,str(ROOT/'outputs/EYKM_Acappella_v3/source'))
from mxl import Chord
from vibacappella.music import check_evidence
from vibacappella.storage import sha256,write_json
from vibacappella.audio_worker import drum_evidence
v=json.loads((ROOT/'outputs/EYKM_Acappella_v3/source/arrangement.json').read_text())
meta=v['metadata']; bars=[];anchors=[];harmonies=[];notes=[]
for m in meta:
 i=m['bar']-1; start=i*1440
 bars.append(dict(number=i+1,start_tick=start,duration_ticks=1440,numerator=3,denominator=4,section=m['label']))
 anchors.append(dict(tick=start,seconds=m['source_time']))
 for h in m['harmonies']:
  c=Chord(h['symbol']);pcs=[p.midi%12 for p,r in c.tones]
  harmonies.append(dict(id=f'h:{start+round(h["offset"]*480)}',start_tick=start+round(h['offset']*480),end_tick=start+round((h['offset']+h['duration'])*480),locked=True,confidence='inherited_reference_not_human_verified',candidates=[dict(symbol=h['symbol'],pcs=pcs,required_pcs=[p for p in pcs if (p-c.root.midi)%12 not in (0,7)],bass_pc=c.bass.midi%12,score=1.0)]))
 # Preserve prior lead transcription/lyric alignment and verified-range flute reference.
 for part,source,role in [('Lead','lead','lead'),('Whistle','flute','flute')]:
  off=0
  for j,n in enumerate(v['score'][part][i]):
   a=m['source_time']+off/3*(m['source_end']-m['source_time']);off+=n['d'];b=m['source_time']+off/3*(m['source_end']-m['source_time'])
   if n['p'] is None: continue
   d=dict(id=f'{source}:{i+1}:{j}',source=source,instrument=source,role=role,start=a,end=b,pitch=n['p'],confidence=.85,syllable=n.get('ly',''),attribution='inherited_v3_reference_transcription')
   if part=='Whistle': d['instrument_confidence']=.8
   notes.append(d)
anchors.append(dict(tick=len(meta)*1440,seconds=meta[-1]['source_end']))
for stem in ['piano','guitar','bass','vocals']:
 for j,(a,b,p,amp) in enumerate(np.load(ROOT/f'work/v3/reference/{stem}.npy')):
  if b-a<.09 or amp<.32 or b<=anchors[0]['seconds'] or a>=anchors[-1]['seconds']:continue
  role='candidate'
  if stem=='vocals':
   if b-a<.35:continue
   overlap=[n for n in notes if n['role']=='lead' and n['start']<b and n['end']>a]
   if any((int(p)-n['pitch'])%12==0 or int(p)-n['pitch'] in (19,28) for n in overlap):continue
   role='backing_candidate'
  notes.append(dict(id=f'{stem}:raw:{j}',source=stem,instrument=stem,role=role,start=max(float(a),anchors[0]['seconds']),end=min(float(b),anchors[-1]['seconds']),pitch=int(p),confidence=min(1,float(amp))))
drum_path=Path('/Users/weiliangluo/src/vibacappella-claude/_work/sep/htdemucs_6s/eykm/drums.wav')
e=dict(schema_version=1,audio_sha256=sha256(ROOT/'input/EYKM.flac'),duration_seconds=299.106667,timing={'anchors':anchors},bars=bars,notes=notes,harmonies=harmonies,drums=drum_evidence(drum_path),alerts=['Inherited V3 timing, lead/lyrics and chord reference; not a published score or fresh human transcription.','Flute identity inherited only for the V3 interlude; attribution remains subject to listening review.','Piano, guitar, bass and backing use existing Basic Pitch candidates; leakage and vocal harmonics remain possible.','SATB and VP are newly arranged by Sonnet 5.5 through tools; no previous SATB arrangement is imported.'],provenance={'human_review':False,'reference_sha256':sha256(ROOT/'outputs/EYKM_Acappella_v3/source/arrangement.json'),'drums_sha256':sha256(drum_path)})
check_evidence(e)
out=ROOT/'agent_system/runs/eykm-sonnet55-evidence.json';write_json(out,e)
print(f'{len(bars)} bars, {len(notes)} notes, {len(e["drums"])} drum candidates: {out}')
