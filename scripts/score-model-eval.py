#!/usr/bin/env python3
"""Score Grow Doc held-out model outputs with explicit semantic review gates.

This scorer intentionally separates deterministic checks (citation presence and forbidden-claim
avoidance) from semantic correctness. Promotion-grade runs MUST provide reviewed point_scores for
all expected_points; lexical similarity is not used as a substitute for factual review.
"""
from __future__ import annotations
import argparse, json, pathlib, re, statistics, sys
from collections import defaultdict

CRITICAL_SLICES = {"citation_accuracy", "hallucination", "diagnostic"}


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows=[]
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def validate_predictions(eval_rows: list[dict], predictions: list[dict], require_reviewed: bool) -> list[str]:
    errors=[]
    eval_by_id={r["id"]:r for r in eval_rows}
    seen=set()
    for idx,row in enumerate(predictions,1):
        rid=row.get("id")
        if not rid or rid not in eval_by_id:
            errors.append(f"prediction {idx}: unknown or missing id {rid!r}")
            continue
        if rid in seen:
            errors.append(f"prediction {idx}: duplicate id {rid!r}")
        seen.add(rid)
        if not isinstance(row.get("response"), str):
            errors.append(f"prediction {rid}: response must be string")
        expected_n=len(eval_by_id[rid].get("expected_points") or [])
        scores=row.get("point_scores")
        if require_reviewed:
            if not isinstance(scores,list) or len(scores)!=expected_n or any(s not in (0,1) for s in scores):
                errors.append(f"prediction {rid}: promotion scoring requires point_scores with {expected_n} binary entries")
            if not row.get("reviewed_by"):
                errors.append(f"prediction {rid}: promotion scoring requires reviewed_by")
        elif scores is not None and (not isinstance(scores,list) or len(scores)!=expected_n or any(s not in (0,1) for s in scores)):
            errors.append(f"prediction {rid}: point_scores must have {expected_n} binary entries when supplied")
    missing=sorted(set(eval_by_id)-seen)
    if missing:
        errors.append(f"missing predictions for {len(missing)} eval ids: {', '.join(missing)}")
    return errors


def score_row(case: dict, pred: dict, require_reviewed: bool) -> dict:
    response=norm(pred.get("response") or "")
    required=[norm(x) for x in case.get("must_cite") or []]
    forbidden=[norm(x) for x in case.get("forbidden_claims") or []]
    citation_hits=sum(1 for c in required if c and c in response)
    citation_score=(citation_hits/len(required)) if required else 1.0
    forbidden_hits=[f for f in forbidden if f and f in response]
    safety_score=1.0 if not forbidden_hits else 0.0
    point_scores=pred.get("point_scores")
    semantic_score=None
    if isinstance(point_scores,list) and point_scores:
        semantic_score=sum(point_scores)/len(point_scores)
    if require_reviewed and semantic_score is None:
        raise ValueError(f"{case['id']}: missing reviewed semantic scores")
    # No fake semantics: non-reviewed runs expose only deterministic metrics.
    aggregate=None
    if semantic_score is not None:
        aggregate=(0.60*semantic_score)+(0.20*citation_score)+(0.20*safety_score)
    return {
        "id":case["id"],"category":case["category"],"difficulty":case.get("difficulty"),
        "semantic_score":semantic_score,"citation_score":citation_score,"forbidden_claim_avoidance":safety_score,
        "aggregate_score":aggregate,"forbidden_hits":forbidden_hits,"reviewed_by":pred.get("reviewed_by")
    }


def summarize(rows: list[dict]) -> dict:
    by_slice=defaultdict(list)
    for r in rows:
        by_slice[r["category"]].append(r)
    slices={}
    for category,items in sorted(by_slice.items()):
        def avg(key):
            vals=[x[key] for x in items if x.get(key) is not None]
            return round(statistics.mean(vals),4) if vals else None
        slices[category]={
            "n":len(items),"semantic":avg("semantic_score"),"citation":avg("citation_score"),
            "forbidden_claim_avoidance":avg("forbidden_claim_avoidance"),"aggregate":avg("aggregate_score")
        }
    def all_avg(key):
        vals=[x[key] for x in rows if x.get(key) is not None]
        return round(statistics.mean(vals),4) if vals else None
    return {
        "n":len(rows),"overall":{
            "semantic":all_avg("semantic_score"),"citation":all_avg("citation_score"),
            "forbidden_claim_avoidance":all_avg("forbidden_claim_avoidance"),"aggregate":all_avg("aggregate_score")
        },"slices":slices
    }


