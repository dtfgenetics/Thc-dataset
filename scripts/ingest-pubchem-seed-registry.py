#!/usr/bin/env python3
"""Bounded PubChem seed-registry ingestion with provenance and funnel metrics."""
import argparse, hashlib, json, pathlib, urllib.request
from datetime import datetime, timezone
PARSER_VERSION="pubchem-seed-registry-v1.0.0"
PROPS="Title,MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,InChI,InChIKey,IUPACName"
BASE="https://pubchem.ncbi.nlm.nih.gov/rest/pug"
def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha(v): return hashlib.sha256(v if isinstance(v,bytes) else canon(v)).hexdigest()
def normalize(properties,synonyms,expected):
    bycid={int(x["CID"]):x for x in properties.get("PropertyTable",{}).get("Properties",[])}
    synmap={int(x["CID"]):x.get("Synonym",[]) for x in synonyms.get("InformationList",{}).get("Information",[])}
    out=[]; quarantine=[]; seen=set(); deduped=0
    for seed in expected:
        cid=int(seed["cid"]); row=bycid.get(cid)
        if not row: quarantine.append({"cid":cid,"reason":"missing_property_record"}); continue
        ik=row.get("InChIKey")
        if not ik: quarantine.append({"cid":cid,"reason":"missing_inchikey"}); continue
        key=(cid,ik)
        if key in seen: deduped+=1; continue
        seen.add(key)
        out.append({"compound_id":f"pubchem:{cid}","cid":cid,"preferred_name":seed["preferred_name"],"class":seed["class"],"title":row.get("Title"),"iupac_name":row.get("IUPACName"),"molecular_formula":row.get("MolecularFormula"),"molecular_weight":row.get("MolecularWeight"),"canonical_smiles":row.get("ConnectivitySMILES") or row.get("CanonicalSMILES"),"isomeric_smiles":row.get("SMILES") or row.get("IsomericSMILES"),"inchi":row.get("InChI"),"inchikey":ik,"synonyms":sorted({str(x).strip() for x in synmap.get(cid,[]) if str(x).strip()},key=str.casefold),"source":"PubChem","evidence_scope":"chemical_identity_and_database_reported_properties","biological_claims":False})
    m={"attempted":len(expected),"fetched":len(bycid),"normalized":len(out),"deduped":deduped,"quarantined":len(quarantine),"published":len(out)}
    return out,quarantine,m
def get(url):
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"DTF-THC-ingestion/2.0"})
    with urllib.request.urlopen(req,timeout=45) as r:return r.read(),dict(r.headers)
def self_test():
    seeds=[{"cid":1,"preferred_name":"A","class":"test"},{"cid":2,"preferred_name":"B","class":"test"}]
    p={"PropertyTable":{"Properties":[{"CID":1,"Title":"A","InChIKey":"KEY1"}]}}
    s={"InformationList":{"Information":[{"CID":1,"Synonym":["A","Alias","A"]}]}}
    n,q,m=normalize(p,s,seeds)
    assert m=={"attempted":2,"fetched":1,"normalized":1,"deduped":0,"quarantined":1,"published":1}
    assert n[0]["synonyms"]==["A","Alias"] and n[0]["biological_claims"] is False and q[0]["cid"]==2
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--registry",type=pathlib.Path,default=pathlib.Path("dataset/sources/pubchem_chemistry_registry_v1.json")); ap.add_argument("--out",type=pathlib.Path,default=pathlib.Path("dataset/generated/pubchem/pubchem_seed_snapshot_v1.json")); ap.add_argument("--self-test",action="store_true"); a=ap.parse_args()
    if a.self_test:self_test();print("pubchem seed ingestion self-test: ok");return
    reg=json.loads(a.registry.read_text()); seeds=reg["seed_compounds"]; ids=",".join(str(x["cid"]) for x in seeds)
    purl=f"{BASE}/compound/cid/{ids}/property/{PROPS}/JSON"; surl=f"{BASE}/compound/cid/{ids}/synonyms/JSON"
    praw,ph=get(purl); sraw,sh=get(surl); p=json.loads(praw); s=json.loads(sraw); records,quarantine,metrics=normalize(p,s,seeds)
    now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    bundle={"schema_version":"thc-pubchem-seed-snapshot-v1","source":{"provider":"PubChem","api":"PUG REST","property_endpoint":purl,"synonym_endpoint":surl,"retrieved_at":now,"property_raw_sha256":sha(praw),"synonym_raw_sha256":sha(sraw),"upstream_version":ph.get("Last-Modified") or ph.get("ETag"),"parser_version":PARSER_VERSION,"rights_state":"government_database_source_review_required"},"metrics":metrics,"records":records,"quarantine":quarantine}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(canon(bundle)+b"\n");print(json.dumps(metrics,sort_keys=True))
if __name__=="__main__":main()
