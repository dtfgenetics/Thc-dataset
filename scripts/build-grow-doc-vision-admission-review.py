#!/usr/bin/env python3
"""Build/check the fail-closed Grow Doc vision admission review queue."""
from __future__ import annotations
import argparse,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
CROPS=ROOT/"images/reference/crops-manifest.json"
ORIGINALS=ROOT/"images/reference/manifest.json"
DEFAULT=ROOT/"dataset/reviewed/vision_admission_review_queue_v1.json"
RANK={"high":0,"medium":1,"low":2}
STRONG=re.compile(r"lab-confirmed|controlled|molecular|pathogenicity|peer-reviewed",re.I)

def load(p): return json.loads(p.read_text(encoding="utf-8"))
def build(crops_doc, originals_doc):
    parents={x["id"]:x for x in originals_doc["records"]}
    rows=[]
    for c in crops_doc["records"]:
        p=parents.get(c["parentId"],{})
        blockers=[
          "human diagnostic/scientific review pending",
          "source-group split assignment pending",
          "independent-source/class coverage threshold pending",
        ]
        if c.get("embeddedPanelLabel"): blockers.append("embedded figure/panel label must be removed or explicitly accepted")
        if (c.get("columnContext") or {}).get("referenceOnlyClass") is True: blockers.append("crop is marked reference-only class")
        if not p.get("license"): blockers.append("parent license metadata missing")
        if p.get("intended_use")!="reference-only": blockers.append("unexpected parent intended-use state requires review")
        strong=bool(STRONG.search(str(c.get("confirmation",""))))
        cannabis="cannabis" in str(c.get("host","")).lower() or "cannabis" in str(p.get("host_species","")).lower()
        priority="low"
        if cannabis and not c.get("embeddedPanelLabel") and strong and (c.get("columnContext") or {}).get("referenceOnlyClass") is not True:
            priority="high"
        elif cannabis and not c.get("embeddedPanelLabel"):
            priority="medium"
        rows.append({
          "crop_id":c["id"],"parent_id":c["parentId"],"source_group_id":c["sourceGroupId"],
          "issue_slug":c["issueSlug"],"label":c["label"],"host":c["host"],"view":c["view"],
          "severity":c.get("severity"),"confirmation":c["confirmation"],
          "repository_path":c["repositoryPath"],"sha256":c["sha256"],"perceptual_hash":c["perceptualHash"],
          "parent_source_article":p.get("source_article"),"parent_license":p.get("license"),
          "parent_confirmation":p.get("confirmation"),"parent_host_species":p.get("host_species"),
          "automated_priority":priority,
          "automated_flags":{
            "cannabis_host":cannabis,
            "strong_confirmation_metadata":strong,
            "embedded_panel_label":bool(c.get("embeddedPanelLabel")),
            "reference_only_class":(c.get("columnContext") or {}).get("referenceOnlyClass") is True,
          },
          "review_state":"pending-human-review",
          "review_decision":"pending",
          "training_eligible":False,
          "blockers":blockers,
        })
    rows.sort(key=lambda x:(RANK[x["automated_priority"]],x["crop_id"]))
    counts={k:sum(x["automated_priority"]==k for x in rows) for k in ("high","medium","low")}
    return {
      "schema_version":"grow-doc-vision-admission-review-v1",
      "source_crop_manifest":"images/reference/crops-manifest.json",
      "source_original_manifest":"images/reference/manifest.json",
      "policy":{
        "queue_generation_never_grants_training_eligibility":True,
        "human_review_required":True,
        "confirmation_evidence_required":True,
        "source_group_isolation_required":True,
        "near_duplicate_isolation_required":True,
        "coverage_thresholds_required":True,
      },
      "record_count":len(rows),
      "source_group_count":len({x["source_group_id"] for x in rows}),
      "priority_counts":counts,
      "records":rows,
    }

def validate_queue(doc):
    if doc.get("schema_version")!="grow-doc-vision-admission-review-v1": raise ValueError("unsupported schema")
    rows=doc.get("records")
    if not isinstance(rows,list) or doc.get("record_count")!=len(rows): raise ValueError("record count mismatch")
    if any(x.get("training_eligible") is not False for x in rows): raise ValueError("queue may never grant training eligibility")
    if any(x.get("review_state")!="pending-human-review" or x.get("review_decision")!="pending" for x in rows):
        raise ValueError("generated queue must remain pending human review")
    if len({x["crop_id"] for x in rows})!=len(rows): raise ValueError("duplicate crop_id")
    groups={x["source_group_id"] for x in rows}
    if doc.get("source_group_count")!=len(groups): raise ValueError("source-group count mismatch")
    for key,value in (doc.get("policy") or {}).items():
        if value is not True: raise ValueError(f"policy must remain true: {key}")

def self_test():
    crops={"records":[{"id":"c","parentId":"p","sourceGroupId":"g","issueSlug":"x","label":"x","host":"Cannabis sativa","view":"leaf","confirmation":"lab-confirmed-controlled","repositoryPath":"x.png","sha256":"a"*64,"perceptualHash":"dhash64:0000","embeddedPanelLabel":False}]}
    originals={"records":[{"id":"p","license":"CC BY 4.0","intended_use":"reference-only","source_article":"https://example.test","confirmation":"lab-confirmed","host_species":"Cannabis sativa"}]}
    doc=build(crops,originals);validate_queue(doc)
    assert doc["record_count"]==1 and doc["priority_counts"]["high"]==1
    bad=json.loads(json.dumps(doc));bad["records"][0]["training_eligible"]=True
    try: validate_queue(bad)
    except ValueError: pass
    else: raise AssertionError("training eligibility bypass must fail")
    print("Grow Doc vision admission review self-test: PASS")

def main():
    p=argparse.ArgumentParser();p.add_argument("--output",type=pathlib.Path,default=DEFAULT);p.add_argument("--check",action="store_true");p.add_argument("--self-test",action="store_true");a=p.parse_args()
    if a.self_test:self_test()
    expected=build(load(CROPS),load(ORIGINALS));validate_queue(expected)
    if a.check:
        actual=load(a.output);validate_queue(actual)
        if actual!=expected:
            print("Grow Doc vision admission review: FAIL: generated queue drift");return 2
        print(f"Grow Doc vision admission review: PASS ({expected['record_count']} records, {expected['source_group_count']} source groups)")
        return 0
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(expected,indent=2)+"\n",encoding="utf-8")
    print(f"Wrote {a.output}: {expected['record_count']} records")
    return 0
if __name__=="__main__": raise SystemExit(main())
