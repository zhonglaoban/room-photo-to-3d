"""Create a NEW rectangular six-sided baseline, never patch an existing model.
Run in a standalone Blender --background --factory-startup process.
"""
import argparse
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_contract import read_spec, camera_position


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = Path(args.output).resolve()
    if output.exists() or output.suffix != '.blend':
        raise ValueError('Output must be a new .blend file')
    data = read_spec(args.config)
    expected = {'SM_Wall_North', 'SM_Wall_South', 'SM_Wall_East', 'SM_Wall_West', 'SM_Floor', 'SM_Ceiling'}
    if set(data['envelope_objects']) != expected or data.get('openings') or data.get('asset_bindings'):
        raise ValueError('Baseline builder requires default six slab names, no openings or furniture bindings')
    # New scene, not a delete-all operation on the current scene.
    scene = bpy.data.scenes.new('Room_Complete')
    if bpy.context.window:
        bpy.context.window.scene = scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    cols = {}
    for name in ['Envelope', 'Furniture', 'Openings', 'Cameras', 'Lights', 'References']:
        c = bpy.data.collections.new('COL_' + name)
        scene.collection.children.link(c)
        cols[name] = c
    mat = bpy.data.materials.new('MAT_Warm_Plaster')
    mat.diffuse_color = (.76, .73, .67, 1)
    mat.use_nodes = True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = mat.diffuse_color
    mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .8
    lo, hi = data['main_room']['bounds_min'], data['main_room']['bounds_max']
    x, y, z = [(a + b) / 2 for a, b in zip(lo, hi)]
    w, d, h = [b - a for a, b in zip(lo, hi)]
    t = data['main_room']['wall_thickness_m']
    def slab(name, location, size):
        # Closed outward-facing solid box, including its interior-facing side.
        vs = [(location[0]+a*size[0]/2, location[1]+b*size[1]/2, location[2]+c*size[2]/2)
              for a,b,c in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]]
        faces = [(0,2,6,4),(1,5,7,3),(0,4,5,1),(2,3,7,6),(0,1,3,2),(4,6,7,5)]
        mesh = bpy.data.meshes.new(name + '_Mesh')
        mesh.from_pydata(vs, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        cols['Envelope'].objects.link(obj)
        obj['room_role'] = 'envelope'
        mesh.materials.append(mat)
    slab('SM_Wall_North', (x, hi[1]+t/2, z), (w+2*t,t,h))
    slab('SM_Wall_South', (x, lo[1]-t/2, z), (w+2*t,t,h))
    slab('SM_Wall_East', (hi[0]+t/2, y, z), (t,d,h))
    slab('SM_Wall_West', (lo[0]-t/2, y, z), (t,d,h))
    slab('SM_Floor', (x,y,lo[2]-t/2), (w+2*t,d+2*t,t))
    slab('SM_Ceiling', (x,y,hi[2]+t/2), (w+2*t,d+2*t,t))
    center = camera_position(data)
    def camera(name, degrees):
        camdata = bpy.data.cameras.new(name)
        obj = bpy.data.objects.new(name, camdata)
        cols['Cameras'].objects.link(obj)
        obj.location = center
        a = math.radians(degrees)
        obj.rotation_euler = Vector((-math.sin(a), math.cos(a), 0)).to_track_quat('-Z','Y').to_euler()
        camdata.lens = 26
        camdata.clip_start = .04
        camdata.clip_end = 100
        return obj
    scene.camera = camera(data['central_camera']['name'], data['central_camera']['heading_degrees'])
    for name, deg in [('North',0),('East',270),('South',180),('West',90)]:
        camera('CAM_Center_'+name, deg)
    lightdata = bpy.data.lights.new('LGT_Ceiling', 'AREA')
    lightdata.energy = 400
    lightdata.shape = 'DISK'
    lightdata.size = min(w,d)*.6
    light = bpy.data.objects.new(lightdata.name, lightdata)
    cols['Lights'].objects.link(light)
    light.location = (x,y,hi[2]-.15)
    scene.world = bpy.data.worlds.new('World_Room')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .15
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 16
    scene.render.resolution_x = 800
    scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    scene['room_id'] = data['room_id']
    scene['model_kind'] = 'assumed_empty_shell_baseline'
    bpy.data.texts.new('SCENE_SPEC.json').write(json.dumps(data,ensure_ascii=False,indent=2))
    bpy.data.texts.new('START_HERE').write('空壳基线；尚无照片布局、家具、门窗。完整外壳，默认中央人眼相机。')
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    print('SHELL_CREATED', output)

if __name__ == '__main__':
    main()
