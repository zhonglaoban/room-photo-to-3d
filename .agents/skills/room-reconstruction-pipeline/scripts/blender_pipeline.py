"""Config-driven static room sync, evaluated-geometry QA, and fixed-camera rendering.
Run: blender --background source.blend --python-exit-code 1 --python THIS -- MODE --profile PROFILE ...
No factory reset, automatic wall construction, or implicit overwrite of source projects.
"""
import argparse,copy,fnmatch,hashlib,json,math,sys
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
from layout_constraints import number,vector,write_json,index

def load_profile(path):
 path=Path(path).resolve();p=json.loads(path.read_text());root=(path.parent/p.get('project_root','.')).resolve()
 if p.get('units')!='m':raise ValueError('Profile requires units=m')
 return p,root
def fingerprint(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def xyz_axis(v):
 d={'+X':(1,0,0),'-X':(-1,0,0),'+Y':(0,1,0),'-Y':(0,-1,0)}
 return Vector(d[v])
def parts_points(ob,deps):
 if ob.type!='MESH':raise ValueError('Geometry probe must select a mesh: '+ob.name)
 ev=ob.evaluated_get(deps);mesh=ev.to_mesh()
 try:return [ev.matrix_world@v.co for v in mesh.vertices]
 finally:ev.to_mesh_clear()
def bbox(pts):
 if not pts:raise ValueError('Empty geometry')
 return [min(p[k] for p in pts) for k in range(3)],[max(p[k] for p in pts) for k in range(3)]
def clone_root(src,name,scene):
 if src.type!='EMPTY':raise ValueError('Template root must be an EMPTY')
 objs=[src]+list(src.children_recursive)
 if any(o.type not in ['EMPTY','MESH'] or o.animation_data for o in objs):raise ValueError('Only static EMPTY/MESH templates are supported')
 mapping={}
 for o in objs:
  c=o.copy();c.name=name if o==src else name+'__'+o.name;scene.collection.objects.link(c);mapping[o]=c
 for o,c in mapping.items():
  if o!=src:c.parent=mapping[o.parent]
 return mapping[src]
def sync(profile,root,layout,scene):
 by=index(layout);details=[];seen=set()
 for binding in profile.get('bindings',[]):
  key=binding['instance_id'];a=by[key];name=binding['root'];seen.add(key);ob=scene.objects.get(name)
  if ob is None:
   src=scene.objects.get(binding.get('template_root',''))
   if not src:raise ValueError('Missing root/template: '+name)
   ob=clone_root(src,name,scene)
  if ob.type!='EMPTY' or ob.parent:raise ValueError('Instance roots must be unparented EMPTY objects: '+name)
  if binding.get('origin')!='bottom_center':raise ValueError('Explicit bottom_center origin contract required')
  forward=binding.get('source_forward');target=binding.get('layout_forward')
  if forward is None or target is None:raise ValueError('Declare source_forward and layout_forward after inspecting geometry')
  f=xyz_axis(forward);t=xyz_axis(target);adapt=math.atan2(t.y,t.x)-math.atan2(f.y,f.x)
  ob.rotation_mode='XYZ';ob.rotation_euler=(0,0,a.get('yaw',0)+adapt);ob.location=a['position']
  if binding.get('resize'):
   base=vector(binding['template_size_m'],True);axes=binding['layout_size_axes']
   if sorted(axes)!=[0,1,2]:raise ValueError('Size axes must be a permutation of XYZ indices')
   ob.scale=[a['size'][axes[k]]/base[k] for k in range(3)]
  if 'tilt_child' in binding:
   child=scene.objects[binding['tilt_child']]
   parent=child.parent
   while parent and parent!=ob:parent=parent.parent
   if parent!=ob:raise ValueError('Tilt child is outside bound instance')
   child.rotation_mode='XYZ';child.rotation_euler.x=a.get('tilt',0)
  ob['layout_instance_id']=key;ob['asset_id']=a['asset_id'];ob['table_instance_id']=a.get('table_instance_id','')
  details.append(dict(instance_id=key,root=ob.name,size_applied=bool(binding.get('resize')),yaw_adaptation_deg=math.degrees(adapt)))
 if not details:raise ValueError('No bindings configured')
 scene.view_layers[0].update()
 return dict(status='SYNCED',bindings=details,unbound_instances=sorted(set(by)-seen),limitations=['Only configured assets are synchronized','Size application is opt-in with explicit template dimensions/axes','Geometry QA must run after synchronization; metadata declarations alone are not validation'])
def chair_probe(ob,a,table,rule,scene,deps):
 matches=[c for c in ob.children_recursive if c.type=='MESH' and fnmatch.fnmatchcase(c.name,rule['mesh_pattern'])]
 if not matches:raise ValueError('No chair geometry matches '+rule['mesh_pattern'])
 world=[v for c in matches for v in parts_points(c,deps)];rot=ob.matrix_world.to_quaternion().to_matrix();local=[rot.transposed()@(p-ob.matrix_world.translation) for p in world];height=a['size'][2]
 def centroid(band):
  lo,hi=band;pts=[p for p in local if lo*height<=p.z<=hi*height]
  if not pts:raise ValueError('Probe height band has no vertices: '+ob.name)
  return rot@(sum(pts,Vector())/len(pts))+ob.matrix_world.translation
 back=centroid(rule['back_height_fraction']);seat=centroid(rule['seat_height_fraction']);front=seat-back;front.z=0
 if front.length<1e-6:raise ValueError('Seat/back cannot define a forward direction')
 front.normalize();tx,ty,tz=table['position'];w,d,h=table['size'];yaw=table.get('yaw',0);r=Matrix.Rotation(yaw,3,'Z');center=Vector((tx,ty,seat.z));ls=r.transposed()@(seat-center)
 target=Vector((max(-w/2,min(w/2,ls.x)),max(-d/2,min(d/2,ls.y)),0));toward=r@target+center-seat;toward.z=0
 if toward.length<1e-5:toward=r@Vector((0,-ls.y,0))
 if toward.length<1e-5:raise ValueError('Ambiguous seat at table center')
 toward.normalize()
 def distance(p):
  v=r.transposed()@(p-center);return math.hypot(max(-w/2-v.x,0,v.x-w/2),max(-d/2-v.y,0,v.y-d/2))
 dot=front.dot(toward);extra=distance(back)-distance(seat)
 return dict(root=ob.name,table_instance_id=a['table_instance_id'],front_dot=dot,back_extra_distance_m=extra,back_distance_m=distance(back),seat_distance_m=distance(seat),passes=dot>=rule['minimum_dot'] and extra>=rule['minimum_back_extra_m'])
def qa(profile,layout,scene,negative_probe=False):
 by=index(layout);deps=bpy.context.evaluated_depsgraph_get();rows=[];bindings={b['instance_id']:b for b in profile.get('bindings',[])}
 for rule in profile.get('qa',{}).get('chairs',[]):
  selected=[o for o in scene.objects if fnmatch.fnmatchcase(o.name,rule['root_pattern']) and o.type=='EMPTY'];checked=[]
  for ob in selected:
   key=ob.get('layout_instance_id')
   if key not in by:raise ValueError('Missing layout_instance_id binding: '+ob.name)
   a=by[key];table_id=a.get('table_instance_id')
   if table_id not in by:raise ValueError('Missing table binding: '+ob.name)
   checked.append(chair_probe(ob,a,by[table_id],rule,scene,deps))
  expected=rule['expected_count'];passes=len(checked)==expected and bool(checked) and all(x['passes'] for x in checked)
  row=dict(check='chairs_face_tables',status='PASS' if passes else 'FAIL',expected=expected,actual=len(checked),details=checked)
  if negative_probe and passes:
   ob=selected[0];saved=[(c,c.matrix_basis.copy()) for c in ob.children]
   try:
    for c,m in saved:c.matrix_basis=Matrix.Rotation(math.pi,4,'Z')@m
    scene.view_layers[0].update();a=by[ob['layout_instance_id']];reversed_result=chair_probe(ob,a,by[a['table_instance_id']],rule,scene,deps)
    if reversed_result['passes']:raise ValueError('Negative probe did not detect reversed chair')
    row['negative_probe']='REJECTED'
   finally:
    for c,m in saved:c.matrix_basis=m
    scene.view_layers[0].update()
  rows.append(row)
 for rule in profile.get('qa',{}).get('supports',[]):
  subject=scene.objects[rule['object']];surface=scene.objects[rule['surface']]
  if rule.get('surface_shape')!='rectangle':raise ValueError('Only explicit rectangular supports supported')
  axis=(surface.matrix_world.to_quaternion()@Vector((0,0,1))).normalized()
  if abs(axis.z)<.9999:raise ValueError('Support surface must be horizontal')
  sp=parts_points(surface,deps);op=parts_points(subject,deps);lo,hi=bbox(sp);olo,ohi=bbox(op);delta=olo[2]-hi[2];passed=abs(delta)<=rule['tolerance_m'] if rule.get('check_contact',True) else True;contains=None
  if rule.get('containment'):
   inv=surface.matrix_world.inverted();sl,sh=bbox([inv@v for v in sp]);ol,oh=bbox([inv@v for v in op]);eps=rule.get('edge_tolerance_local',1e-4);contains=all(ol[k]>=sl[k]-eps and oh[k]<=sh[k]+eps for k in [0,1]);passed=passed and contains
  rows.append(dict(check='support',object=subject.name,surface=surface.name,gap_m=delta,containment=contains,status='PASS' if passed else 'FAIL'))
 for rule in profile.get('qa',{}).get('parallel_panels',[]):
  a=scene.objects[rule['a']];b=scene.objects[rule['b']];axis=Vector(rule['normal_local']);na=(a.matrix_world.to_3x3().inverted().transposed()@axis).normalized();nb=(b.matrix_world.to_3x3().inverted().transposed()@axis).normalized();angle=math.degrees(math.acos(min(1,max(-1,na.dot(nb)))));rows.append(dict(check='panel_parallel',angle_deg=angle,status='PASS' if angle<=rule['max_angle_deg'] else 'FAIL'))
 for rule in profile.get('qa',{}).get('counts',[]):
  count=sum(fnmatch.fnmatchcase(o.name,rule['pattern']) and o.type==rule['type'] for o in scene.objects);rows.append(dict(check='count',pattern=rule['pattern'],actual=count,expected=rule['expected'],status='PASS' if count==rule['expected'] else 'FAIL'))
 if not rows:return dict(status='UNKNOWN',checks=[],limitations=['No geometry checks configured'])
 return dict(status='FAIL' if any(r['status']=='FAIL' for r in rows) else 'PASS',checks=rows,limitations=['Checks cover configured objects and metrics only, not full room collision, photometric truth or survey accuracy'])
def render(profile,root,scene,output):
 config=profile['render'];views=config['views'];out=Path(output)
 if not views:raise ValueError('No render views configured')
 for field in ['samples','width','height']:
  if isinstance(config[field],bool) or not isinstance(config[field],int) or config[field]<1:raise ValueError('Invalid '+field)
 if not 0<=number(config['adaptive_threshold'])<=1:raise ValueError('Invalid adaptive threshold')
 number(config['exposure'])
 if config.get('device') not in ['CPU','METAL']:raise ValueError('Device must be CPU or METAL')
 names=[]
 for view in views:
  s=bpy.data.scenes[view.get('scene',scene.name)]
  if s.objects[view['camera']].type!='CAMERA':raise ValueError('View does not reference a camera')
  name=view['file']
  if Path(name).name!=name or Path(name).suffix.lower()!='.png' or name in names:raise ValueError('Use unique simple PNG filenames')
  for key in ['width','height']:
   value=view.get(key,config[key])
   if isinstance(value,bool) or not isinstance(value,int) or value<1:raise ValueError('Invalid view '+key)
  names.append(name)
 if out.exists() and any(out.iterdir()):raise FileExistsError('Use a new render directory')
 out.mkdir(parents=True,exist_ok=True);manifest={'status':'RUNNING','blend_sha256':fingerprint(bpy.data.filepath),'layout_sha256':fingerprint(root/profile['layout']),'settings':copy.deepcopy(config),'views':[]}
 def save_manifest():
  temp=out/'manifest.json.tmp';temp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(out/'manifest.json')
 save_manifest()
 if config.get('device')=='METAL':
  prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='METAL';prefs.get_devices()
  if not any(d.type=='METAL' for d in prefs.devices):raise ValueError('Requested METAL GPU unavailable')
  for d in prefs.devices:d.use=d.type=='METAL'
 for view in views:
  s=bpy.data.scenes[view.get('scene',scene.name)];bpy.context.window.scene=s;s.camera=s.objects[view['camera']];s.render.engine='CYCLES';s.cycles.samples=config['samples'];s.cycles.use_denoising=True;s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=config['adaptive_threshold'];s.cycles.device='GPU' if config.get('device')=='METAL' else 'CPU'
  s.render.resolution_x=view.get('width',config['width']);s.render.resolution_y=view.get('height',config['height']);s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG'
  s.view_settings.view_transform=config['view_transform'];s.view_settings.look=config['look'];s.view_settings.exposure=config['exposure'];name=view['file']
  if Path(name).name!=name or Path(name).suffix.lower()!='.png':raise ValueError('View output must be a simple PNG filename')
  s.render.filepath=str(out/name);bpy.ops.render.render(write_still=True,scene=s.name);manifest['views'].append(dict(camera=s.camera.name,file=name,scene=s.name));save_manifest()
 manifest['status']='COMPLETE';save_manifest();return manifest
def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['sync','qa','render']);p.add_argument('--profile',required=True);p.add_argument('--output',required=True);p.add_argument('--negative-probe',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]);profile,root=load_profile(a.profile);layout_path=(root/profile['layout']).resolve();layout=json.loads(layout_path.read_text());index(layout)
 if layout.get('units')!='m':raise ValueError('Layout units must be m')
 scene=bpy.data.scenes[profile['scene']];bpy.context.window.scene=scene;scene.view_layers[0].update()
 if a.mode=='sync':
  output=Path(a.output).resolve()
  if output.exists() or Path(str(output)+'.sync.json').exists() or output==Path(bpy.data.filepath).resolve():raise FileExistsError('Sync writes a new .blend and new sidecar only')
  result=sync(profile,root,layout,scene);result['qa']=qa(profile,layout,scene,a.negative_probe)
  if result['qa']['status']!='PASS':raise ValueError('Refusing to save: configured geometry QA did not pass')
  result.update(layout_sha256=fingerprint(layout_path),profile_sha256=fingerprint(a.profile),source_blend_sha256=fingerprint(bpy.data.filepath));t=bpy.data.texts.get('RECONSTRUCTION_SYNC.json') or bpy.data.texts.new('RECONSTRUCTION_SYNC.json');t.clear();t.write(json.dumps(result,ensure_ascii=False,indent=2));output.parent.mkdir(parents=True,exist_ok=True);bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(output));write_json(str(output)+'.sync.json',result)
 elif a.mode=='qa':
  result=qa(profile,layout,scene,a.negative_probe);result.update(layout_sha256=fingerprint(layout_path),blend_sha256=fingerprint(bpy.data.filepath),profile_sha256=fingerprint(a.profile));write_json(a.output,result)
  if result['status']!='PASS':raise ValueError('Geometry QA '+result['status'])
 else:result=render(profile,root,scene,a.output)
 print(json.dumps({'status':result['status'],'mode':a.mode,'output':a.output}))
if __name__=='__main__':main()
