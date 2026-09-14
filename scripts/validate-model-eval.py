#!/usr/bin/env python3
"""Validate locked Grow Doc model-evaluation JSONL with only the Python stdlib."""
from __future__ import annotations
import argparse, json, pathlib, sys

REQUIRED = {"id","category","difficulty","prompt","expected_points","must_cite","forbidden_claims","source_metadata"}
ALLOWED = {"factuality","diagnostic","science","citation_accuracy","hallucination","education","regression","grounded_qa"}
ALLOWED_DIFFICULTIES = {"easy","medium","hard"}
REQUIRED_SOURCE_METADATA = {"source_id","title","year"}

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
    for extra_doi in meta.get("additional_dois") or []:
        extra_doi=str(extra_doi).strip()
        if extra_doi:
            ids.add(canonical_source_id(f"doi:{extra_doi}"))
    for extra_url in meta.get("additional_urls") or []:
        extra_url=str(extra_url).strip()
        if extra_url:
            ids.add(canonical_source_id(f"url:{extra_url}"))
    return ids

def validate(path: pathlib.Path, *, require_all_categories: bool = True) -> list[str]:
    errors=[]
    seen=set()
    category_counts={category: 0 for category in ALLOWED}
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
        if not isinstance(rid, str) or not rid.strip():
            errors.append(f"{path}:{lineno}: id must be a non-empty string")
        elif rid in seen:
            errors.append(f"{path}:{lineno}: duplicate id {rid!r}")
        seen.add(rid)

        category=row.get("category")
        if category not in ALLOWED:
            errors.append(f"{path}:{lineno}: unsupported category {category!r}")
        else:
            category_counts[category] += 1
        if row.get("difficulty") not in ALLOWED_DIFFICULTIES:
            errors.append(f"{path}:{lineno}: unsupported difficulty {row.get('difficulty')!r}")
        prompt=row.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append(f"{path}:{lineno}: prompt must be a non-empty string")

        points=row.get("expected_points")
        cites=row.get("must_cite")
        forbidden=row.get("forbidden_claims")
        if not isinstance(points, list) or not points or not all(isinstance(point, str) and point.strip() for point in points):
            errors.append(f"{path}:{lineno}: expected_points must be a non-empty list of non-empty strings")
            points=[]
        if not isinstance(cites, list) or not cites:
            errors.append(f"{path}:{lineno}: must_cite must be non-empty list")
            cites=[]
        if not isinstance(forbidden, list) or not all(isinstance(claim, str) and claim.strip() for claim in forbidden):
            errors.append(f"{path}:{lineno}: forbidden_claims must be a list of non-empty strings")

        meta=row.get("source_metadata")
        if not isinstance(meta, dict):
            errors.append(f"{path}:{lineno}: source_metadata must be an object")
            meta={}
        missing_meta=REQUIRED_SOURCE_METADATA-meta.keys()
        if missing_meta:
            errors.append(f"{path}:{lineno}: source_metadata missing fields: {sorted(missing_meta)}")
        if not isinstance(meta.get("source_id"), str) or not str(meta.get("source_id") or "").strip():
            errors.append(f"{path}:{lineno}: source_metadata.source_id must be a non-empty string")
        if not isinstance(meta.get("title"), str) or not str(meta.get("title") or "").strip():
            errors.append(f"{path}:{lineno}: source_metadata.title must be a non-empty string")
        year=meta.get("year")
        if not isinstance(year, int) or isinstance(year, bool) or year < 1900 or year > 2100:
            errors.append(f"{path}:{lineno}: source_metadata.year must be an integer from 1900 through 2100")
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

    if require_all_categories:
        missing_categories=sorted(category for category, count in category_counts.items() if count == 0)
        if missing_categories:
            errors.append(f"{path}: missing required evaluation categories: {missing_categories}")
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
        "source_metadata":{"source_id":"fixture","title":"Fixture source","doi":"10.1000/ABC","year":2026},
    }
    with tempfile.TemporaryDirectory() as td:
        path=pathlib.Path(td)/"eval.jsonl"
        path.write_text(json.dumps(base)+"\n",encoding="utf-8")
        assert validate(path, require_all_categories=False) == []

        bad=dict(base)
        bad["must_cite"]=["doi:10.1000/wrong"]
        path.write_text(json.dumps(bad)+"\n",encoding="utf-8")
        assert any("not represented by source_metadata" in e for e in validate(path, require_all_categories=False))

        bad_difficulty=dict(base, difficulty="expert")
        path.write_text(json.dumps(bad_difficulty)+"\n",encoding="utf-8")
        assert any("unsupported difficulty" in e for e in validate(path, require_all_categories=False))

        bad_forbidden=dict(base, forbidden_claims="not a list")
        path.write_text(json.dumps(bad_forbidden)+"\n",encoding="utf-8")
        assert any("forbidden_claims must be a list" in e for e in validate(path, require_all_categories=False))

        bad_meta=dict(base)
        bad_meta["source_metadata"]={"doi":"10.1000/abc"}
        path.write_text(json.dumps(bad_meta)+"\n",encoding="utf-8")
        assert any("source_metadata missing fields" in e for e in validate(path, require_all_categories=False))

        multi=dict(base)
        multi["must_cite"]=["doi:10.1000/abc","doi:10.1000/extra"]
        multi["source_metadata"]=dict(base["source_metadata"], additional_dois=["10.1000/EXTRA"])
        path.write_text(json.dumps(multi)+"\n",encoding="utf-8")
        assert validate(path, require_all_categories=False) == []

        multi_url=dict(base)
        multi_url["must_cite"]=["doi:10.1000/abc","url:https://example.org/source"]
        multi_url["source_metadata"]=dict(base["source_metadata"], additional_urls=["https://example.org/source"])
        path.write_text(json.dumps(multi_url)+"\n",encoding="utf-8")
        assert validate(path, require_all_categories=False) == []

        rows=[]
        for index, category in enumerate(sorted(ALLOWED)):
            row=dict(base, id=f"case-{index}", category=category)
            rows.append(json.dumps(row))
        path.write_text("\n".join(rows)+"\n",encoding="utf-8")
        assert validate(path) == []
        path.write_text("\n".join(rows[:-1])+"\n",encoding="utf-8")
        assert any("missing required evaluation categories" in e for e in validate(path))
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
