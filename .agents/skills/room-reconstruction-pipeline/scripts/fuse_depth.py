#!/usr/bin/env python3
"""Fuse one explicitly supported RGB/depth/camera export; does not infer object identity.
Requires numpy/Pillow. Camera format: fx/fy/cx/cy,width/height,t_00..t_23;
camera-to-world, X-right/Y-up/forward -Z. Other formats require an adapter.
"""
import argparse,json,hashlib,math
from pathlib import Path
import numpy as np
from PIL import Image

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--keyframes',required=True);p.add_argument('--output',required=True);p.add_argument('--depth-scale',required=True,type=float);p.add_argument('--confidence-value',required=True,type=int);p.add_argument('--voxel-m',type=float,default=.025);p.add_argument('--stride',type=int,default=2);p.add_argument('--max-frames',type=int);p.add_argument('--near-m',type=float,default=.25);p.add_argument('--far-m',type=float,default=8);p.add_argument('--edge-m',type=float,default=.15);a=p.parse_args()
 if not math.isfinite(a.depth_scale) or a.depth_scale<=0 or a.stride<1 or a.voxel_m<=0 or not 0<a.near_m<a.far_m:raise ValueError('Invalid scale/range/stride')
 root=Path(a.keyframes).resolve();out=Path(a.output).resolve()
 if out.exists():raise FileExistsError('Use a new output directory')
 files=sorted((root/'cameras').glob('*.json'))
 if a.max_frames is not None:
  if a.max_frames<1:raise ValueError('max-frames must be positive')
  files=files[:a.max_frames]
 if not files:raise ValueError('No camera JSON files')
 points=[];colors=[];frames=[];records=[]
 for i,f in enumerate(files):
  c=json.loads(f.read_text());raw=np.asarray(Image.open(root/'depth'/(f.stem+'.png')));conf=np.asarray(Image.open(root/'confidence'/(f.stem+'.png')))
  if raw.ndim!=2 or raw.shape!=conf.shape or raw.dtype.kind not in 'ui':raise ValueError('Invalid integer depth/confidence image')
  if not all(math.isfinite(c[k]) for k in ['fx','fy','cx','cy','width','height']) or min(c['fx'],c['fy'],c['width'],c['height'])<=0:raise ValueError('Invalid camera intrinsics')
  z=raw.astype('f4')*a.depth_scale;h,w=z.shape;Y,X=np.mgrid[:h,:w];u=((X+.5)*(c['width']/w)-.5-c['cx'])/c['fx'];v=((Y+.5)*(c['height']/h)-.5-c['cy'])/c['fy'];local=np.stack([u*z,-v*z,-z],axis=-1)
  valid=np.isfinite(z)&(z>a.near_m)&(z<a.far_m)&(conf==a.confidence_value)
  edge=np.zeros_like(valid);edge[1:-1,1:-1]=(np.abs(z[1:-1,2:]-z[1:-1,:-2])<a.edge_m)&(np.abs(z[2:,1:-1]-z[:-2,1:-1])<a.edge_m);valid&=edge;sample=np.zeros_like(valid);sample[::a.stride,::a.stride]=True;valid&=sample
  rot=np.array([[c['t_'+str(r)+str(k)] for k in range(3)] for r in range(3)]);trans=np.array([c['t_'+str(r)+'3'] for r in range(3)])
  if not np.isfinite(rot).all() or not np.isfinite(trans).all() or not np.allclose(rot.T@rot,np.eye(3),atol=.03) or np.linalg.det(rot)<.9:raise ValueError('Invalid camera rotation')
  rgb=np.asarray(Image.open(root/'images'/(f.stem+'.jpg')).convert('RGB').resize((w,h),Image.Resampling.BILINEAR))
  xyz=np.einsum('ij,kj->ki',rot,local[valid])+trans
  if not np.isfinite(xyz).all():raise ValueError('Non-finite transformed points')
  points.append(xyz.astype('f4'));colors.append(rgb[valid]);frames.append(np.full(len(xyz),i,dtype='i4'));records.append({'stem':f.stem,'accepted_points':len(xyz),'camera_sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
 xyz=np.concatenate(points);rgb=np.concatenate(colors);fi=np.concatenate(frames)
 if not len(xyz):raise ValueError('No valid points; do not silently relax confidence')
 _,idx=np.unique(np.floor(xyz/a.voxel_m).astype('i8'),axis=0,return_index=True);out.mkdir(parents=True)
 np.savez_compressed(out/'fused.npz',points=xyz[idx],colors=rgb[idx],frames=fi[idx])
 (out/'manifest.json').write_text(json.dumps({'status':'FUSED','format':'camera-to-world X-right Y-up -Z-forward; explicit adapter only','depth_scale_m_per_value':a.depth_scale,'confidence_value':a.confidence_value,'frame_count':len(files),'raw_point_count':len(xyz),'voxel_point_count':len(idx),'frames':records,'limitations':['Not GLB registration, semantic segmentation or full object dimensions','Depth scale was supplied, not independently measured','Visible depth surfaces may omit transparent/reflective/occluded geometry']},indent=2));print('FUSED',len(xyz),'VOXELS',len(idx))
if __name__=='__main__':main()
