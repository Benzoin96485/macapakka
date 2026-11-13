from pathlib import Path
s=Path('outputs/EYKM_Acappella/source/build_arrangement.py').read_text()
imports=s[s.index('from pathlib'):s.index('# Theme A:')]
imports=imports[:imports.index("ROOT=Path")]+'''ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'source/arrangement.json').read_text())
PARTS=DATA['parts']; SHORT=['Ld.','S','A','T','B','VP','Wh.']
TITLE=DATA['title']; score=DATA['score'];meta=DATA['metadata']; RANGES=DATA['ranges']
CHORDS=DATA['chords']
KEYS={'Cm':-3,'Fm':-4,'Dm':-1,'Gm':-2,'Em':1,'Am':0,'C#m':4,'F#m':3,'Bm':2}
NOTENAMES=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
'''
suffix=s[s.index('# MusicXML utilities.'):]
suffix=suffix.replace("'Theme arrangement prepared with ChatGPT for student rehearsal'","'Full-form a cappella arrangement v2 for student ensemble'")
suffix=suffix.replace("TITLE+' | Student chamber a cappella'","TITLE+' | Full-form a cappella v2'")
suffix=suffix.replace("'Theme phrasing; original ornaments optional'","'Keep text, melismas and phrase shape; breathe at marked rests'")
suffix=suffix.replace("{'intro':'dolce','verse':'sotto voce','full':'cantabile','whistle':'leggero','verse2':'flowing','bridge':'wordless; conversational','reprise':'espressivo','climax':'open ah; lead remains clear','coda':'diminuendo; no added hold'}[inf['style']]","inf.get('direction','cantabile')")
suffix=suffix.replace("Theme arrangement / rehearsal draft 1","Full-form arrangement v2 / rehearsal edition")
suffix=suffix.replace("Music: Yuki Kajiura; student theme arrangement","Music: Yuki Kajiura; full-form student a cappella v2")
suffix=suffix.replace("range(-KEYS[key])","range(abs(KEYS[key]))")
suffix=suffix.replace("x+(-KEYS[key])*space*1.25","x+abs(KEYS[key])*space*1.25")
suffix=suffix.replace("vals=[4,7,3,6,2] if clef!='bass' else [2,5,1,4,0]","vals=([8,5,9,6,3,7,4] if clef!='bass' else [6,3,7,4,1,5,2]) if KEYS[key]>0 else ([4,7,3,6,2,5,1] if clef!='bass' else [2,5,1,4,0,3,-1])")
suffix=suffix.replace("'\\u266d',space*3.1","('\\u266f' if KEYS[key]>0 else '\\u266d'),space*3.1")
suffix=suffix.replace("head=65 if part else 77","head=77 if part else 87")
suffix=suffix.replace("flat_steps=set('BEADG'[:max(0,-KEYS[inf['key']])]);acc_state={}","flat_steps=set('BEADGCF'[:max(0,-KEYS[inf['key']])]);sharp_steps=set('FCGDAEB'[:max(0,KEYS[inf['key']])]);acc_state={}")
suffix=suffix.replace("-1 if st in flat_steps else 0)","-1 if st in flat_steps else 1 if st in sharp_steps else 0)")
suffix=suffix.replace("typ={.5:'eighth',1:'quarter',1.5:'quarter',2:'half',3:'half'}[e['d']]","typ={.25:'16th',.5:'eighth',.75:'eighth',1:'quarter',1.5:'quarter',2:'half',3:'half'}[e['d']]")
suffix=suffix.replace("in [1.5,3]","in [.75,1.5,3]")
suffix=suffix.replace("if e['d']==.5:","if e['d'] in [.25,.5,.75]:")
suffix=suffix.replace("c.setLineWidth(1.3);c.drawPath(pth)","c.setLineWidth(1.3);c.drawPath(pth)\n   if e['d']==.25:\n    p2=c.beginPath();p2.moveTo(stemx,stemy-sgn*space*.8);p2.curveTo(stemx+space*1.8,stemy-sgn*space*1.4,stemx+space*1.4,stemy-sgn*space*2.5,stemx+space*.5,stemy-sgn*space*2.8);c.drawPath(p2)")
suffix=suffix.replace("cp='\\U0001d13d' if e['d']>=1 else '\\U0001d13e'","cp='\\U0001d13d' if e['d']>=1 else ('\\U0001d13f' if e['d']==.25 else '\\U0001d13e')")
suffix=suffix.replace("if e['d']==1.5:","if e['d'] in [.75,1.5]:")
suffix=suffix.replace("if '--notation-only' in sys.argv:","if '--notation-only' in sys.argv:")
suffix=suffix.replace("SR=22050;COUNT=6*60/108","SR=22050;COUNT=6*60/meta[0]['tempo']")
suffix=suffix.replace("st=int(i*60/108*SR)","st=int(i*60/meta[0]['tempo']*SR)")
suffix=suffix.replace("pitch_source='hand-authored theme adaptation informed by supplied-audio spectral analysis; not a critical transcription'","pitch_source='Local source separation and pitch/onset analysis, with editorial transcription and new SATB/VP orchestration'")
suffix=suffix.replace("human_listening_review=False","human_listening_review=False,version='2.0',source_seconds=299.106667")
# Replace enharmonic spelling and duration decomposition.
a=suffix.index('def spell(');b=suffix.index('def mkxml(',a)
suffix=suffix[:a]+'''def spell(n,key='Cm',chord=None):
 pc=n%12;octv=n//12-1
 scale=KEYS[key]
 names=(['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'] if scale>0 else NOTENAMES)
 if chord:
  root=chord.split('/')[0]
  if root.startswith('A7') and pc==1: return 'C',1,octv
  if root.startswith('D7') and pc==6: return 'F',1,octv
  if root.startswith('E7') and pc==8: return 'G',1,octv
  if root.startswith('B7') and pc==3: return 'D',1,octv
  if root.startswith('C#7') and pc==5: return 'E',1,octv
  if root.startswith('G#7') and pc==0:return 'B',1,octv-1
 na=names[pc];return na[0],(-1 if 'b' in na else 1 if '#' in na else 0),octv

def fragments(e):
 d=e['d'];pieces=[]
 for value in [3,2,1.5,1,.75,.5,.25]:
  while d>=value-1e-7:
   pieces.append(value);d-=value
 assert abs(d)<1e-7
 out=[]
 for j,v in enumerate(pieces):
  x=dict(e,d=v)
  if j:x['ly']=''
  if e['p'] is not None:
   if j:x['tie_stop']=True
   if j<len(pieces)-1:x['tie_start']=True
  out.append(x)
 return out

'''+suffix[b:]
# Remove duplicated staff detail.
suffix=suffix.replace("     if p=='VP':sd=sub(at,'staff-details');sub(sd,'staff-lines',1)\n     if p=='VP':sd=sub(at,'staff-details');sub(sd,'staff-lines',1)","     if p=='VP':sd=sub(at,'staff-details');sub(sd,'staff-lines',1)")
Path('outputs/EYKM_Acappella_v2/source/render_arrangement.py').write_text('''"""Engrave and render the explicit v2 event score. No original audio embedded."""\n'''+imports+suffix)
