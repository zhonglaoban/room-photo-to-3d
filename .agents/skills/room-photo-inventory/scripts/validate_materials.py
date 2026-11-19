"""Validate photo-material evidence and handoff consistency, not photographic truth.
Pure standard library. Explicit UNKNOWN is retained; unsupported pattern changes fail.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

PATTERNS = {'straight_grain', 'wavy_grain', 'ring_grain', 'weave', 'speckled', 'veined', 'plain', 'geometric', 'other', 'unknown'}
CONFIDENCE = {'low', 'medium', 'high', 'unknown'}
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')

def finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

def interval(v):
    return isinstance(v, list) and len(v) == 2 and all(finite(n) for n in v) and 0 < v[0] <= v[1]

def validate_records(inventory, observations, spec):
    errors, warnings, checks = [], [], []
    def check(name, condition, message):
        checks.append({'name': name, 'status': 'PASS' if condition else 'FAIL', 'result': message})
        if not condition: errors.append(message)
    assets = {a['asset_id']: a for a in inventory.get('assets', [])}
    images = {i['image_id']: i for i in inventory.get('images', [])}
    check('schema_room', observations.get('schema_version') == spec.get('schema_version') == '1.0'
          and observations.get('room_id') == spec.get('room_id') == inventory.get('room_id')
          and observations.get('color_space') == 'sRGB', 'Material schema, room ID and sRGB declaration must match')
    obs_list, mats = observations.get('observations'), spec.get('materials')
    check('arrays', isinstance(obs_list, list) and isinstance(mats, list) and bool(mats), 'Material arrays required; material list cannot be empty')
    obs_list = obs_list if isinstance(obs_list, list) else []
    mats = mats if isinstance(mats, list) else []
    lookup = {}
    for o in obs_list:
        oid = o.get('observation_id'); aid = o.get('asset_id'); iid = o.get('image_id')
        check(str(oid)+':identity', bool(oid) and oid not in lookup and aid in assets and bool(o.get('surface_id')),
              f'{oid}: unique observation ID, asset and surface required')
        lookup[oid] = o
        check(str(oid)+':image', iid in images and images[iid].get('status') == 'downloaded'
              and iid in assets.get(aid, {}).get('evidence_image_ids', []), f'{oid}: evidence must be a downloaded source image of this asset')
        region = o.get('region', {}); method = region.get('method'); bbox = region.get('bbox_normalized')
        check(str(oid)+':region', bool(region.get('description')) and ((method == 'visual_only' and bbox is None)
              or (method == 'annotated_bbox' and isinstance(bbox, list) and len(bbox) == 4
                  and all(finite(v) and 0 <= v <= 1 for v in bbox) and bbox[0] < bbox[2] and bbox[1] < bbox[3])),
              f'{oid}: declare visual-only evidence or a real normalized annotated rectangle')
        color = o.get('color', {}); palette = color.get('approx_hex')
        check(str(oid)+':color', color.get('method') in {'visual_estimate', 'roi_statistics', 'unknown'}
              and isinstance(palette, list) and all(isinstance(h, str) and HEX.fullmatch(h) for h in palette)
              and bool(color.get('description')) and bool(color.get('lighting'))
              and bool(color.get('bias_notes')) and color.get('confidence') in CONFIDENCE,
              f'{oid}: color encoding, method, lighting bias and confidence required')
        if color.get('method') == 'unknown':
            check(str(oid)+':unknown_color', palette == [] and color.get('confidence') == 'unknown', f'{oid}: unknown color cannot claim a palette or certainty')
        else:
            check(str(oid)+':known_color', bool(palette), f'{oid}: observed color requires at least one approximate swatch')
        if color.get('method') == 'roi_statistics':
            n = color.get('sample_count')
            check(str(oid)+':roi', method == 'annotated_bbox' and isinstance(n, int) and not isinstance(n, bool) and n > 0,
                  f'{oid}: ROI statistics need an actual region and positive sample count')
        texture = o.get('texture', {})
        check(str(oid)+':texture', texture.get('pattern') in PATTERNS and texture.get('contrast') in {'low', 'medium', 'high', 'unknown'}
              and bool(texture.get('material_appearance')) and bool(texture.get('direction_in_image'))
              and bool(texture.get('finish_appearance')) and texture.get('confidence') in CONFIDENCE,
              f'{oid}: texture pattern, direction, contrast and appearance required')
        scale = texture.get('scale_range_m')
        check(str(oid)+':scale', scale is None or (interval(scale) and bool(texture.get('scale_basis'))), f'{oid}: numerical texture scale needs a positive interval and basis')
    seen, surfaces, coverage, visual = set(), set(), {aid: set() for aid in assets}, []
    for m in mats:
        mid = m.get('material_id'); aid = m.get('asset_id'); surface = m.get('surface_id')
        check(str(mid)+':identity', bool(mid) and mid not in seen and aid in assets and bool(surface) and (aid, surface) not in surfaces,
              f'{mid}: unique material and asset surface required')
        seen.add(mid); surfaces.add((aid, surface))
        if aid in coverage: coverage[aid].add(mid)
        refs = m.get('evidence_observation_ids', [])
        matched = [lookup[oid] for oid in refs if oid in lookup]
        check(str(mid)+':evidence', isinstance(refs, list) and len(refs) == len(set(refs)) and len(matched) == len(refs)
              and all(o['asset_id'] == aid and o['surface_id'] == surface for o in matched), f'{mid}: evidence must refer to this asset and surface')
        color = m.get('base_color', {}); tex = m.get('texture', {}); cross = m.get('cross_view', {})
        check(str(mid)+':base_color', color.get('status') in {'modeling_assumption', 'unknown'} and bool(color.get('basis'))
              and ((color.get('status') == 'unknown' and color.get('target_srgb_hex') is None)
                   or (color.get('status') == 'modeling_assumption' and isinstance(color.get('target_srgb_hex'), str)
                       and HEX.fullmatch(color['target_srgb_hex']))), f'{mid}: candidate color must be an explicit assumption or unknown, never measured from an ordinary photo')
        allowed = color.get('allowed_srgb_range')
        if color.get('status') == 'modeling_assumption':
            valid_range = isinstance(allowed, list) and len(allowed) == 3 and all(isinstance(r, list) and len(r) == 2
                          and all(finite(v) and 0 <= v <= 255 for v in r) and r[0] <= r[1] for r in allowed)
            check(str(mid)+':color_range', valid_range and bool(color.get('range_basis')), f'{mid}: define a per-surface candidate sRGB range and its assumption basis')
            target = color.get('target_srgb_hex')
            if valid_range and isinstance(target, str) and HEX.fullmatch(target):
                rgb = [int(target[i:i+2], 16) for i in (1, 3, 5)]
                check(str(mid)+':color_in_range', all(allowed[i][0] <= rgb[i] <= allowed[i][1] for i in range(3)), f'{mid}: selected color is outside the evidence-reviewed candidate range')
        else:
            check(str(mid)+':unknown_color_range', allowed is None, f'{mid}: unknown color cannot invent a numeric acceptance range')
        check(str(mid)+':texture', tex.get('pattern') in PATTERNS and tex.get('contrast') in {'low', 'medium', 'high', 'unknown'}
              and bool(tex.get('direction_basis')) and tex.get('relief') in {'flat', 'micro', 'visible_relief', 'unknown'}
              and bool(tex.get('relief_basis')) and (tex.get('scale_range_m') is None or (interval(tex['scale_range_m']) and bool(tex.get('scale_basis')))),
              f'{mid}: explicit texture choice, direction, relief and scale basis required')
        excluded = cross.get('excluded_observation_ids', [])
        check(str(mid)+':excluded', isinstance(excluded, list) and set(excluded) <= set(refs)
              and (not excluded or bool(cross.get('exclusion_reason'))), f'{mid}: excluding evidence requires an explicit reason')
        check(str(mid)+':cross_view', cross.get('status') in {'consistent', 'single_view', 'conflict', 'unknown'} and bool(cross.get('basis')),
              f'{mid}: cross-view result and selection basis required')
        active = [o for o in matched if o['observation_id'] not in excluded]
        # Different IDs for the same uploaded bytes are still one source view.
        active_images = {images[o['image_id']].get('_material_source_sha256') or images[o['image_id']].get('sha256')
                         or images[o['image_id']].get('file') or o['image_id'] for o in active if o['image_id'] in images}
        if cross.get('status') == 'consistent':
            check(str(mid)+':multiple_views', len(active_images) >= 2 and not cross.get('conflicts'), f'{mid}: consistency needs at least two distinct usable views without unresolved conflicts')
        if cross.get('status') == 'single_view':
            check(str(mid)+':single_view', len(active_images) == 1, f'{mid}: single-view result must refer to exactly one usable image')
        if cross.get('status') == 'conflict':
            check(str(mid)+':conflicts', bool(cross.get('conflicts')), f'{mid}: conflict result must retain its conflict descriptions')
            warnings.append(f'{mid}: cross-view appearance conflict remains unresolved')
        # All observations of this same surface must participate, including explicit exclusions.
        all_surface = {oid for oid, o in lookup.items() if o.get('asset_id') == aid and o.get('surface_id') == surface}
        check(str(mid)+':complete_evidence', set(refs) == all_surface, f'{mid}: include all surface observations; do not hide conflicting views')
        known = {o.get('texture', {}).get('pattern') for o in active} - {'unknown', None}
        override = m.get('design_override', {})
        override_ok = override.get('source') == 'user' and bool(override.get('reason'))
        check(str(mid)+':pattern_evidence', not known or tex.get('pattern') == 'unknown' or tex.get('pattern') in known or override_ok,
              f'{mid}: selected pattern is unsupported by the photos; a design change needs an actual user override')
        if len(known) > 1 and not override_ok and cross.get('status') != 'conflict':
            check(str(mid)+':pattern_conflict', False, f'{mid}: incompatible observed patterns must be reviewed as a conflict')
        if not refs:
            check(str(mid)+':unseen', color.get('status') == 'unknown' and tex.get('pattern') == 'unknown' and cross.get('status') == 'unknown', f'{mid}: unseen surfaces must remain unknown')
        reviews = m.get('review_checks', [])
        names = [c.get('name') for c in reviews]
        check(str(mid)+':review_coverage', {'color_consensus', 'pattern_match', 'lighting_bias'} <= set(names) and len(names) == len(set(names)), f'{mid}: separate color, pattern and lighting reviews required')
        for review in reviews:
            status = review.get('status'); visual.append(status)
            check(str(mid)+':review_record', status in {'PASS', 'WARN', 'UNKNOWN', 'FAIL'} and bool(review.get('method')) and bool(review.get('notes')), f'{mid}: reviews need actual methods, outcomes and notes')
            if status == 'FAIL': errors.append(f'{mid}: visual review failed: '+str(review.get('name')))
            if review.get('name') == 'color_consensus' and status == 'PASS':
                check(str(mid)+':color_consensus', len(active_images) >= 2 and cross.get('status') == 'consistent', f'{mid}: a single view or unresolved conflict cannot certify cross-view color consistency')
        if color.get('status') == 'unknown' or tex.get('pattern') == 'unknown' or cross.get('status') in {'single_view', 'conflict', 'unknown'}:
            warnings.append(f'{mid}: appearance remains partially unknown or not cross-validated')
    for aid, asset in assets.items():
        check(aid+':coverage', bool(coverage[aid]) and set(asset.get('appearance', {}).get('material_ids', [])) == coverage[aid], f'{aid}: all assets need matching appearance.material_ids, including unknown surfaces')
    visual_status = 'FAIL' if 'FAIL' in visual else 'UNKNOWN' if warnings or any(s in {'UNKNOWN', 'WARN'} for s in visual) or not visual else 'REVIEWED'
    return {'schema_version': '1.0', 'room_id': inventory.get('room_id'), 'overall': 'FAIL' if errors else 'WARN' if visual_status != 'REVIEWED' else 'PASS',
            'structural_status': 'FAIL' if any(c['status'] == 'FAIL' for c in checks) else 'PASS', 'visual_status': visual_status,
            'checks': checks, 'errors': errors, 'warnings': warnings,
            'limitations': ['Metadata and evidence consistency checked; actual pixels, annotation accuracy, calibrated albedo and rendered similarity are not automatically certified.']}

def validate_folder(folder, require=False):
    folder = Path(folder); inventory = json.loads((folder/'objects.json').read_text(encoding='utf-8'))
    names = ['material-observations.json', 'material-spec.json']
    present = [bool((folder/n).exists()) for n in names]
    if not require and not any(present) and 'appearance_analysis' not in inventory:
        print('MATERIALS_UNKNOWN: legacy inventory has no color/texture analysis'); return None
    expected = {'schema_version': '1.0', 'observations_file': names[0], 'spec_file': names[1], 'validation_file': 'material-validation.json'}
    if inventory.get('appearance_analysis') != expected or not all(present):
        raise ValueError('Complete appearance_analysis links and both material files required')
    observations, spec = [json.loads((folder/n).read_text(encoding='utf-8')) for n in names]
    # Hash actual local sources for cross-view deduplication; do not modify source JSON.
    inventory = {**inventory, 'images': [dict(i) for i in inventory.get('images', [])]}
    for image in inventory['images']:
        rel = image.get('file'); source = (folder/rel).resolve() if isinstance(rel, str) else folder
        if isinstance(rel, str) and not Path(rel).is_absolute() and folder.resolve() in source.parents and source.is_file():
            image['_material_source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    result = validate_records(inventory, observations, spec)
    used = {o.get('image_id') for o in observations.get('observations', [])}
    for image in inventory.get('images', []):
        if image.get('image_id') not in used: continue
        rel = image.get('file'); source = (folder/rel).resolve() if isinstance(rel, str) else folder
        ok = isinstance(rel, str) and not Path(rel).is_absolute() and folder.resolve() in source.parents and source.is_file()
        if ok and image.get('sha256'):
            ok = hashlib.sha256(source.read_bytes()).hexdigest() == image['sha256']
        message = f"{image.get('image_id')}: local source must exist inside the room folder and match its declared SHA256"
        result['checks'].append({'name': str(image.get('image_id'))+':source_file', 'status': 'PASS' if ok else 'FAIL', 'result': message})
        if not ok:
            result['errors'].append(message); result['overall'] = result['structural_status'] = 'FAIL'
    (folder/'material-validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if result['overall'] == 'FAIL': raise ValueError('; '.join(result['errors'][:8]))
    print(f"MATERIALS_{result['overall']}: structure={result['structural_status']}; visual={result['visual_status']}; calibrated appearance not certified")
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('folder'); parser.add_argument('--require', action='store_true'); args = parser.parse_args()
    validate_folder(args.folder, args.require)
