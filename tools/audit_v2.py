"""Read-only audit of archived musical data; writes only the requested audit JSON."""
from pathlib import Path
import argparse, ast, collections, hashlib, json, re, subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'outputs/EYKM_Acappella_v2'

def probe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)
    ]))

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    data = json.loads((R/'source/arrangement.json').read_text())
    tr = json.loads((R/'source/transcription.json').read_text())
    meta, score, parts = data['metadata'], data['score'], data['parts']
    out = {'audit_scope': 'Current files and code, not auditory or original-score accuracy',
           'measures': len(meta), 'parts': parts, 'source_sha256': digest(ROOT/'input/EYKM.flac')}
    assert out['source_sha256'] == data['source_sha256']
    assert len(meta) == len(tr['bars']) == 196
    out['source_audio'] = probe(ROOT/'input/EYKM.flac')
    out['ranges'] = {}; out['events'] = {}; out['longest_sounding_spans'] = {}
    def seconds(q):
        i = min(int(q//3), len(meta)-1)
        return sum(180/x['tempo'] for x in meta[:i]) + (q-i*3)*60/meta[i]['tempo']
    for part in parts:
        assert len(score[part]) == 196
        spans = []
        for i, bar in enumerate(score[part]):
            assert abs(sum(e['d'] for e in bar)-3) < 1e-8
            pos = 0
            for e in bar:
                assert e['d'] > 0 and abs(e['d']*4-round(e['d']*4)) < 1e-8
                start = i*3+pos; end = start+e['d']; pos += e['d']
                if e['p'] is None: continue
                if e.get('tie_stop') and spans and spans[-1]['pitch']==e['p'] and abs(spans[-1]['end']-start)<1e-8:
                    spans[-1]['end'] = end
                else: spans.append({'bar':i+1,'pitch':e['p'],'start':start,'end':end})
        for s in spans: s['seconds'] = seconds(s['end'])-seconds(s['start'])
        out['events'][part] = {'notated':sum(len(b) for b in score[part]), 'sounding_attacks':len(spans)}
        out['ranges'][part] = [min(s['pitch'] for s in spans),max(s['pitch'] for s in spans)]
        out['longest_sounding_spans'][part] = sorted(spans,key=lambda s:s['seconds'],reverse=True)[:3]
    for i in range(196):
        for q in [k/4 for k in range(12)]:
            sounding=[]
            for part in ['Soprano','Alto','Tenor','Bass']:
                pos=0
                for e in score[part][i]:
                    if pos <= q < pos+e['d']:
                        if e['p'] is not None: sounding.append(e['p'])
                        break
                    pos+=e['d']
            assert sounding==sorted(sounding,reverse=True),(i+1,q,sounding)
    out['satb_crossings']=0
    def expected(bar):
        result=[]
        for e in bar:
            remaining=e['d']
            for dur in [3,2,1.5,1,.75,.5,.25]:
                while remaining >= dur-1e-7:
                    result.append((e['p'],round(dur*8))); remaining-=dur
            assert abs(remaining)<1e-7
        return result
    out['musicxml']=[]
    for path in sorted(R.rglob('*.musicxml')):
        xml=ET.parse(path).getroot()
        declared={p.attrib['id']:p.findtext('part-name') for p in xml.findall('part-list/score-part')}
        assert len(xml.findall('part')) == (7 if path.parent.name=='scores' else 1)
        ids={i.attrib['id'] for i in xml.findall('.//score-instrument')}
        for p in xml.findall('part'):
            name=declared[p.attrib['id']]; measures=p.findall('measure'); assert len(measures)==196
            for i,m in enumerate(measures):
                notes=[]
                for n in m.findall('note'):
                    dur=int(n.findtext('duration','0'))
                    if n.find('rest') is not None: pitch=None
                    elif n.find('unpitched') is not None:
                        inst=n.find('instrument').attrib['id']; assert inst in ids
                        pitch={'K':36,'S':38,'H':42}[inst.rsplit('-',1)[1]]
                    else:
                        pi=n.find('pitch'); pitch=(int(pi.findtext('octave'))+1)*12
                        pitch+=dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[pi.findtext('step')]+int(pi.findtext('alter','0'))
                    notes.append((pitch,dur))
                assert sum(d for _,d in notes)==24,(path,i)
                assert notes==expected(score[name][i]),(path,i,name)
        out['musicxml'].append(str(path.relative_to(ROOT)))
    a=ET.parse(R/'scores/EYKM_Full_Score.musicxml').getroot()
    b=ET.parse(R/'scores/EYKM_v2_MuseScore_Piano_Flute_Drums.musicxml').getroot()
    out['musescore_notation_identical']=all(ET.tostring(x)==ET.tostring(y) for x,y in zip(a.findall('part'),b.findall('part')))
    assert out['musescore_notation_identical']
    out['musescore_mapping']=[{'part':p.findtext('part-name'),'midi':[{v.tag:v.text for v in mi} for mi in p.findall('midi-instrument')]} for p in b.findall('part-list/score-part')]
    out['musical_seconds']=seconds(588)
    out['mp3']=[{'file':str(p.relative_to(ROOT)), 'duration':float(probe(p)['format']['duration'])} for p in sorted((R/'audio').glob('*.mp3'))]
    assert len(out['mp3'])==9 and max(x['duration'] for x in out['mp3'])-min(x['duration'] for x in out['mp3'])<.001
    out['pdf_pages']={str(p.relative_to(ROOT)):len(re.findall(rb'/Type\s*/Page\b',p.read_bytes())) for p in sorted(R.rglob('*.pdf'))}
    try:
        import mido
        out['midi']=[{'file':str(p.relative_to(ROOT)), 'duration':mido.MidiFile(p).length} for p in sorted((R/'midi').glob('*.mid'))]
        assert len(out['midi'])==9
        assert all(abs(m['duration']-out['musical_seconds'])<.01 for m in out['midi'])
    except ImportError: out['midi']='Not checked: install mido to enable duration checks'
    out['sections']=[]
    for i,m in enumerate(meta):
        if m['local']==1:
            out['sections'].append({k:m[k] for k in ['bar','section','label','key','source_time','source_end']})
    for i,s in enumerate(out['sections']):
        s['last_bar']=out['sections'][i+1]['bar']-1 if i+1<len(out['sections']) else 196
    out['explicit_overrides']={p:sum(p in b for b in tr['bars']) for p in parts}
    for filename,var in [('edit_transcription_v2.py','M'),('instruments_v2.py','W')]:
        for n in ast.parse((ROOT/'work'/filename).read_text()).body:
            if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==var for t in n.targets):
                out[filename+'_explicit_bars']=len(ast.literal_eval(n.value))
    out['status']='PASS'
    if args.output: args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['status','measures','ranges','musical_seconds','satb_crossings','explicit_overrides','edit_transcription_v2.py_explicit_bars','instruments_v2.py_explicit_bars']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
