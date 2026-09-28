#!/usr/bin/env python3
"""Validate final heldout-v3 replication candidates against reviewed source research."""
import json
from pathlib import Path

CANDIDATES = Path("model_tuning/eval/candidates/heldout_v3_final_replication_v1.jsonl")
RESEARCH = Path("model_tuning/eval/candidates/heldout_v3_gap_source_research_v1.json")
EXPECTED = {"hallucination", "education", "regression"}

def canonical_doi(value):
    value = str(value or "").strip().lower()
    return value[4:] if value.startswith("doi:") else value

def validate(rows, research):
    errors = []
    sources = {r["target_slice"]: r for r in research.get("sources", [])}
    if set(sources) != EXPECTED: errors.append("research must cover exactly final replication slices")
    if len(rows) != 3 or {r.get("category") for r in rows} != EXPECTED: errors.append("exactly one candidate per final replication slice is required")
    ids = [r.get("id") for r in rows]
    if len(set(ids)) != len(ids) or any(not x for x in ids): errors.append("candidate ids must be unique and non-empty")
    seen_dois = set()
    for row in rows:
        label = row.get("id") or "unnamed"
        category = row.get("category")
        source = row.get("source_metadata") or {}
        reviewed = sources.get(category) or {}
        doi = canonical_doi(source.get("doi"))
        cites = {canonical_doi(x) for x in row.get("must_cite") or []}
        if row.get("candidate_status") != "reviewed_replication_candidate": errors.append(f"{label}: invalid candidate_status")
        if row.get("promotion_eligible") is not False: errors.append(f"{label}: promotion_eligible must remain false")
        if row.get("rag_first") is not True: errors.append(f"{label}: rag_first must remain true")
        if row.get("difficulty") not in {"medium", "hard"}: errors.append(f"{label}: invalid difficulty")
        if len(row.get("expected_points") or []) < 2: errors.append(f"{label}: expected_points needs >=2 points")
        if not row.get("forbidden_claims"): errors.append(f"{label}: forbidden_claims required")
        if not doi or doi not in cites: errors.append(f"{label}: citation must match source DOI")
        if doi in seen_dois: errors.append(f"{label}: duplicate DOI")
        seen_dois.add(doi)
        if source.get("source_id") != reviewed.get("source_id") or doi != canonical_doi(reviewed.get("doi")): errors.append(f"{label}: source does not match reviewed research")
        if reviewed.get("source_identity_verified") is not True or reviewed.get("claim_scope_review") != "pass": errors.append(f"{label}: source research is not fully reviewed")
        if source.get("publisher_url") != reviewed.get("publisher_url"): errors.append(f"{label}: publisher provenance mismatch")
    return errors

def load_rows():
    return [json.loads(x) for x in CANDIDATES.read_text(encoding="utf-8").splitlines() if x.strip()]

if __name__ == "__main__":
    rows = load_rows(); research = json.loads(RESEARCH.read_text(encoding="utf-8")); errors = validate(rows, research)
    if errors:
        print("\n".join("ERROR: " + e for e in errors)); raise SystemExit(1)
    bad = json.loads(json.dumps(rows)); bad[0]["promotion_eligible"] = True
    assert any("promotion_eligible" in e for e in validate(bad, research))
    bad = json.loads(json.dumps(rows)); bad[1]["source_metadata"]["doi"] = "10.0000/wrong"
    assert any("citation must match" in e or "does not match" in e for e in validate(bad, research))
    print("heldout-v3 final replication candidates: PASS")
