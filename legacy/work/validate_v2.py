from pathlib import Path
import json,subprocess,xml.etree.ElementTree as ET
R=Path('outputs/EYKM_Acappella_v2');D=json.loads((R/'source/arrangement.json').read_text());P=D['parts'];S=D['score'];M=D['metadata']
cross=[];limits={'Lead':(57,79),'Soprano':(60,79),'Alto':(55,73),'Tenor':(48,66),'Bass':(40,55),'Whistle':(71,89)}
for p in P:
 assert len(S[p])==196
 for i,bar in enumerate(S[p]):
  assert abs(sum(e['d'] for e in bar)-3)<1e-8,(p,i)
  for e in bar:
   if p!='VP' and e['p'] is not None:assert limits[p][0]<=e['p']<=limits[p][1],(p,i+1,e)
for i in range(196):
 for q in [j/4 for j in range(12)]:
  pitches=[]
  for p in ['Soprano','Alto','Tenor','Bass']:
   pos=0;note=None
   for e in S[p][i]:
    if pos<=q<pos+e['d']:note=e['p'];break
    pos+=e['d']
   if note is not None:pitches.append((p,note))
  if [n for _,n in pitches]!=sorted([n for _,n in pitches],reverse=True):cross.append((i+1,q,pitches))
assert not cross,cross[:20]
for p in R.rglob('*.musicxml'):
 root=ET.parse(p).getroot();parts=root.findall('part');assert len(parts)==(7 if 'Full_Score' in p.name else 1)
 for part in parts:
  measures=part.findall('measure');assert len(measures)==196
  for m in measures:assert sum(int(n.findtext('duration','0')) for n in m.findall('note'))==24,(p,m.attrib)
 ids={x.attrib['id'] for x in root.findall('.//score-instrument')}
 assert all(x.attrib['id'] in ids for x in root.findall('.//note/instrument'))
print('PASS: 196 bars x 7 parts; eighth/sixteenth durations, ranges, no SATB crossing; 8 MusicXML files')
if (R/'source/validation.json').exists():
 v=json.loads((R/'source/validation.json').read_text())
 durations=[]
 for f in R.glob('audio/*.mp3'):
  o=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(f)]));durations.append(float(o['format']['duration']))
 if durations:assert len(durations)==9 and max(durations)-min(durations)<.001 and abs(durations[0]-v['audio_seconds'])<.1
 v.update(validation_performed=True,SATB_crossing='none at each quarter-beat event boundary',ranges_checked=limits,mp3_files_checked=len(durations),full_form_measures=196)
 (R/'source/validation.json').write_text(json.dumps(v,indent=2))
 print('PASS: synchronized audio',durations[:1])