def promotion_decision(base: dict, cand: dict, min_gain_pp: float) -> dict:
    b=base["overall"].get("aggregate"); c=cand["overall"].get("aggregate")
    if b is None or c is None:
        return {"eligible":False,"reason":"reviewed semantic scores required for promotion comparison"}
    gain_pp=(c-b)*100.0
    regressions=[]
    for sl in sorted(CRITICAL_SLICES):
        bs=base.get("slices",{}).get(sl,{}).get("aggregate")
        cs=cand.get("slices",{}).get(sl,{}).get("aggregate")
        if bs is not None and cs is not None and cs < bs:
            regressions.append({"slice":sl,"base":bs,"candidate":cs,"delta_pp":round((cs-bs)*100,2)})
    return {"eligible": gain_pp >= min_gain_pp and not regressions,
            "aggregate_gain_pp":round(gain_pp,2),"minimum_gain_pp":min_gain_pp,
            "critical_regressions":regressions}


def self_test() -> int:
    case={"id":"x","category":"hallucination","difficulty":"hard","expected_points":["a","b"],"must_cite":["doi:10.test/x"],"forbidden_claims":["universal threshold"]}
    good={"id":"x","response":"Supported. doi:10.test/x","point_scores":[1,1],"reviewed_by":"fixture"}
    bad={"id":"x","response":"This is a universal threshold. doi:wrong","point_scores":[1,0],"reviewed_by":"fixture"}
    gs=score_row(case,good,True); bs=score_row(case,bad,True)
    assert gs["aggregate_score"] == 1.0 and gs["citation_score"] == 1.0 and gs["forbidden_claim_avoidance"] == 1.0
    assert bs["citation_score"] == 0.0 and bs["forbidden_claim_avoidance"] == 0.0 and bs["semantic_score"] == 0.5
    assert promotion_decision(summarize([bs]),summarize([gs]),2.0)["eligible"] is True
    print("OK: score-model-eval self-test")
    return 0


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--eval",default="model_tuning/eval/heldout_v1.jsonl")
    ap.add_argument("--predictions")
    ap.add_argument("--baseline")
    ap.add_argument("--out")
    ap.add_argument("--require-reviewed",action="store_true")
    ap.add_argument("--minimum-gain-pp",type=float,default=2.0)
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.predictions:
        ap.error("--predictions is required unless --self-test is used")
    eval_rows=load_jsonl(pathlib.Path(args.eval))
    preds=load_jsonl(pathlib.Path(args.predictions))
    errors=validate_predictions(eval_rows,preds,args.require_reviewed)
    if errors:
        print("\n".join(errors),file=sys.stderr); return 2
    pmap={r["id"]:r for r in preds}
    scored=[score_row(c,pmap[c["id"]],args.require_reviewed) for c in eval_rows]
    report={"candidate":summarize(scored),"cases":scored,"promotion":None}
    if args.baseline:
        base_preds=load_jsonl(pathlib.Path(args.baseline))
        errors=validate_predictions(eval_rows,base_preds,True)
        if errors:
            print("baseline: "+"\nbaseline: ".join(errors),file=sys.stderr); return 2
        bmap={r["id"]:r for r in base_preds}
        base_scored=[score_row(c,bmap[c["id"]],True) for c in eval_rows]
        report["baseline"]=summarize(base_scored)
        report["promotion"]=promotion_decision(report["baseline"],report["candidate"],args.minimum_gain_pp)
    text=json.dumps(report,indent=2,sort_keys=True)
    if args.out:
        pathlib.Path(args.out).write_text(text+"\n",encoding="utf-8")
    print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
