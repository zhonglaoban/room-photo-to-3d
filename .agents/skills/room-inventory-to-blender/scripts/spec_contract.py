"""Small shared parser; no Blender import required."""
import json
import math
from pathlib import Path


def read_spec(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('units') != 'm' or data.get('coordinate_frame') != 'blender_xyz_z_up':
        raise ValueError('Expected meters and Blender XYZ Z-up')
    room = data['main_room']
    lo, hi = room['bounds_min'], room['bounds_max']
    if len(lo) != 3 or len(hi) != 3 or not all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        for v in lo + hi
    ) or not all(a < b for a, b in zip(lo, hi)):
        raise ValueError('Invalid inner room bounds')
    thickness = room['wall_thickness_m']
    if not isinstance(thickness, (int, float)) or not math.isfinite(thickness) or thickness <= 0:
        raise ValueError('Invalid wall thickness')
    camera = data['central_camera']
    if camera['mode'] not in ('human_eye', 'geometric_center'):
        raise ValueError('Unsupported camera mode')
    eye = camera['eye_height_m']
    if not math.isfinite(eye) or not 0 < eye < hi[2] - lo[2]:
        raise ValueError('Eye height must be inside the room')
    names = data['envelope_objects']
    if not names or len(names) != len(set(names)):
        raise ValueError('Envelope names must be nonempty and unique')
    import hashlib
    for field, key in [('inventory_file', '_inventory_source'), ('distance_estimates_file', '_distance_source')]:
        if data.get(field):
            source_path = (Path(path).resolve().parent / data[field]).resolve()
            raw = source_path.read_bytes()
            source = json.loads(raw)
            if source.get('room_id') != data['room_id'] or source.get('units') != 'm':
                raise ValueError('Source room/units mismatch: ' + field)
            data[key] = source
            data.setdefault('_source_hashes', {})[field] = hashlib.sha256(raw).hexdigest()
    return data


def camera_position(data):
    lo, hi = data['main_room']['bounds_min'], data['main_room']['bounds_max']
    z = ((lo[2] + hi[2]) / 2 if data['central_camera']['mode'] == 'geometric_center'
         else lo[2] + data['central_camera']['eye_height_m'])
    return ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, z)
