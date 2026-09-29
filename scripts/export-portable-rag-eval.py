#!/usr/bin/env python3
"""Export Grow Doc run artifacts to a portable RAG-evaluation JSONL contract.

This adapter is dependency-free and does not score or promote models. It exposes
the same immutable run data in a generic shape usable by external evaluators
without making any external framework part of Grow Doc's promotion authority.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1048576),b""): h.update(chunk)
    return h.hexdigest()

def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

def export(benchmark: Path, responses: Path, snapshot: Path|None) -> list[dict]:
    cases={r["id"]:r for r in load_jsonl(benchmark)}
    retrieval={}
    if snapshot:
        retrieval={r["case_id"]:r for r in load_jsonl(snapshot)}
    out=[]
    seen=set()
    for row in load_jsonl(responses):
        rid=row.get("id")
        if rid not in cases: raise ValueError(f"response id not in benchmark: {rid!r}")
        if rid in seen: raise ValueError(f"duplicate response id: {rid}")
        seen.add(rid)
        case=cases[rid]
        retrieved=(retrieval.get(rid) or {}).get("retrieved",[])
        out.append({
            "id":rid,
            "category":case["category"],
            "input":case["prompt"],
            "actual_output":row.get("response",""),
            "expected_output":"\n".join(case.get("expected_points") or []),
            "retrieval_context":[item["claim"] for item in retrieved],
            "retrieval_source_ids":[item.get("source_ids",[]) for item in retrieved],
            "must_cite":case.get("must_cite") or [],
            "forbidden_claims":case.get("forbidden_claims") or [],
        })
    missing=sorted(set(cases)-seen)
    if missing: raise ValueError(f"responses missing benchmark ids: {missing}")
    return out

def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); b=root/"b.jsonl"; r=root/"r.jsonl"; s=root/"s.jsonl"
        b.write_text(json.dumps({"id":"x","category":"factuality","prompt":"p","expected_points":["e"],"must_cite":["doi:x"],"forbidden_claims":["f"]})+"\n")
        r.write_text(json.dumps({"id":"x","response":"a"})+"\n")
        s.write_text(json.dumps({"case_id":"x","retrieved":[{"claim":"ctx","source_ids":["doi:x"]}]})+"\n")
        rows=export(b,r,s)
        assert rows[0]["input"]=="p" and rows[0]["actual_output"]=="a"
        assert rows[0]["retrieval_context"]==["ctx"] and rows[0]["expected_output"]=="e"
    print("portable eval artifact exporter self-test: PASS")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--benchmark",default="model_tuning/eval/heldout_v3.jsonl")
    p.add_argument("--responses")
    p.add_argument("--retrieval-snapshot")
    p.add_argument("--out")
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test: self_test(); return 0
    if not a.responses or not a.out: p.error("--responses and --out are required")
    b=Path(a.benchmark); r=Path(a.responses); s=Path(a.retrieval_snapshot) if a.retrieval_snapshot else None
    rows=export(b,r,s)
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text("".join(json.dumps(x,sort_keys=True,ensure_ascii=False)+"\n" for x in rows),encoding="utf-8")
    manifest={"schema_version":"grow-doc-portable-rag-eval-v1","promotion_eligible":False,"benchmark_sha256":sha256(b),"responses_sha256":sha256(r),"retrieval_snapshot_sha256":sha256(s) if s else None,"records":len(rows)}
    Path(str(out)+".manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(manifest,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
