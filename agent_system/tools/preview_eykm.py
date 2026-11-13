import sys,json
from pathlib import Path
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'agent_system'))
from vibacappella.samples import SampleBank,SR
from vibacappella.music import PARTS,sound_events,tick_to_seconds
s=json.loads((ROOT/'agent_system/runs/eykm-sonnet55-01/first-pass-score.json').read_text())
a0=41.8585714286;b0=66.1442857143
bank=SampleBank(Path('/Applications/MuseScore 4.app/Contents/Resources/sound/MS Basic.sf3'))
y=np.zeros((round((b0-a0+2)*SR),2),np.float32)
gains={'Lead':1,'Soprano':.75,'Alto':.7,'Tenor':.7,'Bass':.95,'VP':.6,'Whistle':.95}
for p in PARTS:
 for e in sound_events(s,p):
  a=tick_to_seconds(s,e['start']);b=tick_to_seconds(s,e['end'])
  if b<=a0 or a>=b0:continue
  z=bank.tone(128 if p=='VP' else 0,73 if p=='Whistle' else 0,e['pitch'],e['velocity'],max(.04,b-a-.025))
  off=round((a-a0)*SR)
  if off<0:z=z[-off:];off=0
  n=min(len(z),len(y)-off)
  y[off:off+n]+=z[:n]*gains[p]*(.32 if p=='VP' else .8 if p=='Whistle' else 12)
y*=.91/max(1e-8,float(abs(y).max()))
sf.write(ROOT/'outputs/EYKM_Sonnet55/preview_firstpass.wav',y,SR)
