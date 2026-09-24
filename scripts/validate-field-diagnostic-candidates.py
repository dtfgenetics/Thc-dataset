#!/usr/bin/env python3
"""Fail closed on Grow Doc field-diagnostic candidate records.

The candidate file is optional until population begins. If it exists, every row
must preserve the evaluation-only boundary and basic provenance/evidence rules.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PATH = Path("model_tuning/eval/field_diagnostic_candidates.jsonl")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
CASE_ID = re.compile(r"^gdfd-[a-z0-9][a-z0-9._-]*$")
ALLOWED_STATUS = {"candidate", "reviewed_candidate"}
ALLOWED_MEDIA = {"image", "video"}
ALLOWED_DIRECTNESS = {"direct", "supporting", "background", "conflicting"}
ALLOWED_TIERS = {"primary_peer_reviewed", "review_peer_reviewed", "institutional", "reference_database", "other_reviewed"}


def load(path: Path = PATH) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for i, row in enumerate(rows, 1):
        cid = row.get("case_id")
        label = str(cid or f"row-{i}")
        if not isinstance(cid, str) or not CASE_ID.fullmatch(cid):
            errors.append(f"{label}: invalid case_id")
        elif cid in seen:
            errors.append(f"{label}: duplicate case_id")
        else:
            seen.add(cid)
        if row.get("schema_version") != "grow-doc-field-diagnostic-v0":
            errors.append(f"{label}: wrong schema_version")
        if row.get("status") not in ALLOWED_STATUS:
            errors.append(f"{label}: candidates cannot be frozen")
        if row.get("evaluation_only_never_training") is not True:
            errors.append(f"{label}: evaluation_only_never_training must be true")
        families = row.get("case_families")
        if not isinstance(families, list) or not families or len(families) != len(set(families)):
            errors.append(f"{label}: case_families must be a non-empty unique list")
        media = row.get("media")
        if not isinstance(media, list) or not media:
            errors.append(f"{label}: media must be non-empty")
        else:
            for m in media:
                if not isinstance(m, dict) or m.get("media_type") not in ALLOWED_MEDIA or not SHA256.fullmatch(str(m.get("sha256", ""))):
                    errors.append(f"{label}: malformed media record/hash")
                    break
                if not str(m.get("provenance", "")).strip() or not str(m.get("license", "")).strip():
                    errors.append(f"{label}: media provenance/license required")
                    break
        expected = row.get("expected")
        if not isinstance(expected, dict) or not isinstance(expected.get("observations"), list) or not isinstance(expected.get("differential"), list) or not isinstance(expected.get("uncertainty"), dict):
            errors.append(f"{label}: expected observations/differential/uncertainty required")
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{label}: at least one reviewed evidence record required")
        else:
            for ev in evidence:
                if not isinstance(ev, dict) or not str(ev.get("source_id", "")).strip() or not str(ev.get("citation", "")).strip() or not str(ev.get("claim_scope", "")).strip():
                    errors.append(f"{label}: evidence source/citation/claim_scope required")
                    break
                if ev.get("evidence_tier") not in ALLOWED_TIERS or ev.get("directness") not in ALLOWED_DIRECTNESS:
                    errors.append(f"{label}: invalid evidence tier/directness")
                    break
    return errors


def self_test() -> None:
    good = [{
        "schema_version":"grow-doc-field-diagnostic-v0","case_id":"gdfd-self-test","status":"candidate","evaluation_only_never_training":True,
        "case_families":["clean"],"media":[{"media_id":"m1","media_type":"image","sha256":"a"*64,"provenance":"test fixture","license":"test-only"}],
        "expected":{"observations":[],"differential":[],"uncertainty":{"abstention_expected":True,"reason":"fixture"}},
        "evidence":[{"source_id":"s1","citation":"test fixture","claim_scope":"validator fixture","evidence_tier":"other_reviewed","directness":"background"}]
    }]
    assert not validate(good), validate(good)
    bad = json.loads(json.dumps(good)); bad[0]["evaluation_only_never_training"] = False
    assert validate(bad)
    bad = json.loads(json.dumps(good)); bad[0]["media"][0]["sha256"] = "bad"
    assert validate(bad)
    bad = json.loads(json.dumps(good)); bad.append(json.loads(json.dumps(good[0])))
    assert validate(bad)
    print("field diagnostic candidate validator self-test: PASS")


def main() -> int:
    self_test()
    rows = load()
    if not rows:
        print(f"field diagnostic candidate file not populated yet: {PATH}")
        return 0
    errors = validate(rows)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"field diagnostic candidates valid: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
