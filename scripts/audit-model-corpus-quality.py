#!/usr/bin/env python3
"""Audit Grow Doc diagnostic source data before model-corpus construction.

Dependency-free and intentionally conservative: reports corroborated duplicate claims but fails
on identity collisions, missing scientific provenance, unreviewed records that could be mistaken
for verified material, and training-eligible media without explicit permission.
"""
from __future__ import annotations

import argparse, json, pathlib, re, sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"

def norm(v: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (v or "").lower())).strip()

def load(path: pathlib.Path):
    rows=[]
    for n,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
        if line.strip():
            try: rows.append(json.loads(line))
            except json.JSONDecodeError as e: raise ValueError(f"{path}:{n}: invalid JSON: {e}") from e
    return rows

def audit(rows):
    errors=[]; warnings=[]
    ids=Counter(r.get("id") for r in rows); slugs=Counter(r.get("slug") for r in rows)
    for k,c in ids.items():
        if not k or c>1: errors.append(f"profile id collision/missing: {k!r} count={c}")
    for k,c in slugs.items():
        if not k or c>1: errors.append(f"profile slug collision/missing: {k!r} count={c}")
    claim_sources={}
    reviewed=0; quarantinable=0; sources=0; claims=0; media=0
    for r in rows:
        pid=r.get("id") or "<missing>"
        if r.get("reviewStatus")=="reviewed": reviewed+=1
        else:
            quarantinable+=1
            warnings.append(f"{pid}: reviewStatus={r.get('reviewStatus')!r}; must remain outside verified SFT")
        srcs=r.get("sources") or []
        if not srcs: errors.append(f"{pid}: no sources")
        for s in srcs:
            sources+=1
            sid=(s.get("doi") or s.get("url") or "").strip()
            sc=s.get("supportedClaims") or []
            if not sid: errors.append(f"{pid}: source lacks DOI/URL: {s.get('title')!r}")
            if not sc: errors.append(f"{pid}: source has no supportedClaims: {s.get('title')!r}")
            for c in sc:
                claims+=1; key=norm(c)
                if not key: errors.append(f"{pid}: empty supported claim")
                else: claim_sources.setdefault(key,set()).add(sid)
        for m in r.get("media") or []:
            media+=1
            if m.get("trainingEligible") is True and m.get("trainingPermission") not in {"permitted","allowed","approved"}:
                errors.append(f"{pid}: media {m.get('id')!r} is trainingEligible without explicit permission")
            if m.get("trainingPermission") in {"not-permitted","unknown"} and m.get("trainingEligible") is True:
                errors.append(f"{pid}: prohibited/unknown-rights media marked trainingEligible: {m.get('id')!r}")
    corroborated=sum(1 for v in claim_sources.values() if len(v)>1)
    return {
      "profiles":len(rows),"reviewed_profiles":reviewed,"nonreviewed_profiles":quarantinable,
      "sources":sources,"supported_claims":claims,"media_records":media,
      "corroborated_exact_claims":corroborated,"errors":errors,"warnings":warnings,
    }

def self_test():
    good={"id":"p1","slug":"p1","reviewStatus":"reviewed","sources":[{"doi":"10.x/a","supportedClaims":["Claim A"]}],"media":[{"id":"m1","trainingEligible":False,"trainingPermission":"not-permitted"}]}
    assert not audit([good])["errors"]
    bad=json.loads(json.dumps(good)); bad["media"][0].update(trainingEligible=True)
    assert audit([bad])["errors"]
    dup=json.loads(json.dumps(good)); assert audit([good,dup])["errors"]
    print("model corpus quality self-test: PASS")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",default=str(DEFAULT_INPUT)); ap.add_argument("--self-test",action="store_true"); args=ap.parse_args()
    if args.self_test: self_test(); return 0
    report=audit(load(pathlib.Path(args.input))); print(json.dumps(report,indent=2))
    if report["errors"]:
        print(f"corpus quality audit: FAIL ({len(report['errors'])} errors)",file=sys.stderr); return 1
    print("corpus quality audit: PASS"); return 0
if __name__=="__main__": raise SystemExit(main())
