#!/usr/bin/env python3
"""Validate locked Grow Doc model-evaluation JSONL with only the Python stdlib."""
from __future__ import annotations
import argparse, json, pathlib, sys

REQUIRED = {"id","category","difficulty","prompt","expected_points","must_cite","forbidden_claims","source_metadata"}
ALLOWED = {"factuality","diagnostic","science","citation_accuracy","hallucination","education","regression","grounded_qa"}

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
        if not isinstance(row.get("expected_points"), list) or not row.get("expected_points"):
            errors.append(f"{path}:{lineno}: expected_points must be non-empty list")
        if not isinstance(row.get("must_cite"), list) or not row.get("must_cite"):
            errors.append(f"{path}:{lineno}: must_cite must be non-empty list")
        meta=row.get("source_metadata") or {}
        if not (meta.get("doi") or meta.get("url")):
            errors.append(f"{path}:{lineno}: source_metadata requires doi or url")
        for cite in row.get("must_cite", []):
            if not (cite.startswith("doi:") or cite.startswith("url:") or cite.startswith("source:")):
                errors.append(f"{path}:{lineno}: unsupported citation identifier {cite!r}")
    return errors

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="model_tuning/eval/heldout_v1.jsonl")
    args=ap.parse_args()
    errors=validate(pathlib.Path(args.path))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"OK: {args.path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
