#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, hashlib, json, shutil, subprocess, zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUTROOT=ROOT/'bulk_acquisition'/'phase7_transfer_qa'
WORKROOT=ROOT/'bulk_acquisition'/'work_phase7_transfer_qa'
TAG='bulk-transfer-phase6-2026-08-14'
IMG_EXT={'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}
DATASETS={
 'DS-137':{'archiveSha256':'1ea90d55a1e67084516bcc447326e8a602ae110701360be055c87c62ed4a7d5f','describedImages':9283},
 'DS-138':{'archiveSha256':'7b95cbbf3b725d3fc7f7315438efb374c5ce58e226473975a28e5079f7a08c4d','describedImages':8814},
 'DS-139':{'archiveSha256':'8821ed713dbf61b574a5da2b8ae2d53b924fb56cc79fa6bfaa657524cfefbcb1','describedImages':17609},
 'DS-145':{'archiveSha256':'203aa20caa90a24e3685ef5c516bc9949f8d47818cd21251789f2e6b2d89add8','describedImages':12096},
}

def run(args:list[str]): subprocess.run(args,check=True,text=True)
def sha256(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def dhash(p:Path)->int:
 with Image.open(p) as im:
  im=im.convert('L').resize((9,8),Image.Resampling.LANCZOS); px=list(im.getdata())
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
   if pp.is_absolute() or '..' in pp.parts: raise RuntimeError(f'unsafe ZIP path: {info.filename}')
  z.extractall(dest)
def recursive_extract(outer:Path,dest:Path)->list[str]:
 safe_extract(outer,dest); seen=set(); nested=[]
 while True:
  todo=[p for p in dest.rglob('*.zip') if p not in seen]
  if not todo: break
  for zp in todo:
   seen.add(zp); sub=zp.with_name(zp.stem+'_extracted'); safe_extract(zp,sub); nested.append(zp.relative_to(dest).as_posix())
 return nested

def reconstruct(did:str,meta:dict,work:Path)->Path:
 run(['gh','release','download',TAG,'--repo','dtfgenetics/Thc-dataset','--pattern',f'{did}_archive.part*','--dir',str(work)])
 parts=sorted(work.glob(f'{did}_archive.part*'))
 if not parts: raise RuntimeError('no release chunks')
 outer=work/f'{did}_outer.zip'
 with outer.open('wb') as w:
  for p in parts:
   with p.open('rb') as r: shutil.copyfileobj(r,w,1024*1024)
 got=sha256(outer)
 if got!=meta['archiveSha256']: raise RuntimeError(f'archive SHA mismatch {got}')
 return outer

class UF:
 def __init__(self,n): self.p=list(range(n))
 def find(self,x):
  while self.p[x]!=x: self.p[x]=self.p[self.p[x]]; x=self.p[x]
  return x
 def union(self,a,b):
  a=self.find(a); b=self.find(b)
  if a!=b:self.p[b]=a

class BKNode:
 __slots__=('value','items','children')
 def __init__(self,value:int,idx:int): self.value=value; self.items=[idx]; self.children={}
class BKTree:
 def __init__(self): self.root=None
 @staticmethod
 def dist(a:int,b:int)->int:return (a^b).bit_count()
 def add(self,value:int,idx:int):
  if self.root is None:self.root=BKNode(value,idx);return
  n=self.root
  while True:
   d=self.dist(value,n.value)
   if d==0:n.items.append(idx);return
   if d not in n.children:n.children[d]=BKNode(value,idx);return
   n=n.children[d]
 def query(self,value:int,radius:int):
  if self.root is None:return []
  out=[]; stack=[self.root]
  while stack:
   n=stack.pop(); d=self.dist(value,n.value)
   if d<=radius:
    for idx in n.items:out.append((idx,d))
   lo=max(1,d-radius); hi=d+radius
   for edge,ch in n.children.items():
    if lo<=edge<=hi:stack.append(ch)
  return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('dataset_id',choices=sorted(DATASETS));args=ap.parse_args();did=args.dataset_id;meta=DATASETS[did]
 out=OUTROOT/did;work=WORKROOT/did;shutil.rmtree(out,ignore_errors=True);shutil.rmtree(work,ignore_errors=True);out.mkdir(parents=True);work.mkdir(parents=True)
 outer=reconstruct(did,meta,work);root=work/'extracted';nested=recursive_extract(outer,root)
 imgs=sorted(p for p in root.rglob('*') if p.suffix.lower() in IMG_EXT)
 rows=[];sha_b=defaultdict(list);classes=Counter();bad=[]
 for idx,p in enumerate(imgs):
  rel=p.relative_to(root).as_posix();label=p.parent.name
  try:h=dhash(p)
  except Exception as exc:bad.append({'path':rel,'error':str(exc)});continue
  s=sha256(p);r={'index':len(rows),'relativePath':rel,'classFolder':label,'sizeBytes':p.stat().st_size,'sha256':s,'dhash64':f'{h:016x}'};rows.append(r);sha_b[s].append(r['index']);classes[label]+=1
 exact=[v for v in sha_b.values() if len(v)>1]
 exact_conf=[]
 for g in exact:
  labs={rows[i]['classFolder'] for i in g}
  if len(labs)>1:exact_conf.append({'sha256':rows[g[0]]['sha256'],'members':[{'path':rows[i]['relativePath'],'class':rows[i]['classFolder']} for i in g]})
 tree=BKTree();uf=UF(len(rows));near_edges=0;cross_edges=0;samples=[]
 for i,r in enumerate(rows):
  h=int(r['dhash64'],16)
  for j,d in tree.query(h,4):
   near_edges+=1;uf.union(i,j)
   if rows[j]['classFolder']!=r['classFolder']:
    cross_edges+=1
    if len(samples)<500:samples.append({'a':rows[j]['relativePath'],'b':r['relativePath'],'classA':rows[j]['classFolder'],'classB':r['classFolder'],'hamming':d})
  tree.add(h,i)
 comps=defaultdict(list)
 for i in range(len(rows)): comps[uf.find(i)].append(i)
 near_comps=sum(1 for g in comps.values() if len(g)>1)
 with (out/f'{did}_image_inventory.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0].keys()) if rows else ['index']);w.writeheader();w.writerows(rows)
 qa={'datasetId':did,'sourceArchiveSha256':meta['archiveSha256'],'nestedArchivesExtracted':nested,'decodedImageCount':len(rows),'badImageCount':len(bad),'badImages':bad,'describedImageCount':meta['describedImages'],'countDeltaVsDescription':len(rows)-meta['describedImages'],'classFolderCounts':dict(classes),'uniqueSha256Count':len(sha_b),'exactDuplicateGroupCount':len(exact),'exactDuplicateFileCount':sum(len(g) for g in exact),'exactCrossClassConflictCount':len(exact_conf),'exactCrossClassConflicts':exact_conf[:100],'nearDuplicateEdgeCountDhashLE4':near_edges,'nearDuplicateComponentCount':near_comps,'crossClassNearDuplicateEdgeCount':cross_edges,'crossClassNearDuplicateSample':samples,'trainingGate':'HOLD pending exact/cross-class conflict review, host-preserving ontology mapping, source-group reconstruction and leakage-safe split. Cross-crop causal labels remain transfer-only.'}
 (out/f'{did}_qa.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
 summary=[f'# Phase 7 QA — {did}','',f"Decoded images: **{len(rows)}** (description: {meta['describedImages']}; delta {len(rows)-meta['describedImages']:+d})",f"Unique SHA-256 payloads: **{len(sha_b)}**",f"Exact duplicate groups: **{len(exact)}**",f"Exact cross-class conflicts: **{len(exact_conf)}**",f"dHash<=4 edges: **{near_edges}**",f"Cross-class dHash<=4 edges: **{cross_edges}**",'', 'Training remains on HOLD pending review; cross-crop labels cannot become Cannabis causal ground truth.']
 (out/f'{did}_phase7_summary.md').write_text('\n'.join(summary),encoding='utf-8')
 checks=[]
 for p in sorted(out.iterdir()):
  if p.is_file() and not p.name.endswith('checksums.sha256'):checks.append(f'{sha256(p)}  {p.name}')
 (out/f'{did}_phase7_checksums.sha256').write_text('\n'.join(checks)+'\n',encoding='utf-8')
 print(json.dumps(qa,indent=2))
if __name__=='__main__':main()
