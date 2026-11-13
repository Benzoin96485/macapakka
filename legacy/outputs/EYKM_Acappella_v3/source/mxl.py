"""Small MusicXML toolkit for the a cappella arrangement (3/4, 16th-note grid)."""
import itertools, re
from xml.sax.saxutils import escape

LETTERS = 'CDEFGAB'
NAT = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
BAR = 12  # 16ths per 3/4 bar


class Pitch:
    __slots__ = ('step', 'alter', 'octave')

    def __init__(self, step, alter, octave):
        self.step, self.alter, self.octave = step, alter, octave

    @property
    def midi(self):
        return 12 * (self.octave + 1) + NAT[self.step] + self.alter

    @property
    def pc_name(self):
        return self.step + {-2: 'bb', -1: 'b', 0: '', 1: '#', 2: 'x'}[self.alter]

    def transpose(self, steps, semis):
        li = LETTERS.index(self.step) + steps
        octave = self.octave + li // 7
        step = LETTERS[li % 7]
        base = 12 * (octave + 1) + NAT[step]
        return Pitch(step, self.midi + semis - base, octave)

    def with_octave(self, octave):
        return Pitch(self.step, self.alter, octave)

    def __eq__(self, o):
        return isinstance(o, Pitch) and (self.step, self.alter, self.octave) == (o.step, o.alter, o.octave)

    def __hash__(self):
        return hash((self.step, self.alter, self.octave))

    def __repr__(self):
        return f'{self.pc_name}{self.octave}'


_PRE = re.compile(r'^([A-G])(bb|b|#|x)?(-?\d)$')


def P(name):
    m = _PRE.match(name)
    if not m:
        raise ValueError(f'bad pitch {name!r}')
    alter = {None: 0, 'b': -1, 'bb': -2, '#': 1, 'x': 2}[m.group(2)]
    return Pitch(m.group(1), alter, int(m.group(3)))


class Ev:
    """One rhythmic event inside a bar."""
    __slots__ = ('dur', 'pitches', 'drums', 'tie', 'lyric', 'dirs', 'fermata', 'accent', 'tied_in', 'beams')

    def __init__(self, dur, pitches=None, drums=None, tie=False, lyric=None, dirs=None,
                 fermata=False, accent=False):
        self.dur = dur
        self.pitches = pitches or []
        self.drums = drums or []
        self.tie = tie
        self.lyric = lyric
        self.dirs = dirs or []
        self.fermata = fermata
        self.accent = accent
        self.tied_in = False
        self.beams = None

    @property
    def is_rest(self):
        return not self.pitches and not self.drums


# ---------------------------------------------------------------- token parser
# bars separated by '|'; tokens: Eb4:2  Eb4:2~  r:4  R (whole-bar rest)  C4+Eb4:4
# suffixes: @syl (lyric), ^ (fermata), > (accent);  '!p' '!<' '!>' '!/' '!t=text' attach to next event
DRUMS = set('KSkhoCx')


def parse(text, drums=False):
    bars = []
    for raw in text.split('|'):
        raw = raw.strip()
        if not raw:
            continue
        evs, pending = [], []
        for tok in raw.split():
            if tok.startswith('!'):
                pending.append(_dir(tok[1:]))
                continue
            if tok == 'R':
                evs.append(Ev(BAR, dirs=pending)); pending = []
                continue
            lyric = None
            if '@' in tok:
                tok, lyric = tok.split('@', 1)
                lyric = lyric.replace('_', ' ')
            ferm = tok.endswith('^')
            tok = tok.rstrip('^')
            acc = tok.endswith('>')
            tok = tok.rstrip('>')
            tie = tok.endswith('~')
            tok = tok.rstrip('~')
            body, dur = tok.rsplit(':', 1)
            dur = int(dur)
            if body == 'r':
                ev = Ev(dur)
            elif drums:
                ev = Ev(dur, drums=body.split('+'))
            else:
                ev = Ev(dur, pitches=[P(x) for x in body.split('+')])
            ev.tie, ev.lyric, ev.dirs, ev.fermata, ev.accent = tie, lyric, pending, ferm, acc
            pending = []
            evs.append(ev)
        tot = sum(e.dur for e in evs)
        if tot != BAR:
            raise ValueError(f'bar sums to {tot}: {raw!r}')
        if pending:  # trailing directions -> attach to last event
            evs[-1].dirs += pending
        bars.append(evs)
    return bars


