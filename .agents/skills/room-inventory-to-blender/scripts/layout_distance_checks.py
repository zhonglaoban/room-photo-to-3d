"""Check model dimensions and explicitly bound reference distances in Blender.
This module checks conformance, it does not infer photo distances or solve placement.
"""
import math
import bpy
from mathutils import Vector


def check_constraints(data):
    results=[]
    depsgraph=bpy.context.evaluated_depsgraph_get()
    def emit(cid,status,result,method,limitations=''):
        results.append(dict(id=cid,status=status,result=result,method=method,limitations=limitations))
    def interval(r):
        return isinstance(r,list) and len(r)==2 and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in r) and 0<=r[0]<=r[1]
    def bounds(name):
        obj=bpy.context.scene.objects.get(name)
        if obj is None or obj.type!='MESH':raise ValueError('Missing mesh: '+name)
        ev=obj.evaluated_get(depsgraph)
        mesh=ev.to_mesh()
        try:
            if not mesh.vertices:raise ValueError('Empty mesh: '+name)
            lo=Vector([min(v.co[i] for v in mesh.vertices) for i in range(3)])
            hi=Vector([max(v.co[i] for v in mesh.vertices) for i in range(3)])
            return ev.matrix_world.copy(),lo,hi
        finally:ev.to_mesh_clear()
    def anchor(a):
        matrix,lo,hi=bounds(a['object'])
        if a['mode']=='bbox_center':return matrix@((lo+hi)/2)
        if a['mode']!='local_point':raise ValueError('Unsupported anchor mode')
        p=a['local_point_m']
        if len(p)!=3 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in p):raise ValueError('Invalid local point')
        return matrix@Vector(p)
    def status_for(actual,r,target):
        target_ok=target is None or (isinstance(target,(int,float)) and math.isfinite(target) and r[0]<=target<=r[1])
        return 'PASS' if math.isfinite(actual) and r[0]-1e-6<=actual<=r[1]+1e-6 and target_ok else 'FAIL'
    mapped={b['asset_id']:set(b.get('objects',[])) for b in data.get('asset_bindings',[]) if b.get('disposition')!='omitted'}
    inventory=data.get('_inventory_source')
    if data.get('dimension_constraints') and inventory is None:
        emit('DIMENSION_SOURCE','FAIL','inventory_file is required','Read source inventory')
    for c in data.get('dimension_constraints',[]):
        cid='DIMENSION_'+c.get('asset_id','?')+'_'+c.get('source_dimension','?')
        try:
            if c['object'] not in mapped.get(c['asset_id'],set()):raise ValueError('Dimension object is not bound to source asset')
            a=next(a for a in inventory['assets'] if a['asset_id']==c['asset_id'])
            if inventory.get('units')!='m':raise ValueError('Inventory must use meters')
            r=a['dimensions']['ranges'][c['source_dimension']]
            if r is None:
                emit(cid,'UNKNOWN','Source size unknown','Read upstream size range');continue
            if not interval(r):raise ValueError('Invalid source size range')
            matrix,lo,hi=bounds(c['object'])
            axis='XYZ'.index(c['axis'])
            basis=[matrix.to_3x3().col[i] for i in range(3)]
            if any(abs(basis[i].normalized().dot(basis[j].normalized()))>1e-5 for i in range(3) for j in range(i)):
                emit(cid,'UNKNOWN','Sheared transform needs custom dimension method','Local axis extent');continue
            actual=(hi[axis]-lo[axis])*basis[axis].length
            target=c.get('target_m')
            emit(cid,status_for(actual,r,target),dict(range_m=r,target_m=target,actual_m=actual,deviation_from_target_m=actual-target if target is not None else None),
                 'Evaluated mesh extent along configured local axis, transformed scale', 'Selected object only; composite asset coverage requires manual verification')
        except (KeyError,TypeError,ValueError,StopIteration) as error:emit(cid,'FAIL',str(error),'Dimension source and geometry')
    source=data.get('_distance_source')
    if data.get('distance_constraints') and source is None:
        emit('DISTANCE_SOURCE','FAIL','distance_estimates_file is required','Read upstream distance estimates')
    if source is None:return results
    if inventory is None:
        emit('DISTANCE_INVENTORY','FAIL','inventory_file is required to trace asset IDs and original estimates','Source traceability')
    records=source['distances']
    ids=[d['distance_id'] for d in records]
    if len(ids)!=len(set(ids)):
        emit('DISTANCE_SOURCE','FAIL','Duplicate source distance IDs','Unique source identity');return results
    if inventory is not None and inventory.get('distance_estimates')!=records:
        emit('DISTANCE_SOURCE','FAIL','Inventory and distance file disagree','Exact upstream record comparison')
    bindings=data.get('distance_constraints',[])
    for c in bindings:
        if c['source_distance_id'] not in ids:emit('DISTANCE_'+c['source_distance_id'],'FAIL','Unknown source ID','Source identity')
    for d in records:
        cid='DISTANCE_'+d['distance_id']
        linked=[c for c in bindings if c['source_distance_id']==d['distance_id']]
        if d.get('status') not in ('estimated','measured','unknown'):
            emit(cid,'FAIL','Invalid source status','Source schema');continue
        if d['status']=='unknown':
            if d['range_m'] is not None or any(c.get('state')=='applied' for c in linked):
                emit(cid,'FAIL','Unknown source cannot have numeric range or an applied estimate','Source status')
            else:emit(cid,'UNKNOWN','No metric estimate available; preserve modeling assumption','Source status')
            continue
        if len(linked)!=1:
            emit(cid,'FAIL','Expected exactly one explicit consumption binding','Source coverage');continue
        c=linked[0]
        if c.get('state')=='unresolved' and not c.get('reason'):
            emit(cid,'FAIL','Unresolved constraint needs a reason','Explicit application state');continue
        if c.get('state')=='unresolved' or d.get('conflict_group'):
            emit(cid,'WARN',c.get('reason') or 'Conflicting source intervals','Explicit unresolved constraint');continue
        try:
            if c.get('state')!='applied':raise ValueError('Invalid application state')
            r=d['range_m']
            if not interval(r) or d.get('scale_reference',{}).get('kind') not in ('measured_anchor','documented_product','assumed_typical_size'):raise ValueError('Numeric source requires interval and scale reference')
            metric=d['metric']
            aa,bb=c['subject_anchor'],c['object_anchor']
            if aa['object'] not in mapped.get(d['subject_asset_id'],set()) or bb['object'] not in mapped.get(d['object_asset_id'],set()):raise ValueError('Anchor object is not bound to source asset')
            if metric=='center_distance_xy' and (aa['mode']!='bbox_center' or bb['mode']!='bbox_center'):raise ValueError('Center distance requires bbox_center anchors')
            p,q=anchor(aa),anchor(bb)
            if metric in ('reference_distance_xy','center_distance_xy'):actual=math.hypot(q.x-p.x,q.y-p.y)
            elif metric=='vertical_gap':actual=q.z-p.z
            else:raise ValueError('Unsupported source metric')
            target=c.get('selected_target_m')
            emit(cid,status_for(actual,r,target),dict(metric=metric,range_m=r,target_m=target,actual_m=actual,deviation_from_target_m=actual-target if target is not None else None),
                 'Upstream metric with matrix_world-transformed anchors','Not photo truth, minimum surface clearance or full-path clearance; reference feature mapping requires visual verification')
        except (KeyError,TypeError,ValueError) as error:emit(cid,'FAIL',str(error),'Distance geometry and metric binding')
    return results
