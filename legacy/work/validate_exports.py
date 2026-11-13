import json,subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
root=Path('outputs/EYKM_Acappella');d=json.loads((root/'source/arrangement.json').read_text())
files=list(root.rglob('*.musicxml'))
notes=0
for file in files:
 r=ET.parse(file).getroot();parts=r.findall('part')
 assert len(parts)==(7 if 'Full_Score' in file.name else 1)
 for part in parts:
  assert len(part.findall('measure'))==136
  for m in part.findall('measure'):
   dur=sum(int(n.findtext('duration','0')) for n in m.findall('note'));assert dur==24,(file,m.attrib,dur)
   for n in m.findall('note'):
    if n.find('rest') is None:notes+=1
 # Every instrument ID in notation resolves within the part-list.
 ids={x.attrib['id'] for x in r.findall('.//score-instrument')}
 assert all(n.attrib['id'] in ids for n in r.findall('.//note/instrument'))
 print('XML OK',file.name)
for path in root.glob('audio/*.mp3'):
 v=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)]))
 duration=float(v['format']['duration']);assert 204<duration<206,(path,duration)
print('Audio durations OK: 9 matching full-length files')
print('MusicXML sounding note elements',notes)