def _dir(s):
    if s in ('<', '>', '/'):
        return ('wedge', {'<': 'crescendo', '>': 'diminuendo', '/': 'stop'}[s])
    if s.startswith('t='):
        return ('words', s[2:].replace('_', ' '))
    if s.startswith('b='):
        return ('wordsb', s[2:].replace('_', ' '))
    return ('dyn', s)


def transpose_bars(bars, steps, semis):
    out = []
    for bar in bars:
        nb = []
        for e in bar:
            ne = Ev(e.dur, [p.transpose(steps, semis) for p in e.pitches], list(e.drums), e.tie,
                    e.lyric, list(e.dirs), e.fermata, e.accent)
            nb.append(ne)
        out.append(nb)
    return out


# ---------------------------------------------------------------- chords
Q = {
    '':      [(0, 0, 'R'), (2, 4, '3'), (4, 7, '5')],
    'm':     [(0, 0, 'R'), (2, 3, '3'), (4, 7, '5')],
    '7':     [(0, 0, 'R'), (2, 4, '3'), (4, 7, '5'), (6, 10, '7')],
    'm7':    [(0, 0, 'R'), (2, 3, '3'), (4, 7, '5'), (6, 10, '7')],
    'maj7':  [(0, 0, 'R'), (2, 4, '3'), (4, 7, '5'), (6, 11, '7')],
    'sus4':  [(0, 0, 'R'), (3, 5, '4'), (4, 7, '5')],
    'sus2':  [(0, 0, 'R'), (1, 2, '9'), (4, 7, '5')],
    'add9':  [(0, 0, 'R'), (2, 4, '3'), (4, 7, '5'), (1, 2, '9')],
    'madd9': [(0, 0, 'R'), (2, 3, '3'), (4, 7, '5'), (1, 2, '9')],
    '7sus4': [(0, 0, 'R'), (3, 5, '4'), (4, 7, '5'), (6, 10, '7')],
    '6':     [(0, 0, 'R'), (2, 4, '3'), (4, 7, '5'), (5, 9, '6')],
    'm6':    [(0, 0, 'R'), (2, 3, '3'), (4, 7, '5'), (5, 9, '6')],
    '5':     [(0, 0, 'R'), (4, 7, '5')],
    '7no3':  [(0, 0, 'R'), (4, 7, '5'), (6, 10, '7')],
    'm9':    [(0, 0, 'R'), (2, 3, '3'), (4, 7, '5'), (6, 10, '7'), (1, 2, '9')],
    'maj9':  [(0, 0, 'R'), (2, 4, '3'), (4, 7, '5'), (6, 11, '7'), (1, 2, '9')],
    '69':    [(0, 0, 'R'), (2, 4, '3'), (4, 7, '5'), (5, 9, '6'), (1, 2, '9')],
    'sus4add9': [(0, 0, 'R'), (3, 5, '4'), (4, 7, '5'), (1, 2, '9')],
    'aug':   [(0, 0, 'R'), (2, 4, '3'), (4, 8, '5')],
    'm7b5':  [(0, 0, 'R'), (2, 3, '3'), (4, 6, '5'), (6, 10, '7')],
    'maj7#5': [(0, 0, 'R'), (2, 4, '3'), (4, 8, '5'), (6, 11, '7')],
}
REQUIRED = {'3': 30, '4': 30, '7': 16, '6': 12, '9': 6}
_CRE = re.compile(r'^([A-G](?:b|#)?)([a-z0-9]*)(?:/([A-G](?:b|#)?))?$')


