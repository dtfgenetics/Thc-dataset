#!/usr/bin/env python3
"""Score Grow Doc held-out model outputs with explicit semantic review gates.

This scorer intentionally separates deterministic checks (citation presence and forbidden-claim
avoidance) from semantic correctness. Promotion-grade runs MUST provide reviewed point_scores for
all expected_points; lexical similarity is not used as a substitute for factual review.

Baseline-vs-candidate promotion comparisons additionally require run manifests proving that the
benchmark, tokenizer, decoding, retrieval snapshot, base model, dtype, scorer and core runtime are
comparable. Reviewed prediction rows must reproduce the immutable raw response text byte-for-byte,
and the raw response files must match the SHA-256 values recorded in their manifests.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, statistics, sys
from collections import defaultdict

CRITICAL_SLICES = {
    "factuality",
    "diagnostic",
    "hallucination",
    "citation_accuracy",
    "science",
    "education",
    "grounded_qa",
    "regression",
}
RUNTIME_COMPARABILITY_KEYS = ("python", "transformers", "torch", "accelerate", "peft", "bitsandbytes")


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


def load_json(path: pathlib.Path) -> dict:
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value,dict):
        raise ValueError(f"{path}: manifest must be a JSON object")
    return value


def sha256_file(path: pathlib.Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def comparable_run_errors(base: dict, cand: dict) -> list[str]:
    """Return hard comparability failures for checkpoint/adapter promotion."""
    errors=[]
    if base.get("schema_version") != cand.get("schema_version"):
        errors.append("run manifest schema_version differs")

    be=base.get("evaluation") or {}; ce=cand.get("evaluation") or {}
    for key in ("benchmark_path", "benchmark_sha256", "scorer_revision"):
        if be.get(key) != ce.get(key):
            errors.append(f"evaluation.{key} differs")

    if base.get("tokenizer") != cand.get("tokenizer"):
        errors.append("tokenizer repository/revision differs")
    if base.get("decoding") != cand.get("decoding"):
        errors.append("decoding configuration differs")
    if base.get("retrieval") != cand.get("retrieval"):
        errors.append("retrieval snapshot/configuration differs")

    bm=base.get("model") or {}; cm=cand.get("model") or {}
    for key in ("repository", "revision", "dtype"):
        if bm.get(key) != cm.get(key):
            errors.append(f"model.{key} differs; adapter promotion requires the exact same base model")

    br=base.get("runtime") or {}; cr=cand.get("runtime") or {}
    for key in RUNTIME_COMPARABILITY_KEYS:
        if br.get(key) != cr.get(key):
            errors.append(f"runtime.{key} differs")
    return errors


def manifest_binding_errors(
    eval_path: pathlib.Path,
    raw_response_path: pathlib.Path,
    manifest: dict,
    label: str,
) -> list[str]:
    errors=[]
    evaluation=manifest.get("evaluation") or {}
    artifacts=manifest.get("artifacts") or {}
    actual_eval_sha=sha256_file(eval_path)
    actual_raw_sha=sha256_file(raw_response_path)
    if evaluation.get("benchmark_sha256") != actual_eval_sha:
        errors.append(f"{label} manifest benchmark_sha256 does not match --eval file")
    if artifacts.get("responses_sha256") != actual_raw_sha:
        errors.append(f"{label} manifest responses_sha256 does not match raw response file")
    return errors


def reviewed_raw_binding_errors(reviewed: list[dict], raw: list[dict], label: str) -> list[str]:
    """Ensure human review annotations did not alter generated model response text."""
    errors=[]
    raw_by_id={}
    for idx,row in enumerate(raw,1):
        rid=row.get("id")
        if not rid:
            errors.append(f"{label} raw response {idx}: missing id")
            continue
        if rid in raw_by_id:
            errors.append(f"{label} raw responses: duplicate id {rid!r}")
        raw_by_id[rid]=row
    reviewed_ids=set()
    for idx,row in enumerate(reviewed,1):
        rid=row.get("id")
        if not rid:
            continue
        reviewed_ids.add(rid)
        source=raw_by_id.get(rid)
        if source is None:
            errors.append(f"{label} reviewed prediction {idx}: id {rid!r} absent from raw responses")
        elif row.get("response") != source.get("response"):
            errors.append(f"{label} reviewed prediction {rid}: response text differs from immutable raw response")
    extra=sorted(set(raw_by_id)-reviewed_ids)
    if extra:
        errors.append(f"{label} raw responses contain ids absent from reviewed predictions: {', '.join(extra)}")
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


def fixture_manifest(adapter_revision: str | None = None) -> dict:
    return {
        "schema_version":"grow-doc-eval-run-v1",
        "model":{"repository":"Qwen/Qwen3-8B","revision":"1234567","dtype":"bfloat16",
                 "adapter":None if adapter_revision is None else {"repository":"dtf/test","revision":adapter_revision}},
        "tokenizer":{"repository":"Qwen/Qwen3-8B","revision":"1234567"},
        "decoding":{"temperature":0.0,"top_p":1.0,"max_new_tokens":512,"do_sample":False,"seed":42},
        "retrieval":{"snapshot_sha256":"a"*64,"top_k":5,"reranker":None},
        "evaluation":{"benchmark_path":"model_tuning/eval/heldout_v2.jsonl","benchmark_sha256":"b"*64,"scorer_revision":"1234567"},
        "runtime":{"python":"3.11","transformers":"4.x","torch":"2.x","accelerate":"1.x","peft":"0.x","bitsandbytes":"0.x"},
        "artifacts":{"responses_path":"responses.jsonl","responses_sha256":"c"*64,"scores_path":"scores.json"},
    }


def self_test() -> int:
    case={"id":"x","category":"hallucination","difficulty":"hard","expected_points":["a","b"],"must_cite":["doi:10.test/x"],"forbidden_claims":["universal threshold"]}
    good={"id":"x","response":"Supported. doi:10.test/x","point_scores":[1,1],"reviewed_by":"fixture"}
    bad={"id":"x","response":"This is a universal threshold. doi:wrong","point_scores":[1,0],"reviewed_by":"fixture"}
    gs=score_row(case,good,True); bs=score_row(case,bad,True)
    assert gs["aggregate_score"] == 1.0 and gs["citation_score"] == 1.0 and gs["forbidden_claim_avoidance"] == 1.0
    assert bs["citation_score"] == 0.0 and bs["forbidden_claim_avoidance"] == 0.0 and bs["semantic_score"] == 0.5
    assert promotion_decision(summarize([bs]),summarize([gs]),2.0)["eligible"] is True

    # A candidate can improve overall while regressing a non-legacy slice; every
    # held-out promotion slice must block that regression, not only the original
    # diagnostic/hallucination/citation subset.
    base_summary={
        "overall":{"aggregate":0.80},
        "slices":{sl:{"aggregate":0.80} for sl in CRITICAL_SLICES},
    }
    cand_summary={
        "overall":{"aggregate":0.84},
        "slices":{sl:{"aggregate":0.84} for sl in CRITICAL_SLICES},
    }
    cand_summary["slices"]["science"]={"aggregate":0.79}
    decision=promotion_decision(base_summary,cand_summary,2.0)
    assert decision["eligible"] is False
    assert any(x["slice"] == "science" for x in decision["critical_regressions"])

    base=fixture_manifest(); cand=fixture_manifest("abcdef1")
    assert comparable_run_errors(base,cand) == []
    changed=json.loads(json.dumps(cand)); changed["retrieval"]["snapshot_sha256"]="d"*64
    assert "retrieval snapshot/configuration differs" in comparable_run_errors(base,changed)
    changed=json.loads(json.dumps(cand)); changed["model"]["revision"]="7654321"
    assert any("exact same base model" in x for x in comparable_run_errors(base,changed))
    changed=json.loads(json.dumps(cand)); changed["decoding"]["temperature"]=0.2
    assert "decoding configuration differs" in comparable_run_errors(base,changed)

    raw=[{"id":"x","response":"unchanged model text"}]
    reviewed=[{"id":"x","response":"unchanged model text","point_scores":[1],"reviewed_by":"fixture"}]
    assert reviewed_raw_binding_errors(reviewed,raw,"candidate") == []
    reviewed[0]["response"]="edited model text"
    assert any("differs from immutable raw response" in x for x in reviewed_raw_binding_errors(reviewed,raw,"candidate"))
    print("OK: score-model-eval self-test")
    return 0


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--eval",default="model_tuning/eval/heldout_v2.jsonl")
    ap.add_argument("--predictions",help="reviewed candidate predictions used for scoring")
    ap.add_argument("--baseline",help="reviewed baseline predictions used for scoring")
    ap.add_argument("--candidate-manifest")
    ap.add_argument("--baseline-manifest")
    ap.add_argument("--candidate-raw-responses")
    ap.add_argument("--baseline-raw-responses")
    ap.add_argument("--out")
    ap.add_argument("--require-reviewed",action="store_true")
    ap.add_argument("--minimum-gain-pp",type=float,default=2.0)
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.predictions:
        ap.error("--predictions is required unless --self-test is used")

    eval_path=pathlib.Path(args.eval)
    pred_path=pathlib.Path(args.predictions)
    eval_rows=load_jsonl(eval_path)
    preds=load_jsonl(pred_path)
    errors=validate_predictions(eval_rows,preds,args.require_reviewed)
    if errors:
        print("\n".join(errors),file=sys.stderr); return 2
    pmap={r["id"]:r for r in preds}
    scored=[score_row(c,pmap[c["id"]],args.require_reviewed) for c in eval_rows]
    report={"candidate":summarize(scored),"cases":scored,"promotion":None}

    if args.baseline:
        if not args.require_reviewed:
            print("promotion comparison requires --require-reviewed",file=sys.stderr); return 2
        required_args=(args.candidate_manifest,args.baseline_manifest,args.candidate_raw_responses,args.baseline_raw_responses)
        if not all(required_args):
            print("promotion comparison requires candidate/baseline manifests and candidate/baseline raw response files",file=sys.stderr); return 2

        base_path=pathlib.Path(args.baseline)
        base_preds=load_jsonl(base_path)
        errors=validate_predictions(eval_rows,base_preds,True)
        if errors:
            print("baseline: "+"\nbaseline: ".join(errors),file=sys.stderr); return 2

        cand_raw_path=pathlib.Path(args.candidate_raw_responses)
        base_raw_path=pathlib.Path(args.baseline_raw_responses)
        cand_raw=load_jsonl(cand_raw_path)
        base_raw=load_jsonl(base_raw_path)
        raw_errors=validate_predictions(eval_rows,cand_raw,False)
        raw_errors.extend(validate_predictions(eval_rows,base_raw,False))
        raw_errors.extend(reviewed_raw_binding_errors(preds,cand_raw,"candidate"))
        raw_errors.extend(reviewed_raw_binding_errors(base_preds,base_raw,"baseline"))
        if raw_errors:
            print("raw/review binding failure:\n- "+"\n- ".join(raw_errors),file=sys.stderr); return 2

        try:
            cand_manifest=load_json(pathlib.Path(args.candidate_manifest))
            base_manifest=load_json(pathlib.Path(args.baseline_manifest))
        except ValueError as exc:
            print(str(exc),file=sys.stderr); return 2
        errors=comparable_run_errors(base_manifest,cand_manifest)
        errors.extend(manifest_binding_errors(eval_path,cand_raw_path,cand_manifest,"candidate"))
        errors.extend(manifest_binding_errors(eval_path,base_raw_path,base_manifest,"baseline"))
        if errors:
            print("non-comparable promotion runs:\n- "+"\n- ".join(errors),file=sys.stderr); return 2

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
