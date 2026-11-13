"""Portable rehearsal-proof PDF. MusicXML + MuseScore is the publication workflow.

Uses real noteheads, rests, accidentals, flags, ties and lyrics; deliberately no
automatic key spelling, lyric hyphenation or sophisticated beam/layout rules.
"""
from pathlib import Path
from .export import fragments, SPELLINGS, TYPES, tempo_events
from .music import PARTS


def score_pdf(score, path, parts=PARTS, font_file=""):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    if not font_file or not Path(font_file).is_file():
        raise ValueError("Proof PDF needs render.font_file with musical glyphs, e.g. MuseScore's FreeSerif.ttf")
    if "MusicProof" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("MusicProof", font_file))
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    full = len(parts) > 1
    w, h = (841.89, 1190.55) if full else (595.28, 841.89)
    c = canvas.Canvas(str(path), pagesize=(w, h))
    c.setTitle(score["title"]+" - "+("Full Score" if full else parts[0]))
    per_system, systems_page = (2, 2) if full else (2, 5)
    groups = [score["bars"][i:i+per_system] for i in range(0, len(score["bars"]), per_system)]
    space = 6 if full else 7
    def text(x, y, content, size=9, center=False):
        c.setFillColorRGB(.08, .13, .17)
        c.setFont("STSong-Light" if any('\u4e00' <= s <= '\u9fff' for s in str(content)) else "MusicProof", size)
        (c.drawCentredString if center else c.drawString)(x, y, str(content))
    def line(x1, y1, x2, y2, width=.55):
        c.setStrokeColorRGB(.1, .15, .18); c.setLineWidth(width); c.line(x1, y1, x2, y2)
    for page, begin in enumerate(range(0, len(groups), systems_page), 1):
        text(35, h-40, score["title"], 20)
        text(35, h-60, "SATB + lead + VP + whistle | Rehearsal proof | Concert pitch", 10)
        text(35, h-77, "Automatic draft; source uncertainties remain. MusicXML is the editable master.", 9)
        text(35, 22, "VP: K kick / pf snare / ka rim / t hat / ts open hat / dm tom / ksh cymbal", 8)
        text(w-45, 22, page, 9)
        for si, bars in enumerate(groups[begin:begin+systems_page]):
            top = h-145-si*(515 if full else 135)
            left, usable = 112 if full else 86, w-(147 if full else 121)
            bar_width = usable/len(bars)
            first = bars[0]
            us = next((us for tick, us in reversed(tempo_events(score)) if tick <= first["start_tick"]), 500000)
            text(left, top+48, f"m. {first['number']}  |  quarter = {60e6/us:.1f}", 9)
            for pi, part in enumerate(parts):
                bottom = top-pi*66 if full else top
                head = left-40
                text(35, bottom+10, part, 9)
                for j in range(5):
                    line(head, bottom+j*space, left+usable, bottom+j*space)
                if part == "VP":
                    text(head+2, bottom+space, "||", 20)
                else:
                    text(head, bottom-space*.35, "\U0001d122" if part == "Bass" else "\U0001d11e", 31 if part == "Bass" else 42)
                    if part == "Tenor":
                        text(head+9, bottom-9, "8", 7)
                text(left-10, bottom+13, first["numerator"], 13, True)
                text(left-10, bottom+1, first["denominator"], 13, True)
                for bj, bar in enumerate(bars):
                    x0, bw = left+bj*bar_width, bar_width
                    dur, base = bar["duration_ticks"], bar["start_tick"]
                    if pi == 0:
                        for harmony in score["harmonies"]:
                            if base <= harmony["start_tick"] < base+dur:
                                x = x0+10+(bw-25)*(harmony["start_tick"]-base)/dur
                                text(x, bottom+35, harmony["candidates"][harmony["selected"]]["symbol"], 10)
                    previous_tie = None
                    for ev in score["score"][part][bar["number"]-1]:
                        frags = fragments(ev)
                        for fi, (offset, ticks) in enumerate(frags):
                            x = x0+13+(bw-28)*offset/dur
                            pitch = ev["pitch"]
                            typ, dots = TYPES[ticks]
                            if pitch is None:
                                glyph = {"whole": "\U0001d13b", "half": "\U0001d13c", "quarter": "\U0001d13d", "eighth": "\U0001d13e", "16th": "\U0001d13f"}[typ]
                                text(x-3, bottom+space, glyph, 22)
                                if dots:
                                    c.circle(x+8, bottom+space*2.4, 1, fill=1, stroke=0)
                                previous_tie = None
                                continue
                            display = pitch+(12 if part == "Tenor" else 0)
                            step, alter = SPELLINGS[display % 12]
                            diatonic = (display//12-1)*7+"CDEFGAB".index(step)
                            baseline = 18 if part == "Bass" else 30
                            y = bottom+2*space if part == "VP" else bottom+(diatonic-baseline)*space/2
                            for ledger in range(-2, int((y-bottom)/(space/2))-1, -2) if y < bottom else range(10, int((y-bottom)/(space/2))+1, 2):
                                line(x-6, bottom+ledger*space/2, x+6, bottom+ledger*space/2)
                            if part == "VP":
                                line(x-3, y-3, x+3, y+3, 1); line(x-3, y+3, x+3, y-3, 1)
                            else:
                                # Explicit natural/flat on each attack avoids accidental carry ambiguity.
                                if fi == 0 and not ev.get("tie_stop"):
                                    text(x-11, y-3, "\u266d" if alter else "\u266e", 13)
                                c.setFillColorRGB(.08, .13, .17)
                                c.ellipse(x-4, y-2.7, x+4, y+2.7, fill=0 if ticks >= 960 else 1, stroke=1)
                            up = y < bottom+2*space or part == "VP"
                            direction = 1 if up else -1
                            stemx, stemy = x+direction*3.7, y+direction*21
                            if typ != "whole":
                                line(stemx, y, stemx, stemy, .8)
                            for flag in range(2 if typ == "16th" else 1 if typ == "eighth" else 0):
                                yy = stemy-direction*flag*5
                                curve = c.beginPath(); curve.moveTo(stemx, yy)
                                curve.curveTo(stemx+10, yy-direction*4, stemx+8, yy-direction*10, stemx+3, yy-direction*13)
                                c.drawPath(curve)
                            if dots:
                                c.circle(x+8, y+2, 1, fill=1, stroke=0)
                            tie_stop = fi > 0 or ev.get("tie_stop")
                            tie_start = fi < len(frags)-1 or ev.get("tie_start")
                            if tie_stop:
                                px = previous_tie[0] if previous_tie else x0
                                py = previous_tie[1] if previous_tie else y
                                curve = c.beginPath(); curve.moveTo(px+4, py-5)
                                curve.curveTo(px+(x-px)*.3, min(py,y)-13, px+(x-px)*.7, min(py,y)-13, x-4, y-5)
                                c.drawPath(curve)
                            previous_tie = (x, y) if tie_start else None
                            if ev.get("syllable") and fi == 0 and not ev.get("tie_stop"):
                                text(x, bottom-24, ev["syllable"], 8, True)
                    if previous_tie:
                        x, y = previous_tie
                        curve = c.beginPath(); curve.moveTo(x+4, y-5)
                        curve.curveTo(x+10, y-12, x0+bw-10, y-12, x0+bw-2, y-5)
                        c.drawPath(curve)
                    line(x0+bw, bottom, x0+bw, bottom+4*space)
            line(left-43, top-(len(parts)-1)*66, left-43, top+4*space, 1)
        c.showPage()
    c.save()


if __name__ == "__main__":
    import sys
    from .storage import Store
    store = Store(sys.argv[1])
    root = store.path(sys.argv[2])
    score, cfg = store.read("score.json"), store.read("config.json")
    for label, selected in [("Full_Score", PARTS)]+[(p, [p]) for p in PARTS]:
        score_pdf(score, root/"scores"/(label+".pdf"), selected, cfg["render"]["font_file"])
