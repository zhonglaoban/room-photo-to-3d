#!/usr/bin/env python3
"""Download explicitly provided image URLs; no host guessing or authentication changes."""
import argparse,concurrent.futures,hashlib,json,time,urllib.request
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
p=argparse.ArgumentParser();p.add_argument('sources');p.add_argument('output');a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
urls=[s.strip() for s in Path(a.sources).read_text().splitlines() if s.strip()]
def download(item):
 i,url=item;target=out/f'{i:02d}_{url.split("/")[-1]}'
 result={'image_id':f'IMG_{i:02d}','source_url':url,'file':target.name}
 try:
  if not target.exists():
   for attempt in range(2):
    try:
     with urllib.request.urlopen(url,timeout=30) as r:data=r.read()
     from io import BytesIO
     with Image.open(BytesIO(data)) as im:im.verify()
     target.write_bytes(data);break
    except Exception:
     if attempt:raise
  with Image.open(target) as im:result.update(width=im.width,height=im.height,format=im.format)
  data=target.read_bytes();result.update(status='downloaded',bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
 except Exception as e:result.update(status='failed',error=str(e))
 return result
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:results=list(ex.map(download,enumerate(urls)))
(out/'images-manifest.json').write_text(json.dumps({'images':results},ensure_ascii=False,indent=2))
for batch in range((len(results)+5)//6):
 sheet=Image.new('RGB',(1500,760),'#eeeeea');draw=ImageDraw.Draw(sheet)
 for k,r in enumerate(results[batch*6:(batch+1)*6]):
  if r['status']!='downloaded':continue
  with Image.open(out/r['file']) as im:thumb=ImageOps.contain(ImageOps.exif_transpose(im).convert('RGB'),(490,335))
  x=(k%3)*500+(500-thumb.width)//2;y=(k//3)*380+28;sheet.paste(thumb,(x,y));draw.text(((k%3)*500+12,(k//3)*380+8),r['image_id'],fill='black')
 sheet.save(out/f'contact-sheet-{batch+1:02}.jpg',quality=90)
print(json.dumps({'downloaded':sum(r['status']=='downloaded' for r in results),'total':len(results)}))
