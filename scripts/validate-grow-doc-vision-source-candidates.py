#!/usr/bin/env python3
"""Validate provenance-controlled Grow Doc vision source candidates."""
from __future__ import annotations
import argparse,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
DEFAULT=ROOT/"dataset/acquisition/vision-source-candidates-v1.json"
DOI=re.compile(r"^doi:10\.\d{4,9}/\S+$",re.I)

def fail(msg): raise ValueError(msg)

def validate_doc(doc):
    if doc.get("schema_version")!="grow-doc-vision-source-candidates-v1":
        fail("unsupported vision source candidate schema")
    policy=doc.get("policy") or {}
    for key in (
        "candidate_registry_never_grants_training_eligibility",
        "exact_child_asset_rights_must_be_verified",
        "human_scientific_review_required",
        "source_group_and_duplicate_controls_required",
    ):
        if policy.get(key) is not True:
            fail(f"policy {key} must be true")
    rows=doc.get("sources")
    if not isinstance(rows,list) or not rows:
        fail("sources must be a non-empty list")
    seen=set()
    for row in rows:
        sid=row.get("source_id")
        if not isinstance(sid,str) or not sid.strip() or sid in seen:
            fail(f"invalid or duplicate source_id: {sid!r}")
        seen.add(sid)
        if row.get("training_eligible") is not False:
            fail(f"{sid}: candidate registry may never set training_eligible=true")
        url=row.get("canonical_url")
        if not isinstance(url,str) or not url.startswith("https://"):
            fail(f"{sid}: canonical_url must be https")
        pids=row.get("persistent_ids")
        if not isinstance(pids,list):
            fail(f"{sid}: persistent_ids must be a list")
        for pid in pids:
            if not DOI.fullmatch(str(pid)):
                fail(f"{sid}: unsupported persistent id {pid}")
        rel=row.get("related_image_dois")
        if not isinstance(rel,list):
            fail(f"{sid}: related_image_dois must be a list")
        for pid in rel:
            if not DOI.fullmatch(str(pid)):
                fail(f"{sid}: invalid related image DOI {pid}")
        for key in ("title","host_species","parent_record_license","rights_status","scientific_status","intended_lane","admission_state","notes"):
            if not isinstance(row.get(key),str) or not row[key].strip():
                fail(f"{sid}: {key} required")
        if row["admission_state"] not in {"pre-admission-rights-review","reference-only-rights-limited","quarantine-rights-unknown"}:
            fail(f"{sid}: invalid admission_state")
        if row["host_species"]!="Cannabis sativa":
            fail(f"{sid}: only Cannabis sativa sources belong in this registry")
        if not isinstance(row.get("scope"),list) or not row["scope"]:
            fail(f"{sid}: scope required")
        blockers=row.get("blockers")
        if not isinstance(blockers,list) or not blockers:
            fail(f"{sid}: unresolved blockers required while training_eligible=false")
        rights=(row["rights_status"]+" "+row["parent_record_license"]).lower()
        unresolved=any(token in rights for token in ("not explicit","not verified","quarantine","verify exact","verification pending"))
        if unresolved and row["admission_state"]=="pre-admission-rights-review":
            if not row["intended_lane"].startswith("candidate-"):
                fail(f"{sid}: pre-admission source must use a candidate lane")
        if row["admission_state"] in {"reference-only-rights-limited","quarantine-rights-unknown"}:
            if row["intended_lane"] not in {"reference-only","reference-or-healthy-morphology-candidate"}:
                fail(f"{sid}: rights-limited/quarantined source cannot claim supervised intent")
    return {"sources":len(rows)}

def self_test():
    good={
      "schema_version":"grow-doc-vision-source-candidates-v1",
      "policy":{
        "candidate_registry_never_grants_training_eligibility":True,
        "exact_child_asset_rights_must_be_verified":True,
        "human_scientific_review_required":True,
        "source_group_and_duplicate_controls_required":True,
      },
      "sources":[{
        "source_id":"x","title":"x","canonical_url":"https://example.test/x","persistent_ids":[],
        "related_image_dois":[],"host_species":"Cannabis sativa","scope":["x"],
        "parent_record_license":"CC BY 4.0","rights_status":"open parent; child verification pending",
        "scientific_status":"study linked","intended_lane":"candidate-supervised-environmental-stress","admission_state":"pre-admission-rights-review",
        "training_eligible":False,"blockers":["review"],"notes":"x"
      }]
    }
    validate_doc(good)
    bad=json.loads(json.dumps(good));bad["sources"][0]["training_eligible"]=True
    try: validate_doc(bad)
    except ValueError: pass
    else: raise AssertionError("candidate training eligibility must fail")
    print("Grow Doc vision source candidate self-test: PASS")

def main():
    p=argparse.ArgumentParser();p.add_argument("--registry",type=pathlib.Path,default=DEFAULT);p.add_argument("--self-test",action="store_true");a=p.parse_args()
    try:
        doc=json.loads(a.registry.read_text(encoding="utf-8"))
        result=validate_doc(doc)
        if a.self_test:self_test()
        else:print(json.dumps({"ok":True,**result},sort_keys=True))
    except (OSError,json.JSONDecodeError,ValueError) as exc:
        print(f"Grow Doc vision source candidates: FAIL: {exc}");return 2
    return 0
if __name__=="__main__":raise SystemExit(main())
