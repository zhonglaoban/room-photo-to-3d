"""Validate distance records, not the truth of photo-based estimates."""
import json
import math
import sys
from pathlib import Path


def interval(value):
    return (isinstance(value, list) and len(value) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value)
            and 0 <= value[0] <= value[1])


def validate_records(records, inventory):
    assets = {a['asset_id'] for a in inventory['assets']}
    images = {i['image_id']: i for i in inventory['images']}
    seen = set()
    for d in records:
        label = d.get('distance_id')
        def require(ok, msg):
            if not ok:
                raise ValueError(f'{label}: {msg}')
        require(isinstance(label, str) and label and label not in seen, 'distance_id missing/duplicate')
        seen.add(label)
        require(d['subject_asset_id'] in assets and d['object_asset_id'] in assets, 'unknown asset')
        require(d['subject_asset_id'] != d['object_asset_id'], 'self distance')
        require(d['metric'] in ('reference_distance_xy', 'center_distance_xy', 'vertical_gap'), 'unknown metric')
        require(bool(d['subject_reference']) and bool(d['object_reference']), 'reference features missing')
        require(d['status'] in ('estimated', 'measured', 'unknown'), 'bad status')
        require(d['confidence'] in ('low', 'medium', 'high', 'unknown'), 'bad confidence')
        require(bool(d['basis']), 'missing basis')
        require(d['provenance'] in ('observed', 'inferred', 'measured'), 'bad provenance')
        require(d['method'] in ('coplanar_ratio', 'rectified_floor', 'visual_range', 'direct_measurement', 'unknown'), 'bad method')
        evidence = d['evidence_image_ids']
        require(isinstance(evidence, list) and all(i in images and images[i]['status'] == 'downloaded' for i in evidence), 'invalid/unavailable evidence')
        if d['status'] == 'unknown':
            require(d['range_m'] is None, 'unknown distance must have null range')
        else:
            require(interval(d['range_m']), 'invalid metric interval')
            scale = d['scale_reference']
            require(scale['kind'] in ('measured_anchor','documented_product','assumed_typical_size'), 'numeric estimate requires scale')
            require(interval(scale['range_m']) and scale['range_m'][0] > 0 and bool(scale['source']) and bool(scale['description']), 'invalid scale reference')
            if d['status'] == 'estimated':
                require(bool(evidence) and d['confidence'] == 'low', 'photo estimates need evidence and low confidence')
                require(d['provenance'] == 'inferred' and d['method'] not in ('unknown','direct_measurement'), 'photo estimate marked as observation/measurement')
            else:
                require(d['method'] == 'direct_measurement' and d['provenance'] == 'measured' and bool(d.get('measurement_source')), 'measured data requires actual measurement source')
    for image in inventory.get('image_spatial_relations', []):
        for relation in image['relationships']:
            for distance_id in relation.get('distance_ids', []):
                require_ref = next((d for d in records if d['distance_id'] == distance_id), None)
                if require_ref is None:
                    raise ValueError(f'Unknown distance reference: {distance_id}')
                if {relation['subject_asset_id'],relation['object_asset_id']} != {require_ref['subject_asset_id'],require_ref['object_asset_id']}:
                    raise ValueError(f'Pair mismatch for {distance_id}')
    return len(records)


def validate_folder(folder):
    folder = Path(folder)
    inventory = json.loads((folder/'objects.json').read_text(encoding='utf-8'))
    sidecar = folder/'furniture-distances.json'
    present = 'distance_estimates' in inventory
    if not present and not sidecar.exists():
        print('DISTANCES_UNKNOWN: legacy inventory has no distance analysis')
        return None
    if not present or not sidecar.exists():
        raise ValueError('Both objects.json.distance_estimates and furniture-distances.json are required')
    data = json.loads(sidecar.read_text(encoding='utf-8'))
    if data.get('units') != 'm' or data.get('room_id') != inventory['room_id']:
        raise ValueError('Distance units/room mismatch')
    if data['distances'] != inventory['distance_estimates']:
        raise ValueError('Distance sidecar and inventory differ')
    count = validate_records(data['distances'], inventory)
    print(f'DISTANCES_PASS: {count} records; metadata validated, photo accuracy not certified')
    return count

if __name__ == '__main__':
    validate_folder(sys.argv[1])