class Chord:
    def __init__(self, sym):
        m = _CRE.match(sym)
        if not m:
            raise ValueError(sym)
        self.sym = sym
        self.root = P(m.group(1) + '4')
        self.qual = m.group(2)
        if self.qual not in Q:
            raise ValueError(f'unknown quality {self.qual!r} in {sym}')
        self.tones = [(self.root.transpose(st, se), role) for st, se, role in Q[self.qual]]
        self.bass = P(m.group(3) + '4') if m.group(3) else self.root

    def role_of_pc(self, pc):
        for p, r in self.tones:
            if p.midi % 12 == pc:
                return r
        return None


RANGES = {'S': (60, 79), 'A': (55, 72), 'T': (48, 67), 'B': (38, 60)}


def _placements(pitch, lo, hi):
    out = []
    for octv in range(1, 7):
        q = pitch.with_octave(octv)
        if lo <= q.midi <= hi:
            out.append(q)
    return out


def voice_upper(chord, bass, prev, target, avoid=None):
    """Return (T, A, S) pitches for chord. prev: previous (T, A, S) or None. target: dict S/A/T midi."""
    cands = {v: [] for v in 'TAS'}
    for p, role in chord.tones:
        for v in 'TAS':
            lo, hi = RANGES[v]
            for q in _placements(p, lo, hi):
                cands[v].append((q, role))
    best, bestc = None, 1e9
    bass_role = chord.role_of_pc(bass.midi % 12)
    for (t, rt), (a, ra), (s, rs) in itertools.product(cands['T'], cands['A'], cands['S']):
        if not (bass.midi < t.midi < a.midi < s.midi):
            continue
        if s.midi - a.midi > 9 or a.midi - t.midi > 12:
            continue
        roles = [rt, ra, rs]
        have = set(roles) | {bass_role}
        c = 0.0
        for r, w in REQUIRED.items():
            if any(rr == r for _, rr in chord.tones) and r not in have:
                c += w
        if '5' not in have and any(rr == '5' for _, rr in chord.tones):
            c += 2
        # doubling
        pcs = [t.midi % 12, a.midi % 12, s.midi % 12]
        for i in range(3):
            for j in range(i + 1, 3):
                if pcs[i] == pcs[j]:
                    c += 6 if roles[i] in ('R', '5') else 14
        if bass_role in ('3', '7') and bass_role in roles:
            c += 12
        if a.midi - t.midi > 9:
            c += 2
        # register
        c += 0.15 * ((s.midi - target['S']) ** 2 + (a.midi - target['A']) ** 2 + 0.7 * (t.midi - target['T']) ** 2)
        if prev:
            pt, pa, ps = prev
            c += 0.8 * abs(t.midi - pt.midi) + 0.8 * abs(a.midi - pa.midi) + 1.0 * abs(s.midi - ps.midi)
            # parallels among upper voices
            pv = [pt, pa, ps]; cv = [t, a, s]
            for i in range(3):
                for j in range(i + 1, 3):
                    i0 = (pv[j].midi - pv[i].midi) % 12
                    i1 = (cv[j].midi - cv[i].midi) % 12
                    if i0 == i1 and i0 in (0, 7) and pv[i].midi != cv[i].midi:
                        c += 10
        if avoid:
            for q in (s, a):
                for x in avoid:
                    if abs(q.midi - x) in (1, 2) and q is s:
                        c += 1.5
        if c < bestc:
            bestc, best = c, (t, a, s)
    if best is None:
        raise RuntimeError(f'no voicing for {chord.sym}')
    return best


def place_bass(pitch, prev, lo=41, hi=53):
    opts = []
    for octv in range(1, 5):
        q = pitch.with_octave(octv)
        if 38 <= q.midi <= 60:
            opts.append(q)
    def cost(q):
        c = 0
        if q.midi < lo: c += (lo - q.midi) * 6
        if q.midi > hi: c += (q.midi - hi) * 3
        if prev is not None: c += abs(q.midi - prev.midi) * 0.8
        return c
    return min(opts, key=cost)


