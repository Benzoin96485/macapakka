from pathlib import Path
import json,re
P=Path('outputs/EYKM_Acappella_v2/source/transcription.json');D=json.loads(P.read_text());B=D['bars']
def nn(s):
 if s=='r':return None
 m=re.fullmatch(r'([A-G])([b#]?)(\d)',s);return (int(m[3])+1)*12+dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[m[1]]+{'':0,'#':1,'b':-1}[m[2]]
def line(s):
 out=[]
 for tok in s.split():
  x=tok.split(':');out.append(dict(p=nn(x[0]),d=float(x[1]),ly=x[2].replace('_',' ') if len(x)>2 else ''))
 assert sum(e['d'] for e in out)==3,(s,out)
 return out
M={
10:'Eb4:.5:Ev- D4:.5:er- C4:1:y D4:.5:time Eb4:.5:you',
11:'D4:.5:kissed Eb4:.5 D4:1:me C4:1:I',
12:'C4:.5:trem- D4:.5:bled C4:.5:like Bb3:1.5:a',
13:'Bb3:1.5:child r:1.5',
14:'Eb4:.5:Ga- D4:.5:ther- C4:1:ing D4:.5:the Eb4:.5:ro-',
15:'D4:2.5:ses Bb3:.5:we',
16:'C4:1:sang Eb4:1:for F4:.5:the G4:.5:hope',
17:'G4:1 r:.5 G4:.5:Your F4:.5:ve- Eb4:.5:ry',
18:'D4:1:voice C4:1:is D4:.5:in Eb4:.5:my',
19:'D4:1:heart- D4:1:beat r:1',
20:'C4:.5:sweet- D4:.5:er C4:.5:than Bb3:1.5:my',
21:'Bb3:2:dream r:.5 C4:.5:We',
22:'C4:.5:were D4:.5:there Eb4:1:in D4:.5:ev- F4:.5:er-',
23:'D4:.5:last- Eb4:.5:ing D4:1 Bb3:1',
24:'Bb3:.5 C4:2.5:bloom',
25:'C4:2 r:1',
26:'Ab4:.5:Ro- G4:.5:ses F4:1:die G4:1:the',
27:'G4:.5:se- Ab4:.5:cret G4:1:is Eb4:1:in-',
28:'F4:.5:side G4:.5 F4:.5:the Eb4:1.5:pain',
29:'Eb4:2.5 r:.5',
30:'Ab4:.5:Winds G4:.5:are F4:1.5:high Ab4:.5:up-',
31:'Ab4:1:on G4:.5:the G4:1:hill Eb4:.5:I',
32:'F4:1:can- Ab4:1:not Bb4:.5:hear C5:.5:you',
33:'C5:1.5 Bb4:1 Ab4:.5',
34:'Ab4:.5:Come G4:.5:and F4:1:hold G4:.5:me Ab4:.5:close',
35:"G4:.5:I'm Ab4:.5:shiv- G4:.5:er- Eb4:1.5:ing",
36:'F4:.5:cold G4:.5:in F4:.5:the Eb4:1.5:heart',
37:'Eb4:.5:of Eb4:2:rain r:.5',
38:"F4:.5:Dark- G4:.5:ness Ab4:1.5:falls Bb4:.5:I'm",
39:'G4:.5:call- Ab4:.5:ing G4:1.5:for Eb4:.5:the',
40:'Eb4:.5 F4:2.5:dawn',41:'F4:3',42:'F4:3',43:'F4:2.5 r:.5',
60:'F4:.5:Sil- E4:.5:ver D4:.5:dish- D4:.5:es E4:.5:for F4:.5:the',
61:'E4:.5:mem- F4:.5:o- E4:1:ries C4:1:for',
62:'D4:.5:the E4:.5:days D4:.5:gone C4:1.5:by',
63:'C4:1.5 r:1.5',
64:'F4:.5:Sing- E4:.5:ing D4:1:for E4:.5:the F4:.5:prom-',
65:'E4:.5:is- F4:.5:es E4:1.5:to- C4:.5:mor-',
66:'C4:.5:row D4:.5:may F4:1:bring G4:.5 A4:.5',
67:'A4:1 r:.5 Bb4:.5:I A4:.5:har- G4:.5:bour',
68:'F4:1.5:all G4:.5:the A4:1:old',
69:'C5:1:af- A4:1:fec- A4:.5:tion r:.5',
70:'Bb4:.5:ro- A4:.5:ses G4:1.5:of A4:.5:the',
71:'A4:2:past r:1',
72:'F4:.5:Dark- F4:.5:ness F4:.5:falls F4:.5:and F4:.5:sum- E4:.5:mer',
73:'E4:.5:will F4:.5:be G4:2:gone',74:'A4:3',
75:'A4:2 r:.5 Bb4:.5:Joys',
76:'A4:1:of G4:1:the Bb4:1:day-',
77:'A4:.5:light F4:2 r:.5',
78:'G4:.5:sha- F4:.5:dows Eb4:1:of F4:1:the',
79:'F4:.5:star- D4:1.5:light r:.5 Eb4:.5:Ev-',
80:'D4:.5:ery- C4:1:thing D4:.5:was Eb4:1',
81:'F4:1:sweet Eb4:1:by C4:.5:your D4:.5:side',
82:'D4:1:my D4:2:love',
83:'D4:2 r:.5 Bb4:.5:Ru-',
84:'Bb4:.5:by A4:.5:tears G4:1:have Bb4:1:come',
85:'C5:1:to A4:.5:me F4:1.5:for',
86:'G4:1:your F4:.5:last Eb4:1.5:words',87:'F4:1.5 r:1.5',
88:"E4:.5:I'm E4:.5:here E4:.5:just F#4:.5:sing- G4:1:ing",
89:'G4:.5:my G4:.5:song F#4:1:of E4:1:woe',
90:'F#4:.5:Wait- F#4:.5:ing F#4:.5:for F#4:.5:you G4:.5:my A4:.5:love',
91:'A4:2 r:1',
92:'A4:.5:Now A4:.5:let A4:.5:my G4:.5:hap- G4:.5:pi- A4:.5:ness',
93:'A4:.5:sing A4:.5:in- A4:.5:side F#4:.5:my G4:1:dream',
94:'G4:3',95:'G4:1.5 r:1.5',96:'r:3',97:'r:2.5 G4:.5:ah',
98:'Bb4:3:ah',99:'Bb4:2.5 r:.5',
100:'Bb4:1:ah A4:2',101:'A4:2.5 r:.5',
102:'G4:.5:ya A4:.5 Bb4:1.5 A4:.5',
103:'A4:.5:ah G4:.5 F4:1 G4:.5 A4:.5',
104:'Bb4:2:ah C5:1',105:'C5:1:ah Bb4:1 C5:.5 r:.5',
106:'Bb4:3:ah',107:'Bb4:2.5 r:.5',
108:'Bb4:1:ah A4:2',109:'A4:2.5 r:.5',
110:'G4:.5:ya A4:.5 Bb4:1 A4:.5 G4:.5',
111:'A4:1:ah G4:.5 F4:.5 G4:.5 A4:.5',
112:'Bb4:2.5:ah r:.5',113:'C5:1:ah Bb4:1 A4:.5 r:.5',
114:'B4:3:ah',115:'B4:2.5 r:.5',
116:'A4:2:ah D5:1',117:'D5:2.5 r:.5',
118:'D5:.5:ya E5:.5 D5:1 C5:1',
119:'B4:1:ah A4:1 F#4:.5 r:.5',
120:'A4:.5:ah C5:2.5',121:'B4:2.5:ah r:.5',
122:'G4:3:ah',123:'B4:2.5:ah r:.5',
124:'B4:.5:ah E5:.5 D5:2',125:'D5:2.5 r:.5',
126:'Eb5:1:ah D5:1 C5:1',127:'C5:1:ah Bb4:1.5 r:.5',
128:'Eb5:2:ah D5:1',129:'Bb4:1:ah F#4:1 G4:1',
130:'G4:1:ah A4:1 Bb4:1',
131:'Bb4:.5:ya C5:.5 Bb4:1 C5:.5 Bb4:.5',
132:'C5:1:ah D5:1 C5:.5 Bb4:.5',
133:'A4:1.5:ah r:1.5',
145:'r:2.5 E4:.5:Ev-',
146:'D#4:1:er- C#4:1:y D#4:.5:time E4:.5:you',
147:'D#4:1:kissed D#4:.5:me D#4:1:my B3:.5:heart',
148:'C#4:.5:was D#4:.5:in C#4:.5:such B3:1.5:pain',
149:'B3:2 r:1',
150:'E4:.5:Ga- D#4:.5:ther- C#4:1:ing D#4:.5:the E4:.5:ro-',
151:'D#4:2.5:ses B3:.5:we',
152:'C#4:1:sang E4:1:of F#4:.5:the G#4:.5:grief',
153:'G#4:1 r:.5 G#4:.5:Your F#4:.5:ve- E4:.5:ry',
154:'D#4:1:voice C#4:1:is D#4:.5:in E4:.5:my',
155:'D#4:1:heart- D#4:1:beat r:1',
156:'C#4:.5:sweet- D#4:.5:er C#4:.5:than B3:1.5:des-',
157:'B3:2:pair r:.5 C#4:.5:We',
158:'C#4:.5:were D#4:.5:there E4:1:in D#4:.5:ev- F#4:.5:er-',
159:'D#4:.5:last- E4:.5:ing D#4:1 B3:1',
160:'B3:.5 C#4:2.5:bloom',161:'C#4:2 r:1',
162:'A4:.5:Un- G#4:.5:der- F#4:1:neath A4:1:the',
163:'G#4:.5:stars E4:2 r:.5',
164:'F#4:.5:sha- E4:.5:ded D4:1:by F#4:1:the',
165:'E4:.5:flow- C#4:1.5:ers r:.5 D4:.5:Kiss',
166:'C#4:.5:me B3:1:in C#4:.5:the D4:1:sum-',
167:'E4:1:mer D4:1:day B3:.5:gloom C#4:.5:my',
168:'C#4:3:love',169:'C#4:2 r:.5 A4:.5:You',
170:'A4:.5:are G#4:.5:all F#4:1:my A4:1:plea-',
171:'B4:1:sure G#4:.5:my E4:1.5:hope',
172:'F#4:1:and E4:.5:my D4:1.5:song',173:'E4:2 r:1',
174:'D#4:.5:I D#4:.5:will D#4:.5:be E#4:.5:here F#4:1:dream-',
175:'F#4:.5:ing F#4:.5:in E#4:1:the D#4:1:past',
176:'E#4:2 F#4:.5 G#4:.5',
177:'G#4:1 r:.5 A4:.5:Un- A4:1:til',
178:'A4:1:you G#4:1:come F#4:1',179:'F#4:1.5 r:1.5',
180:'G#4:.5:Un- G#4:.5:til F#4:.5:we F#4:.5:close E4:1:our',
181:'E4:1.5 r:1 E4:.5:eyes',182:'E4:.5 F#4:2.5',
183:'F#4:3',184:'F#4:3',185:'F#4:3',186:'F#4:2.5 r:.5',
}
for bar,s in M.items():B[bar-1]['Lead']=line(s)
# The source's upper choral line remains independently audible in the middle.
S=[
'D5:3:ah','D5:1:ah Eb5:1 D5:.5 r:.5','D5:1:ah C5:2','C5:2.5:ah r:.5',
'D5:2:ah Eb5:1','D5:1:ah C5:1 D5:.5 r:.5','D5:1:ah Eb5:1 D5:1','C5:2.5:ah r:.5',
'D5:3:ah','D5:1:ah Eb5:1 D5:.5 r:.5','D5:1:ah C5:2','C5:2.5:ah r:.5',
'D5:1:ah Eb5:1 D5:1','D5:1:ah Eb5:1 D5:.5 r:.5','D5:.5:ah Eb5:.5 D5:2','C5:1:ah Bb4:1 A4:.5 r:.5']
for i,s in enumerate(S,97):B[i]['Soprano']=line(s)
# Rebuild only genuine ties; a printed new syllable always articulates.
for b in B:
 for p in ['Lead','Soprano','Whistle']:
  for e in b.get(p,[]):e.pop('tie_start',None);e.pop('tie_stop',None)
for i in range(195):
 for p in ['Lead','Soprano','Whistle']:
  if p not in B[i] or p not in B[i+1]:continue
  a=B[i][p][-1];b=B[i+1][p][0]
  if a['p'] is not None and a['p']==b['p'] and not b['ly']:a['tie_start']=True;b['tie_stop']=True
D['method']='Local source separation and pitch/beat analysis; explicitly edited main lines, lyric underlay and choral response'
D['lyric_underlay']='All English text assigned explicitly; vocalise uses ah / ya; final singer-led checking still required'
P.write_text(json.dumps(D,indent=2))
print('Edited',len(M),'lead measures; added 16 measures of independent upper vocalise')
