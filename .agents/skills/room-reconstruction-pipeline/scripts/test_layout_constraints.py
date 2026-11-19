"""Observable regression tests; source and output are isolated temporary fixtures."""
import copy,hashlib,json,math,tempfile,unittest
from pathlib import Path
from layout_constraints import apply,write_json

class ConstraintsTest(unittest.TestCase):
 def setUp(self):
  self.source={'units':'m','assets':[{'instance_id':'cab','asset_id':'CASE','kind':'solid','position':[0,0,0],'size':[2,.6,.8],'yaw':0},{'instance_id':'island','asset_id':'DESK','kind':'solid','position':[4,2,0],'size':[2,.8,.77],'yaw':math.pi/2}]}
  self.sha='test-source';self.base={'units':'m','reviewed':True,'source_sha256':self.sha,'edits':[]}
 def review(self,edits):
  d=copy.deepcopy(self.base);d['edits']=[dict(raw_user_text='reviewed fixture statement',evidence='test user input',**e) for e in edits];return d
 def test_rotated_gap_moves_group_by_projected_faces(self):
  review=self.review([dict(op='gap',fixed=['cab'],moving=['island'],axis='X',side=1,gap_m=.3,metric='world_aabb_face')]);d=apply(self.source,review,self.sha)
  self.assertAlmostEqual(d['assets'][1]['position'][0],1.7);self.assertEqual(self.source['assets'][1]['position'][0],4)
 def test_seeded_seating_faces_rotated_table(self):
  r=self.review([dict(op='seating',tables=['island'],chair_asset_id='SIMPLE_SEAT',chair_size_m=[.5,.48,.9],per_side=1,floor_z_m=0,seed=123,tuck_m=.05,jitter=dict(tangent_m=.01,normal_m=.01,yaw_deg=3))]);a=apply(self.source,r,self.sha);b=apply(self.source,r,self.sha)
  seats=[x for x in a['assets'] if x['kind']=='chair'];self.assertEqual(len(seats),2);self.assertEqual(a,b)
  for seat in seats:
   v=[self.source['assets'][1]['position'][k]-seat['position'][k] for k in [0,1]];front=[-math.sin(seat['yaw']),math.cos(seat['yaw'])];dot=sum(x*y for x,y in zip(v,front))/math.hypot(*v);self.assertGreater(dot,.99)
 def test_stale_unreviewed_unknown_invalid_values_fail(self):
  for field,value in [('source_sha256','old'),('reviewed',False),('units','cm')]:
   r=self.review([]);r[field]=value
   with self.assertRaises(ValueError):apply(self.source,r,self.sha)
  for edit in [dict(op='set_size',instance_id='island',size_m=[1,-1,1]),dict(op='set_pose',instance_id='island',position_m=[float('nan'),1,2]),dict(op='invent_room')]:
   with self.assertRaises(ValueError):apply(self.source,self.review([edit]),self.sha)
 def test_existing_confirmed_chair_cannot_be_silently_replaced(self):
  d=copy.deepcopy(self.source);d['assets'].append(dict(instance_id='existing',asset_id='SEAT',kind='chair',table_instance_id='island',position=[1,1,0],size=[.4,.4,.8],yaw=0));r=self.review([dict(op='seating',tables=['island'],chair_asset_id='SEAT',chair_size_m=[.5,.48,.9],per_side=1,floor_z_m=0,seed=1,tuck_m=.05,jitter=dict(tangent_m=0,normal_m=0,yaw_deg=0))])
  with self.assertRaises(ValueError):apply(d,r,self.sha)
 def test_output_refuses_overwrite_and_explicit_backup_preserves_original(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'layout.json';write_json(p,{'old':1})
   with self.assertRaises(FileExistsError):write_json(p,{'new':2})
   write_json(p,{'new':2},True);backups=list(Path(tmp).glob('*.bak'));self.assertEqual(len(backups),1);self.assertEqual(json.loads(backups[0].read_text()),{'old':1})
if __name__=='__main__':unittest.main()
