#!/usr/bin/env python3
from __future__ import annotations

import csv, hashlib, json, re, shutil, subprocess, zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'bulk_acquisition'/'phase5_transfer_qa'
WORK=ROOT/'bulk_acquisition'/'work_phase5_transfer_qa'
TAG='bulk-transfer-phase4b-2026-08-14'
DATASETS={
 'DS-142':{'expectedImages':3156,'archiveSha256':'ffc9bae08d34e1c587795f82a9339c13823c16d50c574bf4f21b662b59c46ed5'},
 'DS-143':{'expectedImages':3000,'archiveSha256':'078c6d5851abaac03e5d5e4c1a5ecf2db1346b6741d077a91dc0121deb5b31f3'},
 'DS-146':{'expectedImages':1625,'archiveSha256':'f762ee1c7a3c48940ed3af36eed44ab94eedcccbc1970d8fc1c9bcc327f7ac48'},
}
IMG_EXT={'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}


def run(args:list[str]): subprocess.run(args,check=True,text=True)
def sha256(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def dhash(p:Path)->int:
 with Image.open(p) as im:
  im=im.convert('L').resize((9,8),Image.Resampling.LANCZOS)
  px=list(im.getdata())
 x=0
 for y in range(8):
  row=px[y*9:(y+1)*9]
  for i in range(8): x=(x<<1)|int(row[i]>row[i+1])
 return x
def safe_extract(zp:Path,dest:Path):
 dest.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(zp) as z:
  for info in z.infolist():
   pp=Path(info.filename)
   if pp.is_absolute() or '..' in pp.parts: raise RuntimeError(f'unsafe zip path {info.filename}')
  z.extractall(dest)
def recursive_extract(outer:Path,dest:Path)->list[str]:
 safe_extract(outer,dest)
 extracted=[]; seen=set()
 while True:
  todo=[p for p in dest.rglob('*.zip') if p not in seen]
  if not todo: break
  for zp in todo:
   seen.add(zp); sub=zp.with_name(zp.stem+'_extracted')
   safe_extract(zp,sub); extracted.append(zp.relative_to(dest).as_posix())
 return extracted

def reconstruct(did:str,meta:dict)->Path:
 d=WORK/did; d.mkdir(parents=True,exist_ok=True)
 run(['gh','release','download',TAG,'--repo','dtfgenetics/Thc-dataset','--pattern',f'{did}_archive.part*','--dir',str(d)])
 parts=sorted(d.glob(f'{did}_archive.part*'))
 if not parts: raise RuntimeError(f'no parts downloaded for {did}')
 outer=d/f'{did}_outer.zip'
 with outer.open('wb') as w:
  for p in parts:
   with p.open('rb') as r: shutil.copyfileobj(r,w,1024*1024)
 got=sha256(outer)
 if got!=meta['archiveSha256']: raise RuntimeError(f'{did} archive sha mismatch {got}')
 return outer

class UF:
 def __init__(self,n): self.p=list(range(n))
 def find(self,x):
  while self.p[x]!=x:
   self.p[x]=self.p[self.p[x]]; x=self.p[x]
  return x
 def union(self,a,b):
  a=self.find(a); b=self.find(b)
  if a!=b:self.p[b]=a

def annotation_qa(root:Path)->dict:
 txts=list(root.rglob('*.txt')); token_counts=Counter(); numeric_lines=0; yolo_like=0; sampled=0; examples=[]
 for p in txts:
  try: lines=p.read_text(encoding='utf-8',errors='ignore').splitlines()
  except Exception: continue
  for line in lines:
   s=line.strip()
   if not s: continue
   t=s.split(); token_counts[len(t)]+=1; sampled+=1
   try: vals=[float(x) for x in t]; numeric_lines+=1
   except ValueError: vals=[]
   if len(vals)==5 and vals[0]>=0 and all(0<=x<=1 for x in vals[1:]): yolo_like+=1
   if len(examples)<20: examples.append(s[:200])
   if sampled>=5000: break
  if sampled>=5000: break
 return {'txtFileCount':len(txts),'sampledNonemptyLines':sampled,'tokenCountDistribution':dict(token_counts),'numericLineFraction':numeric_lines/sampled if sampled else 0,'yolo5NormalizedFraction':yolo_like/sampled if sampled else 0,'examples':examples,'interpretation':'YOLO-like only if five-token normalized rows dominate; human class-index/coordinate review still required.'}

def audit(did:str,meta:dict)->dict:
 outer=reconstruct(did,meta); root=WORK/did/'extracted'; nested=recursive_extract(outer,root)
 imgs=sorted(p for p in root.rglob('*') if p.suffix.lower() in IMG_EXT)
 rows=[]; sha_b=defaultdict(list); class_counts=Counter()
 for idx,p in enumerate(imgs):
  rel=p.relative_to(root).as_posix(); label=p.parent.name; s=sha256(p); h=dhash(p)
  rows.append({'index':idx,'relativePath':rel,'classFolder':label,'sizeBytes':p.stat().st_size,'sha256':s,'dhash64':f'{h:016x}'})
  sha_b[s].append(idx); class_counts[label]+=1
 exact=[v for v in sha_b.values() if len(v)>1]
 hashes=[int(r['dhash64'],16) for r in rows]; uf=UF(len(rows)); near=0; cross=0; samples=[]
 for i in range(len(rows)):
  for j in range(i+1,len(rows)):
   d=(hashes[i]^hashes[j]).bit_count()
   if d<=4:
    near+=1; uf.union(i,j)
    if rows[i]['classFolder']!=rows[j]['classFolder']:
     cross+=1
     if len(samples)<200:samples.append({'a':rows[i]['relativePath'],'b':rows[j]['relativePath'],'classA':rows[i]['classFolder'],'classB':rows[j]['classFolder'],'hamming':d})
 comps=defaultdict(list)
 for i in range(len(rows)): comps[uf.find(i)].append(i)
 near_comps=sum(1 for v in comps.values() if len(v)>1)
 with (OUT/f'{did}_image_inventory.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0].keys()) if rows else ['index']); w.writeheader(); w.writerows(rows)
 qa={'datasetId':did,'sourceArchiveSha256':meta['archiveSha256'],'nestedArchivesExtracted':nested,'imageCount':len(rows),'expectedImageCount':meta['expectedImages'],'imageCountMatchesExpected':len(rows)==meta['expectedImages'],'classFolderCounts':dict(class_counts),'exactDuplicateGroupCount':len(exact),'exactDuplicateGroupsSample':[[rows[i]['relativePath'] for i in g] for g in exact[:100]],'nearDuplicateEdgeCountDhashLE4':near,'nearDuplicateComponentCount':near_comps,'crossClassNearDuplicateEdgeCount':cross,'crossClassNearDuplicateSample':samples,'annotationQA':annotation_qa(root) if did=='DS-143' else None,'trainingGate':'HOLD until duplicate review, host-preserving ontology map and leakage-safe split are approved. Cross-crop labels cannot become Cannabis causal ground truth.'}
 (OUT/f'{did}_qa.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
 return qa

def main():
 shutil.rmtree(OUT,ignore_errors=True); shutil.rmtree(WORK,ignore_errors=True); OUT.mkdir(parents=True); WORK.mkdir(parents=True)
 qas=[audit(d,m) for d,m in DATASETS.items()]
 manifest={'schemaVersion':'1.0','phase':'transfer-extraction-dedup-phase5','createdAt':datetime.now(timezone.utc).isoformat(),'results':[{k:q[k] for k in ['datasetId','imageCount','expectedImageCount','imageCountMatchesExpected','classFolderCounts','exactDuplicateGroupCount','nearDuplicateEdgeCountDhashLE4','nearDuplicateComponentCount','crossClassNearDuplicateEdgeCount','annotationQA','trainingGate']} for q in qas]}
 (OUT/'phase5-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 lines=['# Transfer Extraction / Dedup Phase 5','']
 for q in qas: lines.append(f"- **{q['datasetId']}**: {q['imageCount']} images; expected-match={q['imageCountMatchesExpected']}; exact duplicate groups={q['exactDuplicateGroupCount']}; dHash<=4 edges={q['nearDuplicateEdgeCountDhashLE4']}; cross-class edges={q['crossClassNearDuplicateEdgeCount']}")
 lines+=['','All three remain cross-crop transfer-only and training-gated pending human duplicate/ontology/split review.']
 (OUT/'phase5-summary.md').write_text('\n'.join(lines),encoding='utf-8')
 checks=[]
 for p in sorted(OUT.iterdir()):
  if p.is_file() and p.name!='phase5-checksums.sha256': checks.append(f'{sha256(p)}  {p.name}')
 (OUT/'phase5-checksums.sha256').write_text('\n'.join(checks)+'\n',encoding='utf-8')
 print(json.dumps(manifest,indent=2))
if __name__=='__main__': main()
