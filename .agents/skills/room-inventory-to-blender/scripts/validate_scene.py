"""Read-only scene checks. Sampling detects gross gaps, not watertightness.
Run: blender -b model.blend --python validate_scene.py -- --config spec.json --output new.json
"""
import argparse
import itertools
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_contract import read_spec, camera_position
from layout_distance_checks import check_constraints


def validate(data):
    scene = bpy.context.scene
    layer = bpy.context.view_layer
    checks = []
    def record(cid, ok, result, method, limitations=''):
        checks.append(dict(id=cid,status='PASS' if ok else 'FAIL',result=result,method=method,limitations=limitations))
    record('UNITS', scene.unit_settings.system == 'METRIC' and abs(scene.unit_settings.scale_length-1)<1e-6,
           str((scene.unit_settings.system,scene.unit_settings.scale_length)), 'Scene unit settings')
    target = Vector(camera_position(data))
    cam = bpy.data.objects.get(data['central_camera']['name'])
    ok = cam is not None and cam.type == 'CAMERA'
    record('CENTER_CAMERA',ok and (cam.matrix_world.translation-target).length < .001 and scene.camera == cam,
           {'expected':list(target),'actual':list(cam.matrix_world.translation) if ok else None,'active':scene.camera.name if scene.camera else None},
           'World XYZ distance < 1 mm, expected central camera active', 'Does not check furniture clearance')
    hidden_layer_cols=set()
    def scan(lc, inherited=False):
        hidden=inherited or lc.exclude or lc.hide_viewport or lc.collection.hide_render or lc.collection.hide_viewport
        if hidden:hidden_layer_cols.add(lc.collection.name)
        for child in lc.children:scan(child,hidden)
    scan(layer.layer_collection)
    vertices, faces = [], []
    depsgraph=bpy.context.evaluated_depsgraph_get()
    for name in data['envelope_objects']:
        obj=bpy.data.objects.get(name)
        if obj is None or obj.type != 'MESH':
            record('ENVELOPE_'+name,False,'Missing mesh','Configuration name lookup')
            continue
        visible=(not obj.hide_render and not obj.hide_viewport and not obj.hide_get(view_layer=layer)
                 and obj.visible_get(view_layer=layer)
                 and getattr(obj,'visible_camera',True)
                 and any(c.name not in hidden_layer_cols for c in obj.users_collection))
        ev=obj.evaluated_get(depsgraph)
        mesh=ev.to_mesh()
        good=bool(mesh.vertices and mesh.polygons)
        record('ENVELOPE_'+name, visible and good,{'visible':bool(visible),'vertices':len(mesh.vertices),'faces':len(mesh.polygons)},
               'Object / ancestor collection / active View Layer visibility and evaluated mesh')
        if visible and good:
            offset=len(vertices)
            vertices.extend(ev.matrix_world@v.co for v in mesh.vertices)
            faces.extend(tuple(offset+i for i in poly.vertices) for poly in mesh.polygons)
        ev.to_mesh_clear()
    if vertices and faces:
        tree=BVHTree.FromPolygons(vertices,faces,all_triangles=False)
        lo,hi=data['main_room']['bounds_min'],data['main_room']['bounds_max']
        distance=2*Vector([b-a for a,b in zip(lo,hi)]).length
        directions=[Vector(d).normalized() for d in itertools.product([-1,0,1], repeat=3) if d!=(0,0,0)]
        gaps=[]
        total=0
        for u,v,w in itertools.product([.15,.5,.85],[.15,.5,.85],[.1,.3,.5,.7,.9]):
            origin=Vector([lo[i]+f*(hi[i]-lo[i]) for i,f in enumerate([u,v,w])])
            for direction in directions:
                total+=1
                hit=tree.ray_cast(origin,direction,distance)[0]
                if hit is None and len(gaps)<12:gaps.append({'origin':list(origin),'direction':list(direction)})
        record('SAMPLED_ENCLOSURE',not gaps,{'rays':total,'gap_examples':gaps},
               '45 interior sample points × 26 directions against visible envelope only',
               'Rectangular main-room sampling; not a continuous watertightness, normals, opening-shape or multi-room certification')
    else:
        record('SAMPLED_ENCLOSURE',False,'No visible envelope geometry','BVH unavailable')
    for binding in data.get('asset_bindings',[]):
        omitted=binding.get('disposition')=='omitted'
        names=binding.get('objects',[])
        valid=bool(binding.get('reason')) if omitted else bool(names) and all(scene.objects.get(n) is not None for n in names)
        record('ASSET_'+binding['asset_id'],valid,{'disposition':binding.get('disposition'),'objects':names},
               'Explicit modeled object mapping or documented omission','Does not verify identity, photo evidence, shape or count against upstream inventory')
    unpacked=[im.filepath for im in bpy.data.images if im.source=='FILE' and not im.packed_file]
    record('PACKED_IMAGES',not unpacked,unpacked,'FILE image datablocks packed','Other linked libraries/fonts/caches require separate checks')
    checks.extend(check_constraints(data))
    not_checked = []
    if not data.get('_distance_source'):not_checked.append('distance_constraints_no_source')
    if not data.get('dimension_constraints'):not_checked.append('asset_dimensions_no_bindings')
    return {'source_sha256':data.get('_source_hashes',{}),'schema_version':'1.0','room_id':data['room_id'],'file':bpy.data.filepath,
            'overall':'FAIL' if any(c['status']=='FAIL' for c in checks) else ('WARN_LIMITED_CHECKS' if any(c['status'] in ('WARN','UNKNOWN') for c in checks) else 'PASS_LIMITED_CHECKS'),
            'checks':checks,'not_checked':not_checked+['photo_match','furniture_camera_clearance','walkability','true_window_openings','continuous_enclosure','all_external_dependencies']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    output=Path(args.output).resolve()
    if output.exists():raise ValueError('Use a new validation output path')
    result=validate(read_spec(args.config))
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('ROOM_VALIDATION',result['overall'],str(output))

if __name__=='__main__':
    main()
