#!/usr/bin/env python3
import json,sys,hashlib
from pathlib import Path
p=Path(sys.argv[1]);d=json.loads((p/'objects.json').read_text());ims={x['image_id']:x for x in d['images']};assets=d['assets'];assert len({a['asset_id'] for a in assets})==len(assets)
for im in ims.values():
 if im['status']=='downloaded':assert hashlib.sha256((p/im['file']).read_bytes()).hexdigest()==im['sha256']
for a in assets:
 assert all(i in ims and ims[i]['status']=='downloaded' for i in a['evidence_image_ids'])
 assert a['dimensions']['status'] in ['estimated','unknown','measured']
 for r in a['dimensions']['ranges'].values():assert r is None or len(r)==2 and 0<r[0]<=r[1]
 if a['dimensions']['status']=='estimated':assert a['dimensions']['basis'] and a['dimensions']['confidence']=='low'
print(f'PASS: {len(assets)} assets, {sum(i["status"]=="downloaded" for i in ims.values())} source images verified')

for image in d.get('image_spatial_relations',[]):
 ids={o['asset_id'] for o in image['objects']}
 assert image['visible_asset_count']==len(ids)
 assert ids <= {a['asset_id'] for a in assets}
 if len(ids)<=1:assert not image['relationships']
 if image['status']=='unavailable':assert not ids
 for rel in image['relationships']:
  assert rel['subject_asset_id'] in ids and rel['object_asset_id'] in ids
  assert rel['subject_asset_id']!=rel['object_asset_id']
print('PER_IMAGE_RELATIONS_PASS')

from validate_distances import validate_folder
validate_folder(p)

from validate_materials import validate_folder as validate_material_folder
validate_material_folder(p)
