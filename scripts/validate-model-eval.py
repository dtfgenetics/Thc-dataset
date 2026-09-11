#!/usr/bin/env python3
"""Validate locked Grow Doc model-evaluation JSONL with only the Python stdlib."""
from __future__ import annotations
import argparse, json, pathlib, sys

REQUIRED = {"id","category","difficulty","prompt","expected_points","must_cite","forbidden_claims","source_metadata"}
ALLOWED = {"factuality","diagnostic","science","citation_accuracy","hallucination","education","regression","grounded_qa"}

def canonical_source_id(value: str) -> str:
    value=str(value or "").strip()
    prefix, sep, rest=value.partition(":")
    if not sep:
        return value
    prefix=prefix.lower()
    rest=rest.strip()
    if prefix == "doi":
        return f"doi:{rest.lower()}"
    if prefix in {"url", "source"}:
        return f"{prefix}:{rest}"
    return value

def source_metadata_citation_ids(meta: dict) -> set[str]:
    ids=set()
    doi=meta.get("doi")
    url=meta.get("url")
    source_id=meta.get("source_id")
    if doi:
        ids.add(canonical_source_id(f"doi:{doi}"))
    if url:
        ids.add(canonical_source_id(f"url:{url}"))
    if source_id:
        ids.add(canonical_source_id(f"source:{source_id}"))
    return ids

def validate(path: pathlib.Path) -> list[str]:
    errors=[]
    seen=set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row=json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{lineno}: invalid JSON: {exc}")
            continue
        missing=REQUIRED-row.keys()
        if missing:
            errors.append(f"{path}:{lineno}: missing fields: {sorted(missing)}")
        rid=row.get("id")
        if rid in seen:
            errors.append(f"{path}:{lineno}: duplicate id {rid!r}")
        seen.add(rid)
        if row.get("category") not in ALLOWED:
            errors.append(f"{path}:{lineno}: unsupported category {row.get('category')!r}")
        points=row.get("expected_points")
        cites=row.get("must_cite")
        if not isinstance(points, list) or not points:
            errors.append(f"{path}:{lineno}: expected_points must be non-empty list")
            points=[]
        if not isinstance(cites, list) or not cites:
            errors.append(f"{path}:{lineno}: must_cite must be non-empty list")
            cites=[]
        meta=row.get("source_metadata") or {}
        if not (meta.get("doi") or meta.get("url")):
            errors.append(f"{path}:{lineno}: source_metadata requires doi or url")
        canonical_cites={canonical_source_id(c) for c in cites if isinstance(c, str)}
        metadata_ids=source_metadata_citation_ids(meta)
        for cite in cites:
            if not isinstance(cite, str) or not (cite.startswith("doi:") or cite.startswith("url:") or cite.startswith("source:")):
                errors.append(f"{path}:{lineno}: unsupported citation identifier {cite!r}")
                continue
            canonical=canonical_source_id(cite)
            if canonical not in metadata_ids:
                errors.append(f"{path}:{lineno}: must_cite identifier is not represented by source_metadata: {cite!r}")

        bindings=row.get("claim_source_bindings")
        if bindings is not None:
            if not isinstance(bindings, list) or len(bindings) != len(points):
                errors.append(f"{path}:{lineno}: claim_source_bindings must contain one binding per expected_point")
            else:
                for index, binding in enumerate(bindings):
                    if not isinstance(binding, list) or not binding:
                        errors.append(f"{path}:{lineno}: claim_source_bindings[{index}] must be a non-empty citation list")
                        continue
                    for cite in binding:
                        canonical=canonical_source_id(cite) if isinstance(cite, str) else ""
                        if not canonical or canonical not in canonical_cites:
                            errors.append(f"{path}:{lineno}: claim_source_bindings[{index}] references citation outside must_cite: {cite!r}")
    return errors

def self_test() -> int:
    import tempfile
    base={
        "id":"x",
        "category":"citation_accuracy",
        "difficulty":"medium",
        "prompt":"p",
        "expected_points":["e"],
        "must_cite":["doi:10.1000/abc"],
        "forbidden_claims":[],
        "source_metadata":{"source_id":"fixture","doi":"10.1000/ABC","year":2026},
    }
    with tempfile.TemporaryDirectory() as td:
        path=pathlib.Path(td)/"eval.jsonl"
        path.write_text(json.dumps(base)+"\n",encoding="utf-8")
        assert validate(path) == []
        bad=dict(base)
        bad["must_cite"]=["doi:10.1000/wrong"]
        path.write_text(json.dumps(bad)+"\n",encoding="utf-8")
        assert any("not represented by source_metadata" in e for e in validate(path))
    print("OK: validate-model-eval self-test")
    return 0

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="model_tuning/eval/heldout_v2.jsonl")
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()
    if args.self_test:
        return self_test()
    errors=validate(pathlib.Path(args.path))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"OK: {args.path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
