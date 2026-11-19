"""Isolated second-room fixture. Never run interactively in a user's scene."""
import bpy,json,math,sys
from pathlib import Path
from mathutils import Vector
out=Path(sys.argv[sys.argv.index('--')+1]);out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);s=bpy.context.scene;s.name='SecondRoom';s.unit_settings.system='METRIC'
def root(name):o=bpy.data.objects.new(name,None);s.collection.objects.link(o);return o
def cube(name,pos,size,parent=None):
 bpy.ops.mesh.primitive_cube_add(size=1,location=pos);o=bpy.context.object;o.name=name;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.parent=parent;return o
desk=root('ASSET_surface');cube('Top',(0,0,.745),(1.8,.9,.05),desk)
proto=root('PROTO_seat');cube('FixtureSeatShell_Back',(0,-.25,.75),(.46,.04,.30),proto);cube('FixtureSeatShell_Seat',(0,0,.45),(.46,.44,.04),proto)
cube('Support_Top',(5,5,.775),(1,1,.05));cube('Device_Base',(5,5,.85),(.3,.3,.1));cube('Device_Floating',(5,5,1.10),(.3,.3,.1))
theta=math.radians(37);t=[2.7,3.4,0];assets=[dict(instance_id='island',asset_id='DESK',kind='solid',position=t,size=[1.8,.9,.77],yaw=theta)]
for j,side in enumerate([-1,1]):
 v=side*.65;assets.append(dict(instance_id='seat_'+str(j),asset_id='SEAT',kind='chair',position=[t[0]-v*math.sin(theta),t[1]+v*math.cos(theta),0],size=[.46,.44,.9],yaw=theta+(0 if side==-1 else math.pi),table_instance_id='island'))
(out/'layout.json').write_text(json.dumps(dict(units='m',assets=assets)))
cd=bpy.data.cameras.new('TestCamera');cam=bpy.data.objects.new('TestCamera',cd);s.collection.objects.link(cam);cam.location=(5,-2,4);cam.rotation_euler=(Vector((2.7,3.4,.5))-cam.location).to_track_quat('-Z','Y').to_euler();s.camera=cam
ld=bpy.data.lights.new('TestLight','AREA');ld.energy=700;light=bpy.data.objects.new('TestLight',ld);s.collection.objects.link(light);light.location=(2,2,6)
bindings=[dict(instance_id='island',root='ASSET_surface',origin='bottom_center',source_forward='+Y',layout_forward='+Y',resize=False)]+[dict(instance_id='seat_'+str(j),root='ASSET_seat_'+str(j),template_root='PROTO_seat',origin='bottom_center',source_forward='+Y',layout_forward='+Y',resize=False) for j in range(2)]
profile=dict(units='m',project_root='.',layout='layout.json',scene='SecondRoom',bindings=bindings,qa=dict(chairs=[dict(root_pattern='ASSET_seat_*',expected_count=2,mesh_pattern='*FixtureSeatShell*',back_height_fraction=[.8,1.01],seat_height_fraction=[.47,.53],minimum_dot=.90,minimum_back_extra_m=.15)],supports=[dict(object='Device_Base',surface='Support_Top',surface_shape='rectangle',tolerance_m=.001,containment=True)],counts=[dict(pattern='ASSET_seat_*',type='EMPTY',expected=2)]),render=dict(samples=1,adaptive_threshold=.1,width=128,height=96,view_transform='AgX',look='AgX - Medium High Contrast',exposure=0,device='CPU',views=[dict(camera='TestCamera',file='test.png')]))
(out/'profile.json').write_text(json.dumps(profile));bpy.ops.wm.save_as_mainfile(filepath=str(out/'source.blend'));print('SECOND_ROOM_FIXTURE_READY')