# ---------------------------------------------------------------- notation helpers
TYPES = {1: ('16th', 0), 2: ('eighth', 0), 3: ('eighth', 1), 4: ('quarter', 0), 6: ('quarter', 1),
         8: ('half', 0), 12: ('half', 1)}


def _allowed(p, L, rest):
    if p + L > BAR:
        return False
    if L == 12:
        return p == 0
    if L == 8:
        return p in (0, 4)
    if L == 6:
        return (not rest) and p in (0, 6)
    if L == 4:
        return p % 4 == 0 if rest else p % 2 == 0
    if L == 3:
        return p % 4 == 0 if rest else p % 4 in (0, 1)
    if L == 2:
        return p % 2 == 0
    return L == 1


def split(p, d, rest=False):
    segs = []
    while d > 0:
        for L in (12, 8, 6, 4, 3, 2, 1):
            if L <= d and _allowed(p, L, rest):
                segs.append(L); p += L; d -= L
                break
    return segs


DRUMMAP = {  # code: (display step, octave, notehead, instrument-id-suffix, midi, name)
    'K': ('F', 4, None, 'I36', 36, 'Kick'),
    'S': ('C', 5, None, 'I39', 38, 'Snare'),
    'k': ('C', 5, 'x', 'I38', 37, 'Rim / k'),
    'h': ('G', 5, 'x', 'I43', 42, 'Closed Hi-hat'),
    'o': ('G', 5, 'circle-x', 'I47', 46, 'Open Hi-hat'),
    'C': ('A', 5, 'x', 'I50', 49, 'Crash'),
}

DYNS = {'ppp', 'pp', 'p', 'mp', 'mf', 'f', 'ff', 'fff', 'sfz', 'fp'}

HARM_KIND = {
    '': ('major', ''), 'm': ('minor', 'm'), '7': ('dominant', '7'), 'm7': ('minor-seventh', 'm7'),
    'maj7': ('major-seventh', 'maj7'), 'sus4': ('suspended-fourth', 'sus4'),
    'sus2': ('suspended-second', 'sus2'), '6': ('major-sixth', '6'), 'm6': ('minor-sixth', 'm6'),
    '5': ('power', '5'), 'm9': ('minor-ninth', 'm9'), 'maj9': ('major-ninth', 'maj9'),
    'add9': ('major', 'add9', [('9', 0, 'add')]), 'madd9': ('minor', 'm(add9)', [('9', 0, 'add')]),
    '7sus4': ('suspended-fourth', '7sus4', [('7', 0, 'add')]),
    '7no3': ('dominant', '7(no3)', [('3', 0, 'subtract')]),
    '69': ('major-sixth', '6/9', [('9', 0, 'add')]),
    'sus4add9': ('suspended-fourth', 'sus4(add9)', [('9', 0, 'add')]),
    'aug': ('augmented', '+'), 'm7b5': ('half-diminished', 'm7b5'),
    'maj7#5': ('augmented-seventh', 'maj7#5'),
}


def harmony_xml(chord, offset=0):
    kind = HARM_KIND[chord.qual]
    x = ['<harmony print-frame="no">']
    r = chord.root
    x.append(f'<root><root-step>{r.step}</root-step>' + (f'<root-alter>{r.alter}</root-alter>' if r.alter else '') + '</root>')
    x.append(f'<kind text="{escape(kind[1])}">{kind[0]}</kind>')
    if chord.bass is not chord.root:
        b = chord.bass
        x.append(f'<bass><bass-step>{b.step}</bass-step>' + (f'<bass-alter>{b.alter}</bass-alter>' if b.alter else '') + '</bass>')
    for val, alt, typ in (kind[2] if len(kind) > 2 else []):
        x.append(f'<degree><degree-value>{val}</degree-value><degree-alter>{alt}</degree-alter><degree-type>{typ}</degree-type></degree>')
    if offset:
        x.append(f'<offset>{offset}</offset>')
    x.append('</harmony>')
    return ''.join(x)


