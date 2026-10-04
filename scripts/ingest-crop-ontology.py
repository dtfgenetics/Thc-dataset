#!/usr/bin/env python3
"""Incremental Crop Ontology BrAPI ingestion with immutable raw snapshots."""
import argparse, hashlib, json, pathlib, urllib.parse, urllib.request
PARSER_VERSION="crop-ontology-brapi-v1.1.0"
BASE="https://cropontology.org/brapi/v1"
RIGHTS={"state":"licensed_reuse","license":"CC BY 4.0","license_url":"https://creativecommons.org/licenses/by/4.0/","source_terms_url":"https://cropontology.org/about","attribution":"Crop Ontology / CGIAR community curators","note":"Preserve upstream identifiers and attribution."}
def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha(v): return hashlib.sha256(canon(v)).hexdigest()
def rows(payload):
    r=payload.get("result",payload)
    if isinstance(r,dict):
        for k in ("data","traits","variables"):
            if isinstance(r.get(k),list): return r[k]
    return r if isinstance(r,list) else []
def normalize(x,kind):
    ident=x.get(f"{kind}_id") or x.get(f"{kind}DbId") or x.get("observationVariableDbId") or x.get("variable_id")
    name=x.get(f"{kind}_name") or x.get(f"{kind}Name") or x.get("observationVariableName") or x.get("variable_name")
    if not ident or not name: return None
    record={"upstream_id":str(ident),"record_type":kind,"name":str(name),"ontology_id":x.get("ontology_id") or x.get("ontologyDbId"),"ontology_name":x.get("ontology_name") or x.get("ontologyName"),"description":x.get(f"{kind}_description") or x.get("description"),"source":"Crop Ontology","provenance":{"api":BASE,"parser_version":PARSER_VERSION},"rights":RIGHTS}
    if kind=="variable":
        trait=x.get("trait") if isinstance(x.get("trait"),dict) else {}
        method=x.get("method") if isinstance(x.get("method"),dict) else {}
        scale=x.get("scale") if isinstance(x.get("scale"),dict) else {}
        record["components"]={
            "trait":{"upstream_id":x.get("trait_id") or trait.get("traitDbId") or trait.get("id"),"name":x.get("trait_name") or trait.get("traitName") or trait.get("name")},
            "method":{"upstream_id":x.get("method_id") or method.get("methodDbId") or method.get("id"),"name":x.get("method_name") or method.get("methodName") or method.get("name")},
            "scale":{"upstream_id":x.get("scale_id") or scale.get("scaleDbId") or scale.get("id"),"name":x.get("scale_name") or scale.get("scaleName") or scale.get("name")},
        }
    return record
def ingest(payload,kind):
    attempted=rows(payload); out=[]; quarantine=[]; seen=set(); deduped=0
    for x in attempted:
        n=normalize(x,kind)
        if n is None: quarantine.append({"reason":"missing_identity_or_name","raw_sha256":sha(x)}); continue
        key=(n["record_type"],n["upstream_id"])
        if key in seen: deduped+=1; continue
        seen.add(key); out.append(n)
    return out,quarantine,{"attempted":len(attempted),"fetched":len(attempted),"normalized":len(out),"deduped":deduped,"quarantined":len(quarantine),"published":len(out)}
def fetch(url):
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"DTF-THC-ingestion/1.0"})
    with urllib.request.urlopen(req,timeout=30) as r: return json.loads(r.read().decode()),dict(r.headers)
def self_test():
    p={"result":{"data":[{"trait_id":"CO_321:0000020","trait_name":"Plant height","ontology_id":"CO_321","ontology_name":"Wheat"},{"trait_id":"CO_321:0000020","trait_name":"Plant height"},{"trait_id":"broken"}]}}
    n,q,m=ingest(p,"trait")
    assert m=={"attempted":3,"fetched":3,"normalized":1,"deduped":1,"quarantined":1,"published":1}
    assert n[0]["upstream_id"]=="CO_321:0000020" and len(q)==1
    vp={"result":{"data":[{"variable_id":"CO_321:0001199","variable_name":"Plant height - Measurement - cm","trait_id":"CO_321:0000020","trait_name":"Plant height","method_id":"CO_321:0001001","method_name":"Measurement","scale_id":"CO_321:0002001","scale_name":"cm"}]}}
    vn,vq,vm=ingest(vp,"variable")
    assert vm["published"]==1 and not vq
    assert vn[0]["components"]["trait"]["upstream_id"]=="CO_321:0000020"
    assert vn[0]["components"]["method"]["upstream_id"]=="CO_321:0001001"
    assert vn[0]["components"]["scale"]["upstream_id"]=="CO_321:0002001"
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--ontology",default="CO_321"); ap.add_argument("--kind",choices=["trait","variable"],default="trait"); ap.add_argument("--out",type=pathlib.Path); ap.add_argument("--self-test",action="store_true"); a=ap.parse_args()
    if a.self_test: self_test(); print("crop ontology connector self-test: ok"); return
    endpoint=f"{BASE}/{a.kind}s/{urllib.parse.quote(a.ontology,safe='_:')}"
    payload,headers=fetch(endpoint); raw_hash=sha(payload); normalized,quarantine,metrics=ingest(payload,a.kind)
    bundle={"source":{"provider":"Crop Ontology","endpoint":endpoint,"retrieved_from_official_api":True,"raw_sha256":raw_hash,"upstream_version":headers.get("ETag") or headers.get("Last-Modified"),"cursor":None,"parser_version":PARSER_VERSION},"metrics":metrics,"records":normalized,"quarantine":quarantine}
    out=a.out or pathlib.Path(f"dataset/generated/crop_ontology/{a.ontology}_{a.kind}s.json"); out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(canon(bundle)+b"\n"); print(json.dumps(metrics,sort_keys=True))
if __name__=="__main__": main()
