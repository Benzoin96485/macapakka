from pathlib import Path
p=Path('outputs/EYKM_Acappella_v2/source/render_arrangement.py');s=p.read_text()
# Merge notated ties for both MIDI and synthesized practice tracks.
insert='''def sounding_events(part):
 events=[]
 for i,measure in enumerate(score[part]):
  offset=0
  for e in measure:
   if e['p'] is not None:
    if e.get('tie_stop') and events and events[-1]['p']==e['p'] and abs(events[-1]['end']-(i*3+offset))<1e-7:
     events[-1]['end']+=e['d']
    else:events.append(dict(p=e['p'],start=i*3+offset,end=i*3+offset+e['d'],ly=e.get('ly',''),bar=i))
   offset+=e['d']
 return events

'''
s=s.replace('def writemidi(path,selected):',insert+'def writemidi(path,selected):')
a=s.index('  for i,m in enumerate(score[p]):',s.index('def writemidi'))
b=s.index('  tracks.append(track(ev))',a)
s=s[:a]+'''  for e in sounding_events(p):
   st=round(e['start']*TPQ);en=round((e['end']-.035)*TPQ)
   vel=DYN[meta[e['bar']]['dynamic']]+(8 if p=='Lead' else (-15 if p=='VP' else -5 if p=='Whistle' else 0))
   ev.extend([(st,3,bytes([0x90|ch,e['p'],max(25,min(110,vel))])),(en,2,bytes([0x80|ch,e['p'],0]))])
'''+s[b:]
a=s.index(' for i,m in enumerate(score[p]):',s.index('stems={}'))
b=s.index(' stems[p]=arr',a)
s=s[:a]+''' def beattime(q):
  i=min(len(meta)-1,int(q//3));return starts[i]+(q-i*3)*60/meta[i]['tempo']
 for e in sounding_events(p):
  pos=beattime(e['start']);dur=beattime(e['end'])-pos
  amp=DYN[meta[e['bar']]['dynamic']]/100
  d=max(.05,dur-(.04 if p=='Whistle' else .025));z=synth(e['p'],d,p,e.get('ly',''))
  ix=int(pos*SR);arr[ix:ix+len(z)]+=z*amp
'''+s[b:]
# Whistle and detailed arpeggios benefit from three-bar parts.
s=s.replace("barsper=3 if part=='Lead' else 4","barsper=3 if part in ['Lead','Whistle','Tenor','Alto'] else 4")
s=s.replace("'SATB_crossing='", "'SATB_crossing='")
# Metadata carries original recording time references into all deliveries.
s=s.replace("key=inf['key']))","key=inf['key'],source_time=inf.get('source_time')))" )
p.write_text(s)