class PartSpec:
    def __init__(self, pid, name, abbr, clef, program=None, drums=False, transpose_octave=0, sound=None):
        self.pid, self.name, self.abbr, self.clef = pid, name, abbr, clef
        self.sound = sound
        self.program, self.drums = program, drums
        self.bars = []
        self.note_dyn = None


def _dir_xml(d, placement='above'):
    kind, val = d
    if kind == 'dyn':
        if val in DYNS:
            return f'<direction placement="{placement}"><direction-type><dynamics><{val}/></dynamics></direction-type></direction>'
        return f'<direction placement="{placement}"><direction-type><words font-style="italic">{escape(val)}</words></direction-type></direction>'
    if kind == 'wedge':
        return f'<direction placement="{placement}"><direction-type><wedge type="{val}"/></direction-type></direction>'
    if kind == 'words':
        return f'<direction placement="above"><direction-type><words font-style="italic">{escape(val)}</words></direction-type></direction>'
    if kind == 'wordsb':
        return f'<direction placement="below"><direction-type><words font-style="italic">{escape(val)}</words></direction-type></direction>'
    raise ValueError(d)


def write_score(path, title, subtitle, composer, arranger, parts, meta, harmonies=None, harm_part=None, volumes=None):
    """meta: list per bar of dict(key=(fifths,mode)|None, mark=str|None, section=str|None,
    tempo=int|None, tempo_text=str|None, barline=str|None)."""
    nb = len(meta)
    for p in parts:
        assert len(p.bars) == nb, (p.name, len(p.bars), nb)
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">',
           '<score-partwise version="4.0">',
           f'<work><work-title>{escape(title)}</work-title></work>',
           '<identification>',
           f'<creator type="composer">{escape(composer)}</creator>',
           f'<creator type="arranger">{escape(arranger)}</creator>',
           '<encoding><software>vibacappella generator</software></encoding>',
           '</identification>',
           '<defaults><scaling><millimeters>6.2</millimeters><tenths>40</tenths></scaling>'
           '<page-layout><page-height>1916</page-height><page-width>1355</page-width>'
           '<page-margins type="both"><left-margin>70</left-margin><right-margin>60</right-margin>'
           '<top-margin>60</top-margin><bottom-margin>60</bottom-margin></page-margins></page-layout>'
           '<system-layout><system-margins><left-margin>0</left-margin><right-margin>0</right-margin></system-margins>'
           '<system-distance>80</system-distance><top-system-distance>60</top-system-distance></system-layout>'
           '<staff-layout><staff-distance>55</staff-distance></staff-layout></defaults>',
           '<credit page="1"><credit-type>title</credit-type><credit-words default-x="677" default-y="1850" justify="center" valign="top" font-size="22">' + escape(title) + '</credit-words></credit>',
           '<credit page="1"><credit-type>subtitle</credit-type><credit-words default-x="677" default-y="1800" justify="center" valign="top" font-size="12">' + escape(subtitle) + '</credit-words></credit>',
           '<credit page="1"><credit-type>composer</credit-type><credit-words default-x="1295" default-y="1760" justify="right" valign="top" font-size="10">' + escape(composer) + '</credit-words></credit>',

           '<part-list>']
    for p in parts:
        out.append(f'<score-part id="{p.pid}"><part-name>{escape(p.name)}</part-name><part-abbreviation>{escape(p.abbr)}</part-abbreviation>')
        if p.drums:
            for code, (st, oc, nh, iid, midi, nm) in DRUMMAP.items():
                out.append(f'<score-instrument id="{p.pid}-{iid}"><instrument-name>{nm}</instrument-name></score-instrument>')
            for code, (st, oc, nh, iid, midi, nm) in DRUMMAP.items():
                # MuseScore 4 crashes on <volume> for unpitched instruments; drum level is set per note instead
                out.append(f'<midi-instrument id="{p.pid}-{iid}"><midi-channel>10</midi-channel><midi-program>1</midi-program><midi-unpitched>{midi + 1}</midi-unpitched></midi-instrument>')
        else:
            snd = f'<instrument-sound>{p.sound}</instrument-sound>' if p.sound else ''
            iname = 'Piano' if p.sound == 'keyboard.piano' else p.name  # MuseScore picks the playback sound from this
            out.append(f'<score-instrument id="{p.pid}-I1"><instrument-name>{escape(iname)}</instrument-name>{snd}</score-instrument>')
            vol = f'<volume>{volumes[p.pid]}</volume>' if volumes else ''
            out.append(f'<midi-instrument id="{p.pid}-I1"><midi-program>{p.program}</midi-program>{vol}</midi-instrument>')
        out.append('</score-part>')
    out.append('</part-list>')

    for pi, p in enumerate(parts):
        p.note_dyn = volumes[p.pid] if (volumes and p.drums and volumes[p.pid] < 100) else None
        out.append(f'<part id="{p.pid}">')
        open_wedge = False
        for bi in range(nb):
            m = meta[bi]
            out.append(f'<measure number="{bi + 1}">')
            attrs = []
            if bi == 0:
                attrs.append('<divisions>4</divisions>')
            if m.get('key') is not None and not p.drums:
                f, mode = m['key']
                attrs.append(f'<key><fifths>{f}</fifths><mode>{mode}</mode></key>')
            if bi == 0:
                attrs.append('<time><beats>3</beats><beat-type>4</beat-type></time>')
                attrs.append(p.clef)
            if attrs:
                out.append('<attributes>' + ''.join(attrs) + '</attributes>')
            if pi == 0:
                if m.get('mark'):
                    out.append(f'<direction placement="above"><direction-type><rehearsal font-weight="bold" font-size="14" enclosure="square">{escape(m["mark"])}</rehearsal></direction-type></direction>')
                if m.get('section'):
                    out.append(f'<direction placement="above"><direction-type><words font-weight="bold" font-size="11">{escape(m["section"])}</words></direction-type></direction>')
                if m.get('tempo'):
                    tt = m.get('tempo_text')
                    out.append('<direction placement="above"><direction-type>' +
                               (f'<words font-weight="bold">{escape(tt)} </words></direction-type><direction-type>' if tt else '') +
                               f'<metronome parentheses="no"><beat-unit>quarter</beat-unit><per-minute>{m["tempo"]}</per-minute></metronome></direction-type>'
                               f'<sound tempo="{m["tempo"]}"/></direction>')
            # harmonies for this bar
            hlist = harmonies[bi] if (harmonies and p is harm_part) else []
            pos = 0
            for ev in p.bars[bi]:
                for d in ev.dirs:
                    out.append(_dir_xml(d))
                ev_start = pos
                for ch, cpos in hlist:
                    if ev_start <= cpos < ev_start + ev.dur:
                        out.append(harmony_xml(ch, cpos - ev_start))
                out.extend(_note_xml(p, ev, pos))
                pos += ev.dur
            bl = m.get('barline')
            if bl:
                out.append(f'<barline location="right"><bar-style>{bl}</bar-style></barline>')
            out.append('</measure>')
        out.append('</part>')
    out.append('</score-partwise>')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(out))


