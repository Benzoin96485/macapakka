"""everytime you kissed me — a cappella arrangement v2.
Built from the bar-by-bar transcription in _work/tr/ (lead, chords, bass, whistle). Bar keys follow the original
recording from bar 13 (verse 1) on; the rubato intro is re-barred into 9 bars stored under keys 4-12, so the score
measure = key - 3. Textures follow the original instrumentation of each section."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mxl import *
from mxl import _dir
from v2_trfile import read_tr

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.dirname(WORK)
TR = f'{WORK}/tr'
NB = 202  # bar keys 0..201
FIRST = 4  # first bar key used in the score (rubato intro occupies keys 4-12)

# ------------------------------------------------------------------ inputs
def read_chords(path):
    ch = {}
    for line in open(path, encoding='utf-8'):
        l = line.strip()
        if not l or l.startswith('#'):
            continue
        b, s = l.split(':', 1)
        b = int(b)
        if '|' in s:
            a, c = [x.strip() for x in s.split('|')]
            ch[b] = [(a, 6), (c, 6)]
        else:
            parts = s.split()
            ch[b] = [(parts[0], 12)] if len(parts) == 1 else [(p.split(':')[0], int(p.split(':')[1])) for p in parts]
    return ch


CHORDS = read_chords(f'{TR}/chords.txt')
LEAD = read_tr(f'{TR}/lead.txt')
BASS = read_tr(f'{TR}/bass.txt')
WHIS = read_tr(f'{TR}/whistle.txt')

# ------------------------------------------------------------------ choir (S A T) from chords + textures
TEX = {
    'pad':   [(12, 'x', 1)],
    'six8':  [(6, 'x', 0), (6, 'x', 0)],
    'off8':  [(2, 'r', 0), (2, 'x', 0), (2, 'x', 0), (2, 'r', 0), (2, 'x', 0), (2, 'x', 0)],
    'pulse8': [(2, 'x', 0)] * 6,
    'rest':  [(12, 'r', 0)],
    # intro: voices enter one 16th apart, imitating the harp-like rolled chord on each downbeat
    'roll1': [(1, 'r', 0), (11, 'x', 0)], 'roll2': [(2, 'r', 0), (10, 'x', 0)], 'roll3': [(3, 'r', 0), (9, 'x', 0)],
    # a-tempo bar before verse 1: entries on beats 2 and 3 (piano G-chord arpeggio in the original)
    'beat2': [(4, 'r', 0), (8, 'x', 0)], 'beat3': [(8, 'r', 0), (4, 'x', 0)],
}
SYL = {'pad': 'oo', 'six8': 'doo', 'off8': 'doo', 'pulse8': 'da', 'rest': None,
       'roll1': 'oo', 'roll2': 'oo', 'roll3': 'oo', 'beat2': 'mm', 'beat3': 'mm'}


class Choir:
    def __init__(self):
        self.bars = {v: [] for v in 'SAT'}
        self.prev = None
        self.prevB = None
        self.last = {v: None for v in 'SAT'}
        self.harm = []
        self.last_sym = None

    def bar(self, b, tx, target):
        segs, pos = [], 0
        for sym, dur in CHORDS[b]:
            forced = None
            if '=' in sym:
                sym, fv = sym.split('=')
                forced = tuple(P(x) for x in fv.split(','))
            segs.append((Chord(sym), pos, dur, forced)); pos += dur
        hb = []
        for ch, p0, d, _ in segs:
            if ch.sym != self.last_sym:
                hb.append((ch, p0)); self.last_sym = ch.sym
        self.harm.append(hb)
        vo = []
        for ch, p0, d, forced in segs:
            bp = place_bass(ch.bass, self.prevB)
            t, a, s = forced or voice_upper(ch, bp, self.prev, target)
            self.prev, self.prevB = (t, a, s), bp
            vo.append((p0, d, {'S': s, 'A': a, 'T': t}))
        for v in 'SAT':
            name, syl = (tx.get(v, 'rest').split(':') + [None])[:2]
            syl = syl or SYL[name]
            evs, p = [], 0
            for dur, kind, hold in TEX[name]:
                if kind == 'r':
                    evs.append(Ev(dur)); self.last[v] = None; p += dur
                    continue
                end = p + dur
                while p < end:
                    p0, d, vv = next(x for x in vo if x[0] <= p < x[0] + x[1])
                    seg_end = min(end, p0 + d)
                    ev = Ev(seg_end - p, [vv[v]])
                    lv = self.last[v]
                    if hold and lv is not None and lv.pitches[0] == vv[v] and not tx.get('_new'):
                        lv.tie = True
                    else:
                        ev.lyric = syl
                    evs.append(ev); self.last[v] = ev
                    p = seg_end
            self.bars[v].append(evs)


def spans(*items):
    out = [dict() for _ in range(NB)]
    for a, b, d in items:
        for i in range(a, b + 1):
            out[i].update(d)
        out[a]['_new'] = True   # re-articulate at section starts
    return out


ALL = lambda tex: {'S': tex, 'A': tex, 'T': tex}

TEXTURE = spans(
    (0, 3, ALL('rest')),                                        # (unused keys)
    (4, 11, ALL('pad')),                                        # intro: chords rolled B->T->A->S (see note)
    (12, 12, {'S': 'rest', 'A': 'beat3', 'T': 'beat2'}),        # a tempo: G chord built up beat by beat
    (13, 20, {'S': 'rest', 'A': 'six8', 'T': 'six8'}),          # verse 1: piano pulse only
    (21, 28, {'S': 'pad', 'A': 'six8', 'T': 'six8'}),
    (29, 41, {'S': 'pad:ah', 'A': 'pad:ah', 'T': 'six8'}),      # chorus 1: strings enter
    (42, 46, ALL('pad:ah')),                                    # band enters
    (47, 62, {'S': 'six8:dah', 'A': 'six8:dah', 'T': 'off8'}),  # interlude: full band
    (63, 70, {'S': 'rest', 'A': 'six8', 'T': 'six8'}),          # verse 2: bass + piano
    (71, 78, {'S': 'pad', 'A': 'six8', 'T': 'six8'}),           # drums back
    (79, 90, {'S': 'six8:dah', 'A': 'six8:dah', 'T': 'off8'}),  # chorus 2
    (91, 96, {'S': 'pad:ah', 'A': 'pulse8', 'T': 'pulse8'}),    # strings pulsing 8ths
    (97, 100, ALL('pad:ah')),                                   # G major climax
    (101, 116, {'S': 'pad', 'A': 'pad', 'T': 'off8'}),          # under the lead vocalise
    (117, 124, ALL('pad')),                                     # bridge
    (125, 132, {'S': 'six8:dah', 'A': 'six8:dah', 'T': 'off8'}),
    (133, 141, ALL('pad:ah')),                                  # drums/bass out, G pedal
    (142, 148, {'S': 'pad:mm', 'A': 'pad:mm', 'T': 'pad:mm'}),  # break (alto carries the line, see below)
    (149, 156, {'S': 'rest', 'A': 'six8', 'T': 'six8'}),        # verse 3: piano
    (157, 164, {'S': 'pad', 'A': 'six8', 'T': 'six8'}),
    (165, 176, {'S': 'six8:dah', 'A': 'six8:dah', 'T': 'off8'}),  # chorus 3: guitar/piano, no strings
    (177, 182, ALL('six8:dah')),
    (183, 184, ALL('pad:ah')),
    (185, 194, ALL('pad')),                                     # tag: piano chords under F#4
    (195, 201, ALL('pad')),                                     # outro
)

for _b in range(4, 12):
    TEXTURE[_b]['_new'] = True

TARGETS = [((0, 12), dict(S=67, A=63, T=58)), ((13, 28), dict(S=70, A=64, T=58)),
           ((29, 46), dict(S=72, A=66, T=60)), ((47, 62), dict(S=72, A=67, T=60)),
           ((63, 78), dict(S=70, A=65, T=58)), ((79, 100), dict(S=73, A=68, T=61)),
           ((101, 116), dict(S=70, A=65, T=58)), ((117, 141), dict(S=72, A=66, T=60)),
           ((142, 148), dict(S=69, A=64, T=57)), ((149, 164), dict(S=71, A=64, T=58)),
           ((165, 184), dict(S=73, A=68, T=61)), ((185, 201), dict(S=70, A=65, T=58))]


def target(b):
    return next(t for (a, z), t in TARGETS if a <= b <= z)


choir = Choir()
for b in range(NB):
    if b < FIRST:
        choir.harm.append([])
        for v in 'SAT':
            choir.bars[v].append([Ev(12)])
        continue
    choir.bar(b, TEXTURE[b], target(b))
S, A, T = (choir.bars[v] for v in 'SAT')

# alto carries the original break melody (other/strings line), 142-148
A_BREAK = parse("""A4:10 F4:2 | G4:2 A4:2 G4:4 F4:3 D4:1 | F4:4 Bb4:2 C5:2 D5:4 | Bb4:2 A4:2 G4:4 G4:4 |
A4:4 A4:4 D5:2 F4:2 | G4:2 F4:2 Eb4:2 D4:2 C4:2 Eb4:2 | C4:6 Db4:6""")
for i, bar in enumerate(A_BREAK):
    bar[0].lyric = 'oo'
    A[142 + i] = bar


# ------------------------------------------------------------------ lead, bass, whistle from transcription
def from_tr(tr, b, rest_dirs=None):
    if b not in tr:
        return [Ev(12)]
    return [Ev(e.dur, list(e.pitches), [], e.tie, e.lyric, list(e.dirs), e.fermata, e.accent) for e in tr[b]]


lead = [from_tr(LEAD, b) for b in range(NB)]
whistle = [from_tr(WHIS, b) for b in range(NB)]
bass = [from_tr(BASS, b) for b in range(NB)]
QUIET = set(range(0, 29)) | set(range(133, 165)) | set(range(185, NB))
prev_tie = False
for b, bar in enumerate(bass):
    for e in bar:
        if e.pitches and not prev_tie:
            e.lyric = ('mm' if b < 13 or 133 <= b < 149 else 'doo') if b in QUIET else ('dm' if e.dur <= 4 else 'doo')
        prev_tie = e.tie and bool(e.pitches)
for b in (101, 146):
    for e in lead[b]:
        if e.pitches:
            e.lyric = 'ah' if b == 101 else 'mm'
            break

# ------------------------------------------------------------------ vocal percussion (follows the original drum map)
VPAT = {
    'R': 'R',
    'hats': 'h:2 h:2 h:2 h:2 h:2 h:2',
    'hin': 'r:6 h:2 h:2 h:2',
    'l1': 'K+h:2 h:2 h:2 k+h:2 h:2 h:2',
    'l2': 'K+h:2 h:2 h:2 k+h:2 h:2 K+h:2',
    'g1': 'K+h:2 h:2 h:2 S+h:2 h:2 K+h:2',
    'g2': 'K+h:2 h:2 K+h:2 S+h:2 h:2 h:2',
    'gc': 'K+C:2 h:2 h:2 S+h:2 h:2 K+h:2',
    'crash': 'K+C:2 h:2 h:2 h:2 h:2 h:2',
    'fill': 'K+h:2 h:2 h:2 S:1 S:1 S:1 S:1 S:1 S:1',
    'swell': 'o:12',
    'swell2': 'o:6 r:6',
}
VPMAP = {}
def vp_range(a, z, seq):
    for i, b in enumerate(range(a, z + 1)):
        VPMAP[b] = seq[i % len(seq)]
VPMAP[11] = 'swell'
vp_range(44, 44, ['hin']); vp_range(45, 45, ['crash'])
vp_range(46, 61, ['g1', 'g2']); VPMAP.update({47: 'gc', 51: 'gc', 55: 'gc', 59: 'gc', 54: 'fill', 62: 'fill'})
vp_range(70, 70, ['hin']); vp_range(71, 77, ['l1', 'l2']); VPMAP[78] = 'fill'
vp_range(79, 100, ['g1', 'g2'])
for b in (79, 83, 87, 91, 95, 97, 98):
    VPMAP[b] = 'gc'
VPMAP.update({86: 'fill', 90: 'fill', 96: 'fill'})
vp_range(101, 132, ['g1', 'g2'])
for b in (101, 109, 117, 125, 129):
    VPMAP[b] = 'gc'
VPMAP.update({108: 'fill', 116: 'fill', 124: 'fill', 132: 'fill'})
vp_range(157, 164, ['hats'])
vp_range(165, 176, ['l1', 'l2']); VPMAP[165] = 'crash'
vp_range(177, 183, ['hats'])
perc = [parse(VPAT[VPMAP.get(b, 'R')], drums=True)[0] for b in range(NB)]

# ------------------------------------------------------------------ score meta
meta = [dict() for _ in range(NB)]
SECTIONS = [
    (FIRST, 'A', '前奏 Intro (rubato)', (-3, 'minor')), (13, 'B', '主歌 1 Verse 1', None),
    (29, 'C', '副歌 1 Chorus 1', (-4, 'minor')), (47, 'D', '间奏 Interlude (Whistle)', None),
    (63, 'E', '主歌 2 Verse 2', (-1, 'minor')), (79, 'F', '副歌 2 Chorus 2', (-2, 'minor')),
    (101, 'G', '间奏 2 (Lead vocalise)', None), (117, 'H', '桥段 Bridge', (1, 'minor')),
    (142, 'I', '过渡 Break', None), (149, 'J', '主歌 3 Verse 3', (4, 'minor')),
    (165, 'K', '副歌 3 Chorus 3', (3, 'minor')), (185, 'L', '尾句 Tag', None),
    (195, 'M', '尾声 Outro', None),
]
for b, mark, label, key in SECTIONS:
    meta[b].update(mark=mark, section=label)
    if key:
        meta[b]['key'] = key
    if b > FIRST:
        meta[b - 1].setdefault('barline', 'light-light')
meta[129]['key'] = (-2, 'minor')
meta[FIRST].update(tempo=108, tempo_text='Rubato')
meta[12].update(tempo=126, tempo_text='a tempo')
meta[NB - 1]['barline'] = 'light-heavy'

# ------------------------------------------------------------------ dynamics and performance notes
CH4 = [S, A, T, bass]


def at(bars, b, *toks, pos=0):
    p = 0
    for ev in bars[b]:
        if p >= pos:
            for t in toks:
                ev.dirs.append(t if isinstance(t, tuple) else _dir(t.lstrip('!')))
            return
        p += ev.dur
    for t in toks:
        bars[b][-1].dirs.append(t if isinstance(t, tuple) else _dir(t.lstrip('!')))


def ch(b, *toks, pos=0):
    for p in CH4:
        at(p, b, *toks, pos=pos)


W = ('words',)
at(whistle, 4, '!mp', ('words', 'chorus theme')); at(whistle, 10, ('words', 'rit.'))
ch(4, '!p'); at(S, 4, ('words', '每小节第1拍 B→T→A→S 依次快速滚入，模仿原曲的琶音（harp-like roll）')); ch(8, '!<'); ch(10, '!/', '!mp', '!>'); ch(11, '!/', '!p')
ch(12, '!pp')
at(perc, 11, '!pp', '!<', ('words', 'cymbal swell "shhh"')); at(perc, 12, '!/')
for part in [whistle, S, A, T, bass]:   # fermata on the G chord that closes the rubato intro
    held = [e for e in part[11] if e.pitches]
    if held:
        held[-1].fermata = True
perc[11][-1].fermata = True
at(lead, 13, '!mp', ('words', '（歌词请按授权歌词本自行填入）')); ch(13, '!p', ('words', 'piano-like pulse'))
at(lead, 29, '!mf'); ch(29, '!mp', ('words', 'strings')); ch(41, '!<'); ch(43, '!/', '!f')
at(perc, 44, '!mp', ('words', 'VP in')); at(perc, 46, '!mf')
at(whistle, 47, '!f'); ch(47, '!mf'); at(perc, 47, ('words', 'full groove'))
at(lead, 63, '!mp'); ch(63, '!p'); at(perc, 70, '!p'); ch(71, '!mp'); at(perc, 71, '!mp', ('words', 'light groove'))
at(lead, 79, '!f'); ch(79, '!mf'); at(perc, 79, '!f', ('words', 'full groove')); ch(91, '!<'); ch(97, '!/', '!f')
at(lead, 97, '!<'); at(lead, 98, '!/', '!ff')
at(lead, 101, '!mf', ('words', 'ad lib. "ah"')); ch(101, '!mp')
at(lead, 117, '!mp'); ch(117, '!p'); ch(125, '!mf'); at(lead, 125, '!mf'); ch(131, '!<'); ch(133, '!/', '!f', '!>')
ch(141, '!/', '!p')
ch(142, '!pp'); at(lead, 146, '!p', ('words', 'hum')); at(A, 142, ('words', 'melody (orig. strings)'))
at(A, 148, ('words', 'C → D♭(=C♯) 半音上移转调'))
at(lead, 149, '!mp'); ch(149, '!pp'); ch(157, '!p'); at(perc, 157, '!pp', ('words', 'hats only'))
at(lead, 165, '!f'); ch(165, '!mf'); at(perc, 165, '!mp', ('words', 'lighter groove than chorus 2'))
at(perc, 177, '!p'); ch(183, '!>')
at(lead, 185, '!mf', ('words', '持续 F#4')); ch(185, '!p')
at(lead, 190, ('words', 'ad lib.'))
at(whistle, 195, '!mp', ('words', 'orig. piano figure')); ch(195, '!pp')
for part in [whistle, lead, S, A, T, bass]:
    last = [e for e in part[NB - 1] if e.pitches]
    if last:
        last[-1].fermata = True
# whistle/lead end on held notes: make the final bar a single sustained note
lead[NB - 1] = [Ev(12, [P('C#5')], fermata=True)]
lead[NB - 2][-1].tie = True if lead[NB - 2][-1].pitches and lead[NB - 2][-1].pitches[0] == P('C#5') else False

# ------------------------------------------------------------------ parts & output
G = '<clef><sign>G</sign><line>2</line></clef>'
parts = [
    PartSpec('P1', 'Whistle 口哨', 'Wh.', '<clef><sign>G</sign><line>2</line><clef-octave-change>1</clef-octave-change></clef>', program=79),
    PartSpec('P2', 'Lead 主唱', 'Ld.', G, program=1, sound='keyboard.piano'),
    PartSpec('P3', 'Soprano', 'S.', G, program=1, sound='keyboard.piano'),
    PartSpec('P4', 'Alto', 'A.', G, program=1, sound='keyboard.piano'),
    PartSpec('P5', 'Tenor', 'T.', '<clef><sign>G</sign><line>2</line><clef-octave-change>-1</clef-octave-change></clef>', program=1, sound='keyboard.piano'),
    PartSpec('P6', 'Bass', 'B.', '<clef><sign>F</sign><line>4</line></clef>', program=1, sound='keyboard.piano'),
    PartSpec('P7', 'Vocal Percussion', 'VP', '<clef><sign>percussion</sign></clef>', drums=True),
]
for ps, bars in zip(parts, [whistle, lead, S, A, T, bass, perc]):
    assert len(bars) == NB, (ps.name, len(bars))
    for i, bar in enumerate(bars):
        tot = sum(e.dur for e in bar)
        assert tot == 12, (ps.name, i, tot)
    ps.bars = bars[FIRST:]
meta = meta[FIRST:]
HARM = choir.harm[FIRST:]
finalize(parts)

STEM = {'P1': 'Whistle', 'P2': 'Lead', 'P3': 'Soprano', 'P4': 'Alto', 'P5': 'Tenor', 'P6': 'Bass', 'P7': 'VP'}
TITLE = ('everytime you kissed me',
         'A cappella arr. v2 — Lead + SATB + Whistle + Vocal Percussion · 社团内部非营利使用',
         'Music: 梶浦由記 (Yuki Kajiura)',
         'A cappella arr. v2')

if __name__ == '__main__':
    out = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == 'stems':
        for ps in parts:
            write_score(f'{out}/stem_{STEM[ps.pid]}.musicxml', *TITLE, [ps], meta)
    else:
        write_score(out, *TITLE, parts, meta, HARM, parts[1])
        print('bars', NB, 'written', out)
