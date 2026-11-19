"""End-to-end isolated template cloning/sync/QA/render and failure injection."""
import argparse,copy,hashlib,json,subprocess,tempfile
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--blender',required=True);p.add_argument('--result',required=True);a=p.parse_args();here=Path(__file__).resolve().parent
 def run(args,ok=True):
  r=subprocess.run([a.blender,'--background','--python-exit-code','1']+args,capture_output=True,text=True)
  if (r.returncode==0)!=ok:raise AssertionError(r.stdout[-3500:]+r.stderr[-1000:])
  return r
 with tempfile.TemporaryDirectory(prefix='room-pipeline-test-') as tmp:
  t=Path(tmp);run(['--factory-startup','--python',str(here/'create_test_room.py'),'--',str(t)]);source_hash=hashlib.sha256((t/'source.blend').read_bytes()).hexdigest()
  def mode(blend,mode,profile,output,ok=True,extra=[]):return run([str(blend),'--python',str(here/'blender_pipeline.py'),'--',mode,'--profile',str(profile),'--output',str(output)]+extra,ok)
  mode(t/'source.blend','sync',t/'profile.json',t/'synced.blend',extra=['--negative-probe']);assert (t/'synced.blend').exists();assert hashlib.sha256((t/'source.blend').read_bytes()).hexdigest()==source_hash
  mode(t/'synced.blend','qa',t/'profile.json',t/'qa.json',extra=['--negative-probe']);qa=json.loads((t/'qa.json').read_text());assert qa['status']=='PASS';assert qa['checks'][0]['actual']==2 and qa['checks'][0]['negative_probe']=='REJECTED'
  profile=json.loads((t/'profile.json').read_text());bad=copy.deepcopy(profile)
  for b in bad['bindings']:
   if b['instance_id'].startswith('seat_'):b['source_forward']='-Y'
  (t/'reversed.json').write_text(json.dumps(bad));mode(t/'source.blend','sync',t/'reversed.json',t/'must-not-save.blend',False);assert not (t/'must-not-save.blend').exists()
  bad=copy.deepcopy(profile);bad['qa']['chairs'][0]['root_pattern']='NO_MATCH';(t/'empty.json').write_text(json.dumps(bad));mode(t/'synced.blend','qa',t/'empty.json',t/'empty-qa.json',False);assert json.loads((t/'empty-qa.json').read_text())['status']=='FAIL'
  bad=copy.deepcopy(profile);bad['qa']['supports'][0]['object']='Device_Floating';(t/'floating.json').write_text(json.dumps(bad));mode(t/'synced.blend','qa',t/'floating.json',t/'floating-qa.json',False);assert json.loads((t/'floating-qa.json').read_text())['status']=='FAIL'
  mode(t/'synced.blend','render',t/'profile.json',t/'renders');manifest=json.loads((t/'renders/manifest.json').read_text());assert manifest['status']=='COMPLETE' and (t/'renders/test.png').exists();assert manifest['blend_sha256']==hashlib.sha256((t/'synced.blend').read_bytes()).hexdigest()
  mode(t/'synced.blend','render',t/'profile.json',t/'renders',False)
 Path(a.result).parent.mkdir(parents=True,exist_ok=True);Path(a.result).write_text(json.dumps(dict(status='PASS',rotated_second_room=True,chairs=2,new_template_instances_cloned=True,saved_file_reopened=True,source_file_unchanged=True,reversed_templates_rejected=True,empty_matches_rejected=True,floating_support_rejected=True,render_manifest_complete=True,existing_outputs_protected=True),indent=2));print('BLENDER_PIPELINE_E2E_PASS')
if __name__=='__main__':main()