def _note_xml(part, ev, pos):
    xs = []
    if ev.is_rest:
        if ev.dur == BAR and pos == 0:
            return ['<note><rest measure="yes"/><duration>12</duration><voice>1</voice></note>']
        segs = split(pos, ev.dur, rest=True)
        p = pos
        for L in segs:
            typ, dot = TYPES[L]
            xs.append(f'<note><rest/><duration>{L}</duration><voice>1</voice><type>{typ}</type>' + ('<dot/>' * dot) + '</note>')
            p += L
        return xs
    segs = split(pos, ev.dur)
    p = pos
    n = len(segs)
    for si, L in enumerate(segs):
        typ, dot = TYPES[L]
        tie_start = (si < n - 1) or ev.tie
        tie_stop = si > 0 or ev.tied_in
        heads = ev.drums if part.drums else ev.pitches
        for hi, h in enumerate(heads):
            x = [f'<note dynamics="{part.note_dyn}">' if part.note_dyn else '<note>']
            if hi > 0:
                x.append('<chord/>')
            if part.drums:
                st, oc, nh, iid, midi, nm = DRUMMAP[h]
                x.append(f'<unpitched><display-step>{st}</display-step><display-octave>{oc}</display-octave></unpitched>')
            else:
                alt = f'<alter>{h.alter}</alter>' if h.alter else ''
                x.append(f'<pitch><step>{h.step}</step>{alt}<octave>{h.octave}</octave></pitch>')
            x.append(f'<duration>{L}</duration>')
            if tie_stop: x.append('<tie type="stop"/>')
            if tie_start and not part.drums: x.append('<tie type="start"/>')
            if part.drums:
                x.append(f'<instrument id="{part.pid}-{iid}"/>')
            x.append('<voice>1</voice>')
            x.append(f'<type>{typ}</type>' + '<dot/>' * dot)
            if part.drums:
                x.append('<stem>up</stem>')
                if nh: x.append(f'<notehead>{nh}</notehead>')
            if hi == 0 and ev.beams and ev.beams[si]:
                x.append(ev.beams[si])
            nots = []
            if not part.drums:
                if tie_stop: nots.append('<tied type="stop"/>')
                if tie_start: nots.append('<tied type="start"/>')
            if ev.fermata and si == n - 1 and hi == 0:
                nots.append('<fermata type="upright"/>')
            if ev.accent and si == 0 and hi == 0:
                nots.append('<articulations><accent/></articulations>')
            if nots:
                x.append('<notations>' + ''.join(nots) + '</notations>')
            if ev.lyric and si == 0 and hi == 0 and not tie_stop:
                x.append(f'<lyric number="1"><syllabic>single</syllabic><text>{escape(ev.lyric)}</text></lyric>')
            x.append('</note>')
            xs.append(''.join(x))
        p += L
    return xs


