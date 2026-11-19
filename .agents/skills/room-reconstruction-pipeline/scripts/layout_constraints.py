#!/usr/bin/env python3
"""Apply reviewed, normalized layout edits. No room-specific paths or dimensions."""
import argparse,copy,hashlib,json,math,random
from datetime import datetime,timezone
from pathlib import Path

def number(v):
 if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('Expected finite number: '+str(v))
 return float(v)
def vector(v,positive=False):
 if not isinstance(v,list) or len(v)!=3:raise ValueError('Expected XYZ list')
 out=[number(x) for x in v]
 if positive and min(out)<=0:raise ValueError('Size must be positive')
 return out
def index(layout):
 items=layout['assets'];ids=[a['instance_id'] for a in items]
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate instance_id')
 for a in items:
  vector(a['position']);vector(a['size'],True);number(a.get('yaw',0));number(a.get('tilt',0))
 return {a['instance_id']:a for a in items}
def interval(a,axis):
 x,y,_=a['position'];w,d,_=a['size'];t=a.get('yaw',0)
 extent=(abs(math.cos(t))*w+abs(math.sin(t))*d)/2 if axis==0 else (abs(math.sin(t))*w+abs(math.cos(t))*d)/2
 return a['position'][axis]-extent,a['position'][axis]+extent
def apply(layout,review,sha):
 if review.get('units')!='m' or layout.get('units')!='m':raise ValueError('Explicit metre units required')
 if review.get('reviewed') is not True:raise ValueError('Review normalized values before applying')
 if review.get('source_sha256')!=sha:raise ValueError('Stale layout fingerprint')
 d=copy.deepcopy(layout);by=index(d);log=[]
 for edit in review['edits']:
  if not edit.get('raw_user_text') or not edit.get('evidence'):raise ValueError('Every edit needs raw_user_text and evidence')
  op=edit['op']
  if op=='set_size':
   a=by[edit['instance_id']];a['size']=vector(edit['size_m'],True)
  elif op=='set_pose':
   a=by[edit['instance_id']]
   if 'position_m' in edit:a['position']=vector(edit['position_m'])
   for src,dst in [('yaw_deg','yaw'),('tilt_deg','tilt')]:
    if src in edit:a[dst]=math.radians(number(edit[src]))
  elif op=='gap':
   if edit.get('metric')!='world_aabb_face':raise ValueError('Gap metric must explicitly be world_aabb_face')
   axis={'X':0,'Y':1}[edit['axis']];side=edit['side'];gap=number(edit['gap_m'])
   if side not in [-1,1] or gap<0:raise ValueError('Invalid gap side/value')
   fixed=edit['fixed'];moving=edit['moving']
   if not fixed or not moving or len(set(moving))!=len(moving) or set(fixed)&set(moving):raise ValueError('Groups must be distinct and nonempty')
   fi=[interval(by[k],axis) for k in fixed];mo=[interval(by[k],axis) for k in moving]
   delta=max(v[1] for v in fi)+gap-min(v[0] for v in mo) if side==1 else min(v[0] for v in fi)-gap-max(v[1] for v in mo)
   for k in moving:by[k]['position'][axis]+=delta
   log.append(dict(operation='gap',delta_m=delta,metric='world_aabb_face',value_m=gap))
  elif op=='seating':
   size=vector(edit['chair_size_m'],True);n=edit['per_side'];tuck=number(edit['tuck_m']);rng=random.Random(edit['seed'])
   if not isinstance(n,int) or n<1 or n>12 or not 0<=tuck<size[1]/2:raise ValueError('Invalid seating count/tuck')
   jitter=edit['jitter'];tangent=number(jitter['tangent_m']);normal=number(jitter['normal_m']);angle=number(jitter['yaw_deg'])
   if min(tangent,normal,angle)<0:raise ValueError('Jitter magnitudes cannot be negative')
   targets=set(edit['tables'])
   # Replacing only this operation's own generated seats is explicit and repeatable.
   generated=[a for a in d['assets'] if a.get('generator')=='room-reconstruction-pipeline' and a.get('table_instance_id') in targets]
   if generated and not edit.get('replace_generated'):raise ValueError('Generated chairs already exist')
   if any(a.get('kind')=='chair' and a.get('table_instance_id') in targets and a not in generated for a in d['assets']):raise ValueError('Existing unowned chairs: review replacement/mapping explicitly')
   d['assets']=[a for a in d['assets'] if a not in generated]
   for key in edit['tables']:
    table=by[key];tx,ty,tz=table['position'];yaw=table.get('yaw',0);co,si=math.cos(yaw),math.sin(yaw)
    for side in [-1,1]:
     for j in range(n):
      u=(0 if n==1 else (j/(n-1)-.5)*table['size'][0]*.42)+rng.uniform(-tangent,tangent)
      v=side*(table['size'][1]/2+size[1]/2-tuck+rng.uniform(-normal,normal))
      chair=dict(instance_id=f'chair_{key}_{side}_{j}',asset_id=edit['chair_asset_id'],kind='chair',table_instance_id=key,position=[tx+u*co-v*si,ty+u*si+v*co,number(edit['floor_z_m'])],size=size[:],yaw=yaw+(0 if side==-1 else math.pi)+math.radians(rng.uniform(-angle,angle)),generator='room-reconstruction-pipeline',pose_status='seeded_not_measured')
      d['assets'].append(chair)
   by=index(d)
  else:raise ValueError('Unsupported operation: '+op)
  log.append(copy.deepcopy(edit))
 d['review_application']={'source_sha256':sha,'edits':log,'limitations':['Normalized values were reviewed; no automatic interpretation of ambiguous prose','Seating placement is seeded art direction; collision and door clearance need separate checks','World AABB face gaps are not arbitrary rotated-surface shortest distances']}
 index(d);return d
def write_json(path,value,overwrite=False):
 path=Path(path);data=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
 if path.exists():
  if not overwrite:raise FileExistsError(str(path))
  stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');path.with_name(path.name+'.'+stamp+'.bak').write_bytes(path.read_bytes())
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp');tmp.write_text(data,encoding='utf8');tmp.replace(path)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--layout',required=True);p.add_argument('--review',required=True);p.add_argument('--output',required=True);p.add_argument('--replace-backup',action='store_true');a=p.parse_args();source=Path(a.layout);raw=source.read_bytes();review=json.loads(Path(a.review).read_text());value=apply(json.loads(raw),review,hashlib.sha256(raw).hexdigest());write_json(a.output,value,a.replace_backup);print(json.dumps({'status':'APPLIED','assets':len(value['assets']),'output':a.output}))
if __name__=='__main__':main()
