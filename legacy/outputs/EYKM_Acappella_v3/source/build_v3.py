"""Evidence-led seven-singer reduction of EYKM. No source audio enters the render.

Run from any directory. Notes retain provenance; non-pitch percussion is monophonic.
The inherited chord/lead/bass transcriptions are editorial evidence, not a ground truth score.
"""
from pathlib import Path
import json, csv, copy, itertools, hashlib, sys
import numpy as np
from mxl import P, Chord, Ev, PartSpec, finalize, write_score, parse, voice_upper, place_bass
from v2_trfile import read_tr

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
REF = PROJECT / 'work/v3/reference'
ANALYSIS = PROJECT / 'work/v3/analysis'
PARTS = ['Lead', 'Soprano', 'Alto', 'Tenor', 'Bass', 'VP', 'Whistle']
FIRST, LAST = 4, 201
KEYS = list(range(FIRST, LAST + 1))
RANGES = {'Soprano': (62, 81), 'Alto': (55, 74), 'Tenor': (48, 67), 'Bass': (40, 55)}
NAMES_FLAT = ['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
NAMES_SHARP = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

def read_chords():
    out = {}
    for line in (REF/'chords.txt').read_text().splitlines():
        if not line or line.startswith('#'): continue
        k, text = line.split(':', 1)
        a = [x.strip() for x in text.split('|')]
        out[int(k)] = [(Chord(x), 12//len(a)) for x in a]
    return out

CH = read_chords()
LEAD, BASS, WH = [read_tr(REF/f'{n}.txt') for n in ('lead','bass','whistle')]
RAW = {n: np.load(REF/f'{n}.npy') for n in ('piano','vocals','other','bass','guitar')}

# Free opening and ending follow the source attacks, rather than a fixed-tempo shortening.
BOUNDARIES = [.18,2.16,3.86,5.44,7.21,8.87,10.79,12.85,17.572857142857]
BOUNDARIES += [.43 + k*180/126 for k in range(13,198)]
BOUNDARIES += [282.8736517, 285.8, 289.1, 292.7, 296.4]
# key 197 begins at 281.8586; 198 is the last piano chord, not a new composition.
assert len(BOUNDARIES) == len(KEYS)+1, len(BOUNDARIES)

SECTIONS = [
 (4,'A','Piano prologue','Cm','intro','p'),
 (13,'B','Verse 1','Cm','verse','p'),
 (29,'C','Chorus 1','Fm','chorus1','mp'),
 (47,'D','Flute interlude','Fm','flute','mf'),
 (63,'E','Verse 2','Dm','verse2','mp'),
 (79,'F','Chorus 2','Gm','chorus2','mf'),
 (101,'G','Layered vocalise','Gm','vocalise','mf'),
 (117,'H','Bridge','Em','bridge','mf'),
 (142,'I','Instrumental transition','Gm','transition','p'),
 (149,'J','Verse 3','C#m','verse3','p'),
 (165,'K','Chorus 3','F#m','chorus3','mf'),
 (185,'L','Vocal tag','F#m','tag','p'),
 (195,'M','Piano epilogue','F#','outro','pp')]
def section(k): return next(s for s in reversed(SECTIONS) if k >= s[0])
def tim(k, slot=0):
    i=k-FIRST
    return BOUNDARIES[i] + slot/12*(BOUNDARIES[i+1]-BOUNDARIES[i])
def chord_at(k, slot):
    p=0
    for ch,d in CH[k]:
        if p <= slot < p+d: return ch
        p += d
    return CH[k][-1][0]
def pitch(n, k, slot=0):
    ch=chord_at(k,slot)
    for p,_ in ch.tones:
        if p.midi%12 == n%12:
            from mxl import NAT
            return P(p.pc_name + str((n-NAT[p.step]-p.alter)//12-1))
    names=NAMES_SHARP if section(k)[3] in ('C#m','F#m','F#','Em') else NAMES_FLAT
    return P(names[n%12]+str(n//12-1))
def ev(n,d,role,src=None,ly='',velocity=64,**kw):
    return dict(p=n,d=d,ly=ly,role=role,source=src,velocity=velocity,**kw)
def rest(d=12): return ev(None,d,'rest')
def imported(tr,k,role):
    return [ev(e.pitches[0].midi if e.pitches else None,e.dur,role,
               {'file':role+'.txt','key':k},tie_start=e.tie,
               spelling=repr(e.pitches[0]) if e.pitches else None)
            for e in tr.get(k,[Ev(12)])]
def pc_weights(stem,a,z,lo=40,hi=92):
    x=RAW[stem]
    overlap=np.maximum(0,np.minimum(x[:,1],z)-np.maximum(x[:,0],a))
    ix=(overlap>0)&(x[:,2]>=lo)&(x[:,2]<=hi)
    w={}
    for row,o in zip(x[ix],overlap[ix]):
        p=int(row[2]);w[p]=w.get(p,0)+float(o*row[3])
    return w
def at_note(bar,slot):
    p=0
    for e in bar:
        if p <= slot < p+e['d']: return e['p']
        p+=e['d']
def octave_place(n,part,target):
    lo,hi=RANGES[part]
    opts=[p for p in range(lo,hi+1) if p%12==n%12]
    return min(opts,key=lambda p:abs(p-target)+.2*abs(p-n))

SCORE={p:{} for p in PARTS}
for k in KEYS:
    SCORE['Lead'][k]=imported(LEAD,k,'lead')
    SCORE['Bass'][k]=imported(BASS,k,'bass')
    SCORE['Whistle'][k]=imported(WH,k,'flute') if 47<=k<=62 else [rest()]
    for e in SCORE['Bass'][k]:
        if e['p'] is not None:
            e['p']=octave_place(e['p'],'Bass',e['p']);e['ly']='dm' if 47<=k<133 else 'dum'
    # The entire flute line is lowered by one octave for a practical human whistle.
    # Contour and pitch classes are retained; there are no piano notes in this part.
    for e in SCORE['Whistle'][k]:
        if e['p'] is not None:
            e['source']['original_midi']=e['p'];e['p']-=12;e.pop('spelling',None)

# Source-supported half-bar chord voicings. Thirds, suspensions and added notes receive
# priority over duplicated roots/fifths, including under a moving piano line.
VOICINGS={}; prev=None; prev_b=None
for k in KEYS:
    for slot in (0,6):
        ch=chord_at(k,slot);bp=place_bass(ch.bass,prev_b)
        t,a,s=voice_upper(ch,bp,prev,dict(S=72,A=65,T=57))
        VOICINGS[k,slot]={'Soprano':s.midi,'Alto':a.midi,'Tenor':t.midi}
        prev=(t,a,s);prev_b=bp

# Retain the source piano's note attacks and pitch choices. Notes are not replaced
# with the nearest chord tone. Eighth-grid reduction removes short separation artefacts.
PIANO={}; piano_audit=[]
for k in KEYS:
    a,z=tim(k),tim(k,12);x=RAW['piano']; dur=z-a
    rows=x[(x[:,0]>=a-.055)&(x[:,0]<z-.055)&(x[:,2]>=48)&(x[:,2]<=89)&(x[:,3]>=.32)&((x[:,1]-x[:,0])>=.09)]
    slots={s:[] for s in range(0,12,2)}
    for s,e,n,amp in rows:
        slot=int(np.clip(2*round((s-a)/dur*6),0,10))
        # A soft vocal component in the piano stem is not a piano fill.
        vw=pc_weights('vocals',float(s),float(min(e,s+.24)),int(n),int(n)).get(int(n),0)
        pw=float(min(e-s,.24)*amp)
        if k>=79 and vw>1.6*pw and amp<.52: continue
        slots[slot].append(dict(p=int(n),start=float(s),end=float(e),amp=float(amp)))
    PIANO[k]=slots

# Background-vocal extraction: select sustained non-lead pitches in the vocal stem,
# with voice-leading regularization. Harmonic/octave traces of the lead are rejected.
BG={}; bg_audit=[]; prevbg={'Alto':65,'Tenor':55}
for k in KEYS:
    enabled=(29<=k<=46 or 79<=k<=141 or 165<=k<=194)
    for slot in (0,6):
        ch=chord_at(k,slot);lead=at_note(SCORE['Lead'][k],slot+2)
        a,z=tim(k,slot+.5),tim(k,slot+5.5)
        weights=pc_weights('vocals',a,z,48,79) if enabled else {}
        used=[]
        for part in ('Alto','Tenor'):
            cand=[]
            for n,w in weights.items():
                if w<.035: continue
                if lead is not None and (n==lead or n-lead in (12,19,24,28)):continue
                if lead is not None and n%12==lead%12: continue
                p=octave_place(n,part,prevbg[part])
                if p%12 in used: continue
                in_chord=ch.role_of_pc(p%12) is not None
                if not in_chord and w<.22: continue
                sc=w/(z-a)+(.12 if in_chord else -.16)-.017*abs(p-prevbg[part])
                # prefer fundamentals directly represented in this register
                sc-=.07*abs(p-n)/12
                cand.append((sc,p,n,w))
            if cand:
                sc,p,n,w=max(cand)
            else:sc=-999
            if sc>=.13:
                item=dict(p=p,role='vocal_backing',source=dict(stem='vocals',original_midi=n,
                          start=a,end=z,weight=w,confidence='medium'),velocity=59)
                used.append(p%12);prevbg[part]=p
            else:
                item=dict(p=VOICINGS[k,slot][part],role='harmonic_support',source=dict(
                    chord=ch.sym,confidence='editorial'),velocity=53)
            BG[k,slot,part]=item
            if enabled:bg_audit.append(dict(bar=k-3,slot=slot,part=part,**item))

def sparse_line(k,part,source_role='piano',occupied=None):
    """A monophonic line from onset candidates; a rest remains if the source is sparse."""
    target={'Soprano':74,'Alto':65,'Tenor':57}[part]
    attacks=[];prev=target
    for slot,notes in PIANO[k].items():
        opts=[]
        for n in notes:
            # Preserve the source register wherever singable. A previous high note
            # must not pull a later low note up an octave and reverse the contour.
            lo,hi=RANGES[part]
            p=min((x for x in range(lo,hi+1) if x%12==n['p']%12),key=lambda x:abs(x-n['p'])+.05*abs(x-prev))
            if occupied and p%12==occupied.get(slot//6*6,-99)%12:continue
            # upper voice follows the original RH top line; tenor follows inner/LH pitches.
            reg=.018*abs(n['p']-({'Soprano':75,'Alto':67,'Tenor':57}[part]))
            sc=n['amp']-reg-.013*abs(p-prev)
            if part=='Soprano':sc+=.016*(n['p']-65)
            if part=='Tenor' and n['p']>72:sc-=.35
            opts.append((sc,p,n))
        if not opts:continue
        sc,p,n=max(opts,key=lambda x:x[0])
        if sc<-.08:continue
        attacks.append((slot,p,n));prev=p
    out=[];pos=0
    for i,(slot,p,n) in enumerate(attacks):
        if slot>pos:out.append(rest(slot-pos))
        end=attacks[i+1][0] if i+1<len(attacks) else 12
        source_len=(n['end']-n['start'])/(tim(k,12)-tim(k))*12
        # Let genuine longer piano notes ring, but leave articulation and breathing space.
        nd=min(end-slot,max(2,int(2*round(source_len/2))))
        if nd<2:continue
        out.append(ev(p,nd,'piano',dict(stem='piano',original_midi=n['p'],
            start=n['start'],end=n['end'],confidence='medium'),ly='du',
            velocity=int(48+30*n['amp']),accent=slot in (0,6)))
        piano_audit.append(dict(bar=k-3,part=part,slot=slot,midi=p,original_midi=n['p'],
                            source_start=n['start'],source_end=n['end'],amplitude=n['amp']))
        pos=slot+nd
    if pos<12:out.append(rest(12-pos))
    return out or [rest()]

def pad(k,part,from_vocals=False,breath=False):
    out=[]
    for slot in (0,6):
        item=BG[k,slot,part] if from_vocals and part in ('Alto','Tenor') else dict(
            p=VOICINGS[k,slot][part],role='string_pad',source=dict(chord=chord_at(k,slot).sym,
            confidence='editorial'),velocity=52)
        e=ev(item['p'],6,item['role'],item['source'],'ah' if from_vocals else 'oo',item['velocity'])
        if out and out[-1]['p']==e['p'] and out[-1]['role']==e['role']:
            out[-1]['d']+=6
        else:out.append(e)
    if breath:
        out[-1]['d']-=2;out.append(rest(2))
    return out

for k in KEYS:
    style=section(k)[4]
    if style in ('verse','verse2','verse3'):
        SCORE['Soprano'][k]=sparse_line(k,'Soprano')
        SCORE['Alto'][k]=pad(k,'Alto',breath=k%4==0)
        SCORE['Tenor'][k]=sparse_line(k,'Tenor')
    elif style in ('vocalise','bridge'):
        SCORE['Alto'][k]=pad(k,'Alto',True,breath=k%4==0)
        SCORE['Tenor'][k]=pad(k,'Tenor',True,breath=k%4==2)
        SCORE['Soprano'][k]=sparse_line(k,'Soprano')
        if all(e['p'] is None for e in SCORE['Soprano'][k]):
            SCORE['Soprano'][k]=pad(k,'Soprano',breath=k%4==1)
    elif style in ('chorus1','chorus2','chorus3'):
        SCORE['Soprano'][k]=pad(k,'Soprano',breath=k%4==1)
        SCORE['Alto'][k]=sparse_line(k,'Alto')
        SCORE['Tenor'][k]=pad(k,'Tenor',True,breath=k%4==3)
        if all(e['p'] is None for e in SCORE['Alto'][k]):
            SCORE['Alto'][k]=pad(k,'Alto',True,breath=k%4==0)
    elif style=='flute':
        SCORE['Soprano'][k]=pad(k,'Soprano',breath=k%4==1)
        SCORE['Alto'][k]=sparse_line(k,'Alto')
        SCORE['Tenor'][k]=sparse_line(k,'Tenor')
    else:
        SCORE['Soprano'][k]=sparse_line(k,'Soprano')
        SCORE['Alto'][k]=pad(k,'Alto',breath=k%4==1)
        SCORE['Tenor'][k]=sparse_line(k,'Tenor')

# Piano prologue and epilogue themes stay in the choir, with octave reduction only.
# Their exposed note order was manually transcribed in the reference project.
for k in list(range(4,12))+list(range(195,202)):
    SCORE['Soprano'][k]=imported(WH,k,'piano_theme')
    for e in SCORE['Soprano'][k]:
        if e['p'] is not None:
            original=e['p'];e['p']-=12;e['source'].update(original_midi=original,origin='piano; reference whistle reassigned')
            e['ly']='lu';e['velocity']=71;e.pop('spelling',None)
    if k<12:
        # Roll only the introductory chord. Upper melody remains a separate singer.
        for part,delay in [('Tenor',1),('Alto',2)]:
            n=VOICINGS[k,0][part]
            SCORE[part][k]=[rest(delay),ev(n,10-delay,'piano_roll',{'chord':CH[k][0][0].sym},'mm',54),rest(2)]
    elif k>=198:
        # F# add9: preserve A# and G#, not a bare F# major chord.
        SCORE['Soprano'][k]=[ev(70,12,'piano_resonance',{'chord':'F#add9'},'mm',48)]
        SCORE['Alto'][k]=[ev(68,12,'piano_resonance',{'chord':'F#add9'},'mm',45)]
        SCORE['Tenor'][k]=[ev(61,12,'piano_resonance',{'chord':'F#add9'},'mm',44)]
        SCORE['Bass'][k]=[ev(42,12,'piano_resonance',{'chord':'F#add9'},'mm',48)]

# The low F in the opening theme must remain F4. Revoice the other singers below
# it rather than displacing that melody note to F5 to enforce choir ordering.
SCORE['Alto'][8]=[rest(2),ev(60,8,'piano_roll',{'chord':'Fmadd9'},'mm',54),rest(2)]
SCORE['Tenor'][8]=[rest(1),ev(56,9,'piano_roll',{'chord':'Fmadd9'},'mm',54),rest(2)]
SCORE['Bass'][8]=[ev(41,12,'bass',{'file':'bass.txt','key':8,'octave_reduction':True},'dum',60)]

# The returning instrumental line belongs to the voice ensemble, not the whistle.
BREAK = parse('A4:10 F4:2 | G4:2 A4:2 G4:4 F4:3 D4:1 | F4:4 Bb4:2 C5:2 D5:4 | Bb4:2 A4:2 G4:4 G4:4 | A4:4 A4:4 D5:2 F4:2 | G4:2 F4:2 Eb4:2 D4:2 C4:2 Eb4:2 | C4:6 Db4:6')
for k,bar in zip(range(142,149),BREAK):
    SCORE['Alto'][k]=[ev(e.pitches[0].midi,e.dur,'instrumental_counterline',{'reference':'claude A_BREAK'},'lu',64) for e in bar]
    SCORE['Soprano'][k]=pad(k,'Soprano',breath=k%4==1)

# VP: one articulated mouth sound at a time. Two dotted-quarter pulses, phrase-level
# variations, inhaled hats and short fills. Sparse original sections remain sparse.
# Actual drum-flux grids guide the extra kicks; they are not blindly read as scores.
DG={}
for fn in ('drumgrid_62_101.txt','drumgrid_101_201.txt'):
    path=REF/fn
    if path.exists():
        for line in path.read_text().splitlines():
            k,body=line.split('|',1);DG[int(k)]=body.replace('|',' ').split()
VP_INFO={}
for k in KEYS:
    hits={};pattern='silence';strength=58
    if k==11:
        hits={8:49};pattern='breathy cymbal lead-in';strength=35
    elif k in (44,70):
        hits={6:42,8:42,10:46};pattern='pickup hats';strength=42
    elif 45<=k<=62 or 79<=k<=132:
        strength=66 if k>=79 else 59
        hits={0:36,2:42,4:42,6:38,8:42,10:42}
        pattern='two-pulse groove A'
        if k%2==0:hits[10]=36;pattern='two-pulse groove B'
        if k in DG:
            for s in (3,4,9,10):
                if 'K' in DG[k][s] and (s%2==0 or k%4==2):hits[s]=36
        if k in (47,55,79,87,97,101,109,117,125):
            hits[0]=49;hits[1]=36;pattern='section accent + kick'
        if k in (54,62,78,86,96,100,108,116,124,132):
            # Different endings, no simultaneous kick/snare/hat demands.
            fills={0:{8:37,9:38,10:36},1:{8:42,9:37,10:38},2:{8:38,9:37,10:45},3:{8:37,9:45,10:36}}
            hits.update(fills[(k//2)%4]);hits.pop(11,None);pattern='phrase fill; breathe on last 16th'
        if k==132:hits={0:36,2:42,4:42,6:38,8:37,9:45,10:36};pattern='last fill then tacet'
    elif 71<=k<=78:
        strength=46;hits={0:36,2:42,4:42,6:37,8:42}
        if k%2==1:hits[10]=36
        pattern='light verse rim groove'
        if k==78:hits.update({8:37,9:38,10:36});pattern='chorus pickup'
    elif 157<=k<=164:
        strength=34;hits={0:42,2:42,4:42,6:42,8:42,10:42};pattern='inhaled hats only'
        if k%4==0:hits.pop(10)
    elif 165<=k<=176:
        strength=46;hits={0:36,2:42,4:42,6:37,8:42,10:42};pattern='light reprise'
        if k%2==0:hits[10]=36
        if k==165:hits[0]=49;hits[1]=36
        if k==176:hits[9]=37;hits[10]=46
    elif 177<=k<=183:
        strength=35;hits={0:42,2:42,4:42,6:42,8:42};pattern='withdrawal hats'
        if k<=180:hits[10]=42
    syl={36:'B',37:'ka',38:'pf',42:'t',46:'ts',49:'ksh',45:'dm'}
    out=[];pos=0
    for slot,n in sorted(hits.items()):
        if slot>pos:out.append(rest(slot-pos))
        d=1 # explicit spaces between sounds; breathable single-performer VP
        out.append(ev(n,d,'vp_design',{'pattern':pattern,'raw_drum_grid':DG.get(k)},syl[n],
                      strength+(7 if n in (36,38,49) else -8),accent=slot in (0,6)))
        pos=slot+d
    if pos<12:out.append(rest(12-pos))
    SCORE['VP'][k]=out
    VP_INFO[k]=pattern

# Keep the harmonic colour in the notes, not merely in printed chord symbols.
# Only editorial support notes are eligible; transcribed piano, bass, lead and vocal
# counterlines retain their pitch classes. Re-score each half-bar after orchestration.
colour_repairs=[]
for k in KEYS:
    for slot in (0,6):
        ch=chord_at(k,slot)
        weights={}
        for part in ('Lead','Soprano','Alto','Tenor','Bass'):
            for tick in range(slot,slot+6):
                n=at_note(SCORE[part][k],tick)
                if n is not None:weights[n%12]=weights.get(n%12,0)+1
        importance={'3':12,'4':14,'7':11,'6':10,'9':9}
        missing=[(importance[role],tone.midi%12,role) for tone,role in ch.tones
                 if role in importance and weights.get(tone.midi%12,0)<2]
        if not missing:continue
        # Split generic sustained pads at the half-bar boundary before editing them.
        candidates=[]
        for part in ('Alto','Tenor','Soprano'):
            new=[];pos=0
            for e in SCORE[part][k]:
                edges=sorted({pos,pos+e['d']}|({slot,slot+6}&set(range(pos+1,pos+e['d']))))
                for x,y in zip(edges,edges[1:]):
                    e2=copy.deepcopy(e);e2['d']=y-x
                    new.append(e2)
                    if x>=slot and y<=slot+6 and e2['role'] in ('string_pad','harmonic_support'):
                        candidates.append((part,e2))
                pos+=e['d']
            SCORE[part][k]=new
        for _,pc,role in sorted(missing,reverse=True):
            viable=[]
            for i,(part,e) in enumerate(candidates):
                old_role=ch.role_of_pc(e['p']%12)
                # Never remove a unique required colour to replace it with another.
                if old_role in importance and weights.get(e['p']%12,0)<=e['d']:continue
                n=octave_place(pc,part,e['p'])
                viable.append((abs(n-e['p']),i,n))
            if not viable:continue
            _,ix,n=min(viable);part,e=candidates.pop(ix)
            colour_repairs.append(dict(bar=k-3,offset=slot/4,part=part,chord=ch.sym,role=role,old=e['p'],new=n))
            weights[e['p']%12]-=e['d'];weights[n%12]=weights.get(n%12,0)+e['d']
            e['p']=n;e['source']=dict(chord=ch.sym,confidence='editorial',reason='restore required colour '+role)

# Preserve pitch classes while assigning legal choir registers. Split at all SATB
# event boundaries to avoid accidental crossings when a moving line passes a pad.
register_changes=[]
for k in KEYS:
    names=['Soprano','Alto','Tenor','Bass'];grid={};prevpos={p:None for p in names}
    for p in names:
        cells=[]
        for e in SCORE[p][k]:
            for s in range(e['d']):cells.append((e,s==0))
        assert len(cells)==12,(k,p)
        grid[p]=cells
    new={p:[] for p in names};last_tuple=None
    for slot in range(12):
        orig={p:grid[p][slot][0]['p'] for p in names}
        opts=[]
        for p in names:
            n=orig[p]
            if n is None:opts.append([None]);continue
            lo,hi=RANGES[p]
            opts.append([x for x in range(lo,hi+1) if x%12==n%12])
        valid=[]
        for combo in itertools.product(*opts):
            vals=[n for n in combo if n is not None]
            if any(a<b for a,b in zip(vals,vals[1:])):continue
            cost=sum(abs(n-orig[p])*(12 if grid[p][slot][0]['role'] in ('piano_theme','instrumental_counterline') else
                                     5 if grid[p][slot][0]['role']=='piano' else 1)
                     +(.25*abs(n-prevpos[p]) if prevpos[p] is not None else 0)
                     for p,n in zip(names,combo) if n is not None)
            valid.append((cost,combo))
        if not valid:raise ValueError(('unplaceable choir',k,slot,orig))
        combo=min(valid,key=lambda a:a[0])[1]
        for p,n in zip(names,combo):
            e,onset=grid[p][slot];x=copy.deepcopy(e);x['p']=n;x['d']=1
            if n!=orig[p]:
                x.pop('spelling',None);x['register_shift']=n-orig[p]
                if onset:register_changes.append(dict(bar=k-3,slot=slot,part=p,old=orig[p],new=n))
            if new[p] and not onset and new[p][-1]['p']==n:new[p][-1]['d']+=1
            else:
                if not onset:x['ly']='';x.pop('tie_start',None)
                new[p].append(x)
            if n is not None:prevpos[p]=n
        last_tuple=combo
    for p in names:SCORE[p][k]=new[p]

# Stagger short breaths without deleting any pitch attack. Long source note releases
# are shortened by 1-2 sixteenths, and logged, so single singers can execute the score.
breaths=[]
for part in ('Lead','Soprano','Alto','Tenor','Bass'):
    run=0
    for k in KEYS:
        bar=SCORE[part][k]
        for e in bar:
            run=run+e['d']/12*(tim(k,12)-tim(k)) if e['p'] is not None else 0
        limit=7.8 if part=='Lead' else 5.5 if part=='Bass' else 7.0
        if run<=limit:continue
        candidates=[j for j,e in enumerate(bar) if e['p'] is not None and e['d']>=3]
        if not candidates:continue
        j=candidates[-1];e=bar[j];cut=2 if e['d']>=4 else 1
        e['d']-=cut;e.pop('tie_start',None);e['breath_after']=True
        bar.insert(j+1,rest(cut));breaths.append(dict(bar=k-3,part=part,rest_quarters=cut/4))
        run=sum(e['d']/12*(tim(k,12)-tim(k)) for e in bar[j+2:] if e['p'] is not None)

# Replace unsupported cross-pitch ties; join genuinely continuous pads only.
for part in PARTS:
    for i,k in enumerate(KEYS):
        bar=SCORE[part][k]
        for j,e in enumerate(bar):
            nxt=bar[j+1] if j+1<len(bar) else SCORE[part][KEYS[i+1]][0] if i+1<len(KEYS) else None
            if e.get('tie_start') and (not nxt or nxt['p']!=e['p'] or e['p'] is None):e.pop('tie_start',None)
            if nxt and e['p'] is not None and e['p']==nxt['p'] and e['role']==nxt['role'] and e['role'] in ('vocal_backing','string_pad','harmonic_support','piano_resonance'):
                if j+1<len(bar) or (k%3!=0 and k<198):e['tie_start']=True
            if e.get('tie_start'):nxt['tie_stop']=True;nxt['ly']=''
    if part in ('Soprano','Alto','Tenor','Bass'):
        # Alternate breaths in the sustained ending; these are singer breaths,
        # never rearticulated piano harmonies in the whistle.
        for k in (198,199,200,201):
            bar=SCORE[part][k]
            if len(bar)==1 and bar[0]['p'] is not None:
                bar[0].pop('tie_stop',None);bar[0].pop('tie_start',None)
                if k<201:
                    d=10 if (k+PARTS.index(part))%2 else 11
                    bar[0]['d']=d;bar.append(rest(12-d))

for part in PARTS:
    flat=[e for k in KEYS for e in SCORE[part][k]]
    for e in flat:e.pop('tie_stop',None)
    for e,nxt in zip(flat,flat[1:]):
        if e.get('tie_start') and e['p'] is not None and nxt['p']==e['p']:
            nxt['tie_stop']=True;nxt['ly']=''
        else:e.pop('tie_start',None)
    flat[-1].pop('tie_start',None)

meta=[]
for i,k in enumerate(KEYS):
    st,mark,label,key,style,dyn=section(k)
    if 129<=k<142:key='Gm'
    if k>=198:dyn='pp'
    p=0;hs=[]
    for ch,d in CH[k]:hs.append(dict(symbol=ch.sym,offset=p/4,duration=d/4));p+=d
    meta.append(dict(bar=i+1,reference_key=k,section=mark,label=label,key=key,style=style,
        local=k-st+1,dynamic=dyn,tempo=round(180/(BOUNDARIES[i+1]-BOUNDARIES[i]),5),
        source_time=BOUNDARIES[i],source_end=BOUNDARIES[i+1],chord=CH[k][0][0].sym,
        harmonies=hs,vp_pattern=VP_INFO[k]))

# Archive canonical event score with quarter-note durations, explicit evidence and timing.
canonical={p:[] for p in PARTS}
for p in PARTS:
    for k in KEYS:
        bar=copy.deepcopy(SCORE[p][k])
        assert sum(e['d'] for e in bar)==12,(p,k,bar)
        for e in bar:e['d']/=4
        canonical[p].append(bar)
data=dict(title='everytime you kissed me',version='3.0',parts=PARTS,metadata=meta,score=canonical,
    ranges={p:[min(e['p'] for b in canonical[p] for e in b if e['p'] is not None),
               max(e['p'] for b in canonical[p] for e in b if e['p'] is not None)] for p in PARTS if p!='VP'},
    source_sha256=hashlib.sha256((PROJECT/'input/EYKM.flac').read_bytes()).hexdigest(),
    human_listening_review=False,reference='Claude v2 transcription + original separated-note evidence; newly orchestrated SATB/VP',
    whistle_rule='Only reference keys 47-62 (score 44-59), original flute line down one octave')
# Preserve the existing authorized lyric underlay by source time. The DP maintains
# syllable order and assigns at most one old syllable to each new note attack.
old=json.loads((PROJECT/'outputs/EYKM_Acappella_v2/source/arrangement.json').read_text())
syllables=[];attacks=[]
for i,bar in enumerate(old['score']['Lead']):
    pos=0;m=old['metadata'][i]
    for e in bar:
        if e.get('ly') and e['ly'] not in ('ah','oo','mm'):
            syllables.append((m['source_time']+pos/3*(m['source_end']-m['source_time']),e['ly']))
        pos+=e['d']
lead_cells=[]
for i,bar in enumerate(data['score']['Lead']):
    pos=0;m=meta[i];cells=[]
    for j,e in enumerate(bar):
        for tick in range(round(e['d']*4)):
            cells.append((copy.deepcopy(e),tick==0))
            if e['p'] is not None:
                attacks.append((m['source_time']+(pos+tick/4)/3*(m['source_end']-m['source_time']),i,len(cells)-1,tick==0 and not e.get('tie_stop')))
        pos+=e['d']
    lead_cells.append(cells)
n,m=len(syllables),len(attacks);dp=np.full((n+1,m+1),1e9);back=np.zeros((n+1,m+1),np.int8)
dp[0,:]=0
for i in range(1,n+1):
    dp[i,0]=3*i;back[i,0]=2
    for j in range(1,m+1):
        dt=abs(syllables[i-1][0]-attacks[j-1][0]);match=dp[i-1,j-1]+dt+(.05 if not attacks[j-1][3] else 0) if dt<.85 else 1e9
        choices=[dp[i,j-1],match,dp[i-1,j]+3]
        back[i,j]=int(np.argmin(choices));dp[i,j]=min(choices)
i,j=n,m;matched=[];unmatched=[];assignments={}
while i>0:
    op=int(back[i,j]) if j else 2
    if op==0:j-=1
    elif op==1:
        t,bi,ei,onset=attacks[j-1];text=syllables[i-1][1]
        assignments[bi,ei]=text
        matched.append(dict(bar=bi+1,syllable=text,time=t,old_time=syllables[i-1][0]))
        i-=1;j-=1
    else:unmatched.append(dict(time=syllables[i-1][0],syllable=syllables[i-1][1]));i-=1
for bi,cells in enumerate(lead_cells):
    out=[]
    for slot,(e,onset) in enumerate(cells):
        lyric=assignments.get((bi,slot),'')
        e['d']=.25;e['ly']=lyric
        if lyric:
            e.pop('tie_stop',None)
            if out:out[-1].pop('tie_start',None)
            elif bi and data['score']['Lead'][bi-1]:data['score']['Lead'][bi-1][-1].pop('tie_start',None)
        if out and not onset and not lyric and out[-1]['p']==e['p']:
            out[-1]['d']+=.25
        else:
            if not onset:e.pop('tie_stop',None)
            out.append(e)
    data['score']['Lead'][bi]=out
for bi,bar in enumerate(data['score']['Lead']):
    SCORE['Lead'][KEYS[bi]]=copy.deepcopy(bar)
    for e in SCORE['Lead'][KEYS[bi]]:e['d']=round(e['d']*4)
data['lyric_underlay']=dict(matched=len(matched),unmatched=len(unmatched),method='monotone source-time alignment; singer review required')
(ANALYSIS/'lyric_underlay.json').write_text(json.dumps(dict(matched=matched[::-1],unmatched=unmatched[::-1]),ensure_ascii=False,indent=2))
(ROOT/'source/arrangement.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
(ANALYSIS/'colour_repairs.json').write_text(json.dumps(colour_repairs,indent=2))
(ANALYSIS/'breath_edits.json').write_text(json.dumps(breaths,indent=2))
(ANALYSIS/'background_decisions.json').write_text(json.dumps(bg_audit,ensure_ascii=False,indent=2))
(ANALYSIS/'register_changes.json').write_text(json.dumps(register_changes,indent=2))
with (ANALYSIS/'piano_assignments.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(piano_audit[0]));w.writeheader();w.writerows(piano_audit)

fifths={'Cm':-3,'Fm':-4,'Dm':-1,'Gm':-2,'Em':1,'C#m':4,'F#m':3,'F#':6}
clefs={'Tenor':'<clef><sign>G</sign><line>2</line><clef-octave-change>-1</clef-octave-change></clef>',
       'Bass':'<clef><sign>F</sign><line>4</line></clef>',
       'VP':'<clef><sign>percussion</sign></clef>'}
drumcodes={36:'K',37:'k',38:'S',42:'h',46:'o',49:'C',45:'t'}
import mxl
mxl.DRUMMAP['t']=('A',4,None,'I46',45,'Low tom / vocal dm')
specs=[]
for ip,p in enumerate(PARTS):
    spec=PartSpec(f'P{ip+1}',p,{'Soprano':'S.','Alto':'A.','Tenor':'T.','Bass':'B.','Lead':'Ld.','Whistle':'Wh.','VP':'VP'}[p],
        clefs.get(p,'<clef><sign>G</sign><line>2</line></clef>'),program=74 if p=='Whistle' else 1,
        drums=p=='VP',sound='wind.flutes.flute' if p=='Whistle' else 'keyboard.piano')
    for k in KEYS:
        bar=[];slot=0
        for e in SCORE[p][k]:
            ps=[P(e['spelling']) if e.get('spelling') and P(e['spelling']).midi==e['p'] else pitch(e['p'],k,slot)] if e['p'] is not None and p!='VP' else []
            e2=Ev(e['d'],ps,[drumcodes[e['p']]] if p=='VP' and e['p'] is not None else [],
                  bool(e.get('tie_start')),e.get('ly'),accent=bool(e.get('accent')))
            if slot==0 and section(k)[0]==k:
                e2.dirs=[('dyn',meta[k-FIRST]['dynamic'])]
                if p=='VP':e2.dirs.append(('words',VP_INFO[k]))
                if p=='Whistle':e2.dirs.append(('words','Flute line only; sounding one octave below source' if k==47 else 'tacet'))
            bar.append(e2);slot+=e['d']
        spec.bars.append(bar)
    specs.append(spec)
finalize(specs)
mxmeta=[];prevkey=None;prevtempo=None
for m in meta:
    x={}
    if m['key']!=prevkey:x['key']=(fifths[m['key']],'major' if m['key']=='F#' else 'minor');prevkey=m['key']
    if m['local']==1:x.update(mark=m['section'],section=m['label'])
    bpm=round(m['tempo'],4)
    if bpm!=prevtempo:x['tempo']=bpm;prevtempo=bpm
    mxmeta.append(x)
mxmeta[-1]['barline']='light-heavy'
harm=[[(Chord(h['symbol']),int(h['offset']*4)) for h in m['harmonies']] for m in meta]
TITLE=('everytime you kissed me','v3 - Lead + SATB + VP + Whistle','Yuki Kajiura','Student ensemble arrangement v3')
write_score(ROOT/'scores/EYKM_v3_Full_Score.musicxml',*TITLE,specs,mxmeta,harm,specs[0])
for p,spec in zip(PARTS,specs):
    write_score(ROOT/f'parts/EYKM_v3_{p}.musicxml',*TITLE,[spec],mxmeta,harm,spec)
print('Built v3:',len(meta),'bars;',data['ranges'])
print('Piano assignments:',len(piano_audit),'source-backed background choices:',sum(x['role']=='vocal_backing' for x in bg_audit))