def finalize(parts):
    """Expand events into notated segments with beams; mark tie continuations."""
    for p in parts:
        prev_tie = False
        for bar in p.bars:
            for ev in bar:
                ev.tied_in = prev_tie and not ev.is_rest
                prev_tie = ev.tie and not ev.is_rest
        for bar in p.bars:
            _beam_bar(bar)


def _beam_bar(bar):
    # build segment list: (ev, segidx, start, length, beamable)
    segs = []
    pos = 0
    for ev in bar:
        if ev.is_rest:
            ls = split(pos, ev.dur, rest=True) if not (ev.dur == BAR and pos == 0) else [BAR]
        else:
            ls = split(pos, ev.dur)
        ev.beams = [''] * len(ls)
        p = pos
        for i, L in enumerate(ls):
            segs.append([ev, i, p, L, (not ev.is_rest) and L in (1, 2, 3)])
            p += L
        pos += ev.dur
    # group by beat
    groups, cur = [], []
    for s in segs:
        beat = s[2] // 4
        if s[4] and (s[2] + s[3] - 1) // 4 == beat and (not cur or (cur[-1][2] // 4 == beat and cur[-1][2] + cur[-1][3] == s[2])):
            cur.append(s)
        else:
            if len(cur) > 1: groups.append(cur)
            cur = [s] if s[4] and (s[2] + s[3] - 1) // 4 == beat else []
    if len(cur) > 1: groups.append(cur)
    for g in groups:
        n = len(g)
        for i, s in enumerate(g):
            ev, si = s[0], s[1]
            b1 = 'begin' if i == 0 else ('end' if i == n - 1 else 'continue')
            x = f'<beam number="1">{b1}</beam>'
            if s[3] == 1:
                prev16 = i > 0 and g[i - 1][3] == 1
                next16 = i < n - 1 and g[i + 1][3] == 1
                if prev16 and next16: b2 = 'continue'
                elif prev16: b2 = 'end'
                elif next16: b2 = 'begin'
                else: b2 = 'forward hook' if i == 0 else 'backward hook'
                x += f'<beam number="2">{b2}</beam>'
            ev.beams[si] = x
