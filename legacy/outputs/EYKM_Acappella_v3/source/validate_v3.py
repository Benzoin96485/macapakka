"""Check canonical v3, actual XML notes and timing, MIDI, source-only whistle and colour map."""
from pathlib import Path
import json,xml.etree.ElementTree as ET,hashlib,subprocess,collections
import numpy as np
from mxl import NAT, P
from v2_trfile import read_tr
ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT.parents[1]
d=json.loads((ROOT/'source/arrangement.json').read_text());parts=d['parts'];meta=d['metadata']
errors=[];checks={};stats={}
def require(ok,message):
    if not ok:errors.append(message)
def expand(bar):
    return [e['p'] for e in bar for _ in range(round(e['d']*4))]
for p in parts:
    bars=d['score'][p];require(len(bars)==198,p+' bar count')
    previous=None;longest=0;run=0;notes=0
    for bi,bar in enumerate(bars):
        require(abs(sum(e['d'] for e in bar)-3)<1e-9,f'{p} bar {bi+1} duration')
        for e in bar:
            require(e['d']>0 and abs(e['d']*4-round(e['d']*4))<1e-8,f'{p} duration grid')
            if e.get('tie_stop'):
                require(previous is not None and previous.get('tie_start') and previous['p']==e['p'],f'{p} orphan tie stop {bi+1}')
            if previous and previous.get('tie_start'):
                require(e['p']==previous['p'] and e.get('tie_stop'),f'{p} bad tie start {bi+1}')
            if e['p'] is not None:
                notes+=not e.get('tie_stop');run+=e['d']/3*(meta[bi]['source_end']-meta[bi]['source_time'])
                longest=max(longest,run)
            else:run=0
            previous=e
    stats[p]=dict(attacks=notes,longest_unbroken_phrase_seconds=round(longest,3),range=d.get('ranges',{}).get(p))
for bi in range(198):
    grids={p:expand(d['score'][p][bi]) for p in parts}
    for slot in range(12):
        choir=[grids[p][slot] for p in ('Soprano','Alto','Tenor','Bass') if grids[p][slot] is not None]
        require(all(a>=b for a,b in zip(choir,choir[1:])),f'Choir crossing bar {bi+1} tick {slot}')
    if not 43<=bi<=58:require(all(x is None for x in grids['Whistle']),f'Non-flute whistle at bar {bi+1}')
wh=read_tr(PROJECT/'work/v3/reference/whistle.txt')
for k in range(47,63):
    ref=[e.pitches[0].midi-12 if e.pitches else None for e in wh[k] for _ in range(e.dur)]
    require(ref==expand(d['score']['Whistle'][k-4]),f'Flute line changed at {k-3}')
for k in range(4,12):
    ref=[e.pitches[0].midi-12 if e.pitches else None for e in wh[k] for _ in range(e.dur)]
    actual=expand(d['score']['Soprano'][k-4])
    require(all(n is None or n==r for n,r in zip(actual,ref)),f'Piano theme register/contour changed at {k-3}')
for p in ('Soprano','Alto','Tenor'):
    for bi,bar in enumerate(d['score'][p]):
        for e in bar:
            if e['role']=='piano' and e['p'] is not None:
                require(e['p']%12==e['source']['original_midi']%12,f'Piano pitch class changed {p} {bi+1}')

xmls=[ROOT/'scores/EYKM_v3_Full_Score.musicxml']+list((ROOT/'parts').glob('*.musicxml'))
xml_counts={}
for path in xmls:
    root=ET.parse(path).getroot();names={p.attrib['id']:p.findtext('part-name') for p in root.findall('part-list/score-part')}
    drum_ids={m.attrib['id']:int(m.findtext('midi-unpitched'))-1 for m in root.findall('part-list/score-part/midi-instrument') if m.find('midi-unpitched') is not None}
    for part in root.findall('part'):
        name=names[part.attrib['id']];measures=part.findall('measure')
        require(len(measures)==198,f'{path.name} count')
        for bi,m in enumerate(measures):
            grid=[]
            for note in m.findall('note'):
                dur=int(note.findtext('duration'));n=None
                if note.find('pitch') is not None:
                    pitch=note.find('pitch');n=12*(int(pitch.findtext('octave'))+1)+NAT[pitch.findtext('step')]+int(pitch.findtext('alter','0'))
                elif note.find('unpitched') is not None:n=drum_ids[note.find('instrument').attrib['id']]
                grid.extend([n]*dur)
            require(grid==expand(d['score'][name][bi]),f'XML mismatch {path.name} {name} bar {bi+1}')
    xml_counts[path.name]=len(root.findall('part'))
checks['xml_note_grid_matches']=xml_counts

import mido
midpaths=list((ROOT/'midi').glob('*.mid'));mid_times={}
from render_samples import events
for path in midpaths:
    m=mido.MidiFile(path);mid_times[path.name]=m.length
    require(abs(m.length-(meta[-1]['source_end']-meta[0]['source_time']))<.02,'MIDI timing '+path.name)
    for tr in m.tracks:
        name=next((msg.name for msg in tr if msg.type=='track_name'),None)
        if name not in parts:continue
        tick=0;active={};found=[]
        for msg in tr:
            tick+=msg.time
            if msg.type=='note_on' and msg.velocity>0:active[msg.note]=tick
            elif msg.type=='note_off' or (msg.type=='note_on' and msg.velocity==0):
                if msg.note in active:found.append((msg.note,active.pop(msg.note),tick))
        expected=[(e['p'],round(e['start']*480),round(e['end']*480)) for e in events(name)]
        require(sorted(found)==sorted(expected),'MIDI note events '+path.name+' '+name)
        require(not active,'MIDI stuck notes '+path.name+' '+name)
checks['midi_durations']=mid_times
checks['whistle_source_interval_bars']=[44,59]
checks['whistle_octave_change']=-1
checks['piano_theme_contour']='introductory pitches and attacks preserved, one octave lower; logged breath releases'
checks['choir_crossings']=sum('crossing' in x for x in errors)
checks['input_sha256']=hashlib.sha256((PROJECT/'input/EYKM.flac').read_bytes()).hexdigest()
checks['input_unchanged']=checks['input_sha256']==d['source_sha256']
require(checks['input_unchanged'],'Input hash changed')
checks['half_bar_harmony_changes']=sum(len(m['harmonies'])>1 for m in meta)
checks['source_backed_background_events']=sum(e['role']=='vocal_backing' for p in ('Alto','Tenor') for b in d['score'][p] for e in b)
checks['vp_unique_bar_patterns']=len({tuple((e['p'],e['d']) for e in b) for b in d['score']['VP'] if any(e['p'] is not None for e in b)})
checks['vp_sounding_bars']=sum(any(e['p'] is not None for e in b) for b in d['score']['VP'])
checks['lyric_underlay']=d['lyric_underlay']
audio={}
for path in (ROOT/'audio').glob('*.mp3'):
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration,size','-of','json',str(path)]))['format']
    audio[path.name]=info;require(abs(float(info['duration'])-298.72)<.10,'MP3 timing '+path.name)
checks['audio']=audio
result=dict(pass_all=not errors,errors=errors,checks=checks,parts=stats,human_listening_review=False,
    limits='Checks establish internal consistency and recorded source provenance; they do not certify every inferred harmony/background pitch against the original performance.')
(ROOT/'source/validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(dict(pass_all=not errors,errors=errors,parts=stats,lyrics=d['lyric_underlay']),ensure_ascii=False,indent=2))
if errors:raise SystemExit(1)
