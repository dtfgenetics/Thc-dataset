#!/usr/bin/env python3
from __future__ import annotations

import hashlib, json, shutil, urllib.request, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'bulk_acquisition' / 'phase4b_public'
WORK = ROOT / 'bulk_acquisition' / 'work_phase4b_public'
CHUNK_BYTES = 90_000_000
UA = 'THC-Plant-Diagnostic-Dataset/1.0 (+https://github.com/dtfgenetics/Thc-dataset)'

DATASETS = [
    {'datasetId':'DS-142','mendeleyId':'jwc8k4997r','version':1,'title':'TeaLeaf-4','expectedImages':3156,'license':'CC BY 4.0'},
    {'datasetId':'DS-143','mendeleyId':'zg93th7mhb','version':1,'title':'MangoLeafDiseasesDataset','expectedImages':3000,'license':'CC BY 4.0'},
    {'datasetId':'DS-146','mendeleyId':'wkjg6srrk8','version':1,'title':'CottonPest-BD','expectedImages':1625,'license':'CC BY 4.0'},
]

IMG_EXT={'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}
ANN_EXT={'.txt','.csv','.json','.xml','.yaml','.yml'}

def digest(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def download(url:str,dest:Path)->dict:
    tmp=dest.with_suffix(dest.suffix+'.part'); tmp.unlink(missing_ok=True)
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*'})
    with urllib.request.urlopen(req,timeout=900) as r,tmp.open('wb') as w:
        while True:
            b=r.read(4*1024*1024)
            if not b: break
            w.write(b)
        meta={'requestedUrl':url,'finalUrl':r.geturl(),'contentType':r.headers.get('Content-Type'),'contentLengthHeader':r.headers.get('Content-Length')}
    tmp.replace(dest); meta['sizeBytes']=dest.stat().st_size; meta['sha256']=digest(dest); return meta

def inspect_zip(p:Path)->dict:
    rows=[]; images=0; anns=0; nested=[]
    with zipfile.ZipFile(p) as z:
        for i in z.infolist():
            if i.is_dir(): continue
            s=Path(i.filename).suffix.lower()
            images += int(s in IMG_EXT); anns += int(s in ANN_EXT)
            if s=='.zip': nested.append(i.filename)
            rows.append({'name':i.filename,'compressedSize':i.compress_size,'uncompressedSize':i.file_size,'crc32':f'{i.CRC:08x}','isImage':s in IMG_EXT,'isAnnotation':s in ANN_EXT})
    return {'entryCount':len(rows),'imageEntryCount':images,'annotationEntryCount':anns,'nestedZipEntries':nested,'entries':rows}

def chunk(p:Path,did:str)->list[dict]:
    parts=[]; idx=1
    with p.open('rb') as src:
        while True:
            b=src.read(CHUNK_BYTES)
            if not b: break
            q=OUT/f'{did}_archive.part{idx:03d}'
            q.write_bytes(b)
            parts.append({'filename':q.name,'partIndex':idx,'sizeBytes':q.stat().st_size,'sha256':digest(q)})
            idx+=1
    for x in parts:
        x['partCount']=len(parts); x['reconstruct']=f"concatenate {did}_archive.partNNN in numeric order"
    return parts

def acquire(ds:dict)->dict:
    did=ds['datasetId']; mid=ds['mendeleyId']; ver=ds['version']
    url=f'https://data.mendeley.com/public-api/zip/{mid}/download/{ver}'
    archive=WORK/f'{did}_{mid}_v{ver}.zip'
    try:
        meta=download(url,archive)
        if not zipfile.is_zipfile(archive):
            raise RuntimeError(f"public Download All response is not ZIP: {meta.get('contentType')} {archive.stat().st_size} bytes")
        zi=inspect_zip(archive)
        (OUT/f'{did}_zip_inventory.json').write_text(json.dumps(zi,indent=2),encoding='utf-8')
        original={'filename':archive.name,'sizeBytes':archive.stat().st_size,'sha256':digest(archive)}
        parts=chunk(archive,did)
        (OUT/f'{did}_archive_parts.json').write_text(json.dumps(parts,indent=2),encoding='utf-8')
        direct_match = zi['imageEntryCount']==ds['expectedImages']
        return {**ds,'status':'acquired','downloadRoute':url,'downloadMeta':meta,'originalArchive':original,'archiveParts':parts,'zipEntryCount':zi['entryCount'],'directImageEntryCount':zi['imageEntryCount'],'annotationEntryCount':zi['annotationEntryCount'],'nestedZipEntries':zi['nestedZipEntries'],'expectedDirectImageCountMatch':direct_match,'guardrail':'Cross-crop transfer only. Per-file SHA256/pHash, duplicate grouping and host-preserving labels required before training.'}
    except Exception as e:
        return {**ds,'status':'blocked','downloadRoute':url,'error':f'{type(e).__name__}: {e}','truthRule':'No acquired status without valid downloaded ZIP bytes.'}

def main():
    shutil.rmtree(OUT,ignore_errors=True); shutil.rmtree(WORK,ignore_errors=True)
    OUT.mkdir(parents=True); WORK.mkdir(parents=True)
    results=[acquire(x) for x in DATASETS]
    manifest={'schemaVersion':'1.0','phase':'bulk-transfer-phase4b-public-route','createdAt':datetime.now(timezone.utc).isoformat(),'chunkBytes':CHUNK_BYTES,'results':results,'truthRule':'status=acquired means the public Download All ZIP was received and validated as a ZIP; causal labels remain host-specific transfer metadata.'}
    (OUT/'phase4b-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    summary=['# Bulk Transfer Phase 4B — Public Mendeley Download Route','']
    for r in results:
        if r['status']=='acquired': summary.append(f"- **{r['datasetId']}** acquired: {r['originalArchive']['sizeBytes']:,} bytes, {len(r['archiveParts'])} bridge part(s), {r['directImageEntryCount']} direct image entries")
        else: summary.append(f"- **{r['datasetId']}** blocked: {r['error']}")
    summary += ['','All sources remain cross-crop transfer-only until Cannabis-specific validation.']
    (OUT/'phase4b-summary.md').write_text('\n'.join(summary),encoding='utf-8')
    checks=[]
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name!='phase4b-checksums.sha256': checks.append(f'{digest(p)}  {p.name}')
    (OUT/'phase4b-checksums.sha256').write_text('\n'.join(checks)+'\n',encoding='utf-8')
    print(json.dumps({'results':[{'datasetId':r['datasetId'],'status':r['status'],'size':r.get('originalArchive',{}).get('sizeBytes'),'parts':len(r.get('archiveParts',[]))} for r in results]},indent=2))

if __name__=='__main__': main()
