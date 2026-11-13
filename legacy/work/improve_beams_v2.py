from pathlib import Path
p=Path('outputs/EYKM_Acappella_v2/source/render_arrangement.py');s=p.read_text()
s=s.replace(" pos=0;previous_tie=None\n layout=[]\n for e in expanded:",''' pos=0;previous_tie=None
 layout=[]
 beamgroups=[];beamed={};positions=[];qpos=0
 for ev in expanded:positions.append(qpos);qpos+=ev['d']
 for beat in range(3):
  group=[]
  for j,ev in enumerate(expanded):
   if beat-1e-7<=positions[j]<beat+1-1e-7 and positions[j]+ev['d']<=beat+1+1e-7 and ev['p'] is not None and ev['d']<1:
    if group and abs(positions[j]-(positions[group[-1]]+expanded[group[-1]]['d']))>1e-7:
     if len(group)>1:beamgroups.append(group)
     group=[]
    group.append(j)
   elif group:
    if len(group)>1:beamgroups.append(group)
    group=[]
  if len(group)>1:beamgroups.append(group)
 for group in beamgroups:
  ys=[]
  for j in group:
   if part=='VP':ny=bottom+2*space
   else:
    dia,_,_,_=diatonic(expanded[j]['p'],inf['key'],inf['chord'],part)
    base=2*7+4 if part=='Bass' else 4*7+2;ny=bottom+(dia-base)*space/2
   ys.append(ny)
  up=np.mean(ys)<bottom+2*space or part=='VP'
  by=max(ys)+space*3.3 if up else min(ys)-space*3.3
  for j in group:beamed[j]=(up,by)
 for ei,e in enumerate(expanded):''')
s=s.replace("  up=(ny<bottom+2*space) or part=='VP'\n  stemx=nx+(space*.65 if up else -space*.65);stemy=ny+(space*3.3 if up else -space*3.3)","  up,stemy=beamed.get(ei,((ny<bottom+2*space) or part=='VP',None))\n  stemx=nx+(space*.65 if up else -space*.65)\n  if stemy is None:stemy=ny+(space*3.3 if up else -space*3.3)")
s=s.replace("if e['d'] in [.25,.5,.75]:\n   # Individual flags", "if e['d'] in [.25,.5,.75] and ei not in beamed:\n   # Individual flags")
s=s.replace("  previous_tie=(nx,ny) if e.get('tie_start') else None",'''  if e.get('tie_stop') and not previous_tie:
   pth=c.beginPath();pth.moveTo(x+1,ny-space);pth.curveTo(x+4,ny-space*1.8,nx-space*1.2,ny-space*1.8,nx-space*.7,ny-space*.75);c.setLineWidth(.65);c.drawPath(pth)
  previous_tie=(nx,ny) if e.get('tie_start') else None''')
s=s.replace(" # Barline at the right edge.",''' for group in beamgroups:
  up,by=beamed[group[0]];sgn=1 if up else -1
  xs=[layout[j][1]+(space*.65 if up else -space*.65) for j in group]
  rule(c,xs[0],by,xs[-1],by,space*.45)
  for k,j in enumerate(group):
   if expanded[j]['d']==.25:
    if k+1<len(group) and expanded[group[k+1]]['d']==.25:
     rule(c,xs[k],by-sgn*space*.8,xs[k+1],by-sgn*space*.8,space*.4)
    elif k==0 or expanded[group[k-1]]['d']!=.25:
     end=xs[k]+(space*1.1 if k==0 else -space*1.1)
     rule(c,xs[k],by-sgn*space*.8,end,by-sgn*space*.8,space*.4)
 if previous_tie:
  px,py=previous_tie;pth=c.beginPath();pth.moveTo(px+space*.7,py-space*.75);pth.curveTo(px+space*1.2,py-space*1.7,x+w-space*1.5,py-space*1.7,x+w-2,py-space);c.setLineWidth(.65);c.drawPath(pth)
 # Barline at the right edge.''')
p.write_text(s)
