#!/usr/bin/env python3
"""Validate alternate heldout-v3 challenge candidates against reviewed source research."""
import json
from pathlib import Path
CANDIDATES=Path("model_tuning/eval/candidates/heldout_v3_alternate_challenges_v1.jsonl")
RESEARCH=Path("model_tuning/eval/candidates/heldout_v3_gap_source_research_v1.json")
EXPECTED={"hallucination","education","regression"}
def doi(v):
 v=str(v or "").strip().lower(); return v[4:] if v.startswith("doi:") else v
def validate(rows,research):
 errors=[]; sources={r["target_slice"]:r for r in research.get("sources",[])}
 if set(sources)!=EXPECTED: errors.append("research must cover exactly alternate challenge slices")
 if len(rows)!=3 or {r.get("category") for r in rows}!=EXPECTED: errors.append("exactly one alternate challenge per slice is required")
 ids=[r.get("id") for r in rows]
 if len(set(ids))!=len(ids) or any(not x for x in ids): errors.append("candidate ids must be unique and non-empty")
 seen=set()
 for row in rows:
  label=row.get("id") or "unnamed"; source=row.get("source_metadata") or {}; reviewed=sources.get(row.get("category")) or {}; d=doi(source.get("doi")); cites={doi(x) for x in row.get("must_cite") or []}
  if row.get("candidate_status")!="reviewed_replication_candidate": errors.append(f"{label}: invalid candidate_status")
  if row.get("promotion_eligible") is not False: errors.append(f"{label}: promotion_eligible must remain false")
  if row.get("rag_first") is not True: errors.append(f"{label}: rag_first must remain true")
  if len(row.get("expected_points") or [])<2 or not row.get("forbidden_claims"): errors.append(f"{label}: scoring requirements incomplete")
  if not d or d not in cites: errors.append(f"{label}: citation must match source DOI")
  if d in seen: errors.append(f"{label}: duplicate DOI")
  seen.add(d)
  if source.get("source_id")!=reviewed.get("source_id") or d!=doi(reviewed.get("doi")): errors.append(f"{label}: source does not match reviewed research")
  if reviewed.get("source_identity_verified") is not True or reviewed.get("claim_scope_review")!="pass": errors.append(f"{label}: source research is not fully reviewed")
  if source.get("publisher_url")!=reviewed.get("publisher_url"): errors.append(f"{label}: publisher provenance mismatch")
 return errors
if __name__=="__main__":
 rows=[json.loads(x) for x in CANDIDATES.read_text(encoding="utf-8").splitlines() if x.strip()]; research=json.loads(RESEARCH.read_text(encoding="utf-8")); errors=validate(rows,research)
 if errors: print("\n".join("ERROR: "+e for e in errors)); raise SystemExit(1)
 bad=json.loads(json.dumps(rows)); bad[0]["promotion_eligible"]=True; assert any("promotion_eligible" in e for e in validate(bad,research))
 print("heldout-v3 alternate challenge candidates: PASS")
