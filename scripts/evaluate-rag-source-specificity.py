#!/usr/bin/env python3
"""Evaluate source-title specificity as a leak-safe RAG reranking signal.

This is an experiment only. It does not mutate the frozen RAG snapshot or training artifacts.
The held-out must_cite labels are used only after retrieval to score required-source coverage.
"""
from __future__ import annotations

import importlib.util
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts/build-rag-eval-snapshot.py"
CLAIMS = ROOT / "model_tuning/generated/rag/claims_v1.jsonl"
BENCH = ROOT / "model_tuning/eval/heldout_v2.jsonl"

spec = importlib.util.spec_from_file_location("rag_eval", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("could not load build-rag-eval-snapshot.py")
rag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rag)


def title_overlap_score(query: list[str], row: dict, df: Counter[str], n_docs: int) -> float:
    titles = rag.row_fields(row).get("source_title", "")
    tf = Counter(rag.tokens(titles))
    matched = 0.0
    distinct = 0
    for term in set(query):
        if term not in tf:
            continue
        distinct += 1
        idf = math.log((n_docs + 1.0) / (df[term] + 1.0)) + 1.0
        matched += idf * (1.0 + math.log(tf[term]))
    # Require at least two distinct query/title matches before adding a specificity bonus.
    # This prevents generic one-word source titles from dominating retrieval.
    return matched if distinct >= 2 else 0.0


def retrieve_variant(claims: list[dict], prompt: str, top_k: int, bonus_weight: float) -> list[dict]:
    df = rag.document_frequencies(claims)
    query = rag.tokens(prompt)
    ranked = []
    for row in claims:
        score = rag.weighted_score(query, row, df, len(claims))
        score += bonus_weight * title_overlap_score(query, row, df, len(claims))
        ranked.append((score, row["id"], row))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked if item[0] > 0][:top_k]


def coverage(cases: list[dict], selections: dict[str, list[dict]]) -> tuple[int, int, list[str]]:
    eligible = 0
    hits = 0
    missing = []
    for case in cases:
        required = {str(x).strip() for x in case.get("must_cite") or [] if str(x).strip()}
        if not required:
            continue
        eligible += 1
        found = {
            str(source_id).strip()
            for row in selections.get(case["id"], [])
            for source_id in row.get("source_ids") or []
            if str(source_id).strip()
        }
        if required.issubset(found):
            hits += 1
        else:
            missing.append(case["id"])
    return hits, eligible, missing


def main() -> int:
    claims = rag.load_jsonl(CLAIMS)
    cases = rag.load_jsonl(BENCH)
    rag.validate_claims(claims)
    rag.validate_cases(cases)

    current_snapshot = rag.build(claims, cases, 5, metadata_aware=True)
    current = rag.required_source_coverage(cases, current_snapshot)
    print("current", json.dumps(current, sort_keys=True))

    best = (current["hit_cases"], 0.0, current["missing_case_ids"])
    for weight in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0):
        selections = {case["id"]: retrieve_variant(claims, case["prompt"], 5, weight) for case in cases}
        hits, eligible, missing = coverage(cases, selections)
        print(f"source_title_bonus={weight:.2f} coverage={hits}/{eligible} missing={','.join(missing)}")
        if hits > best[0]:
            best = (hits, weight, missing)

    print(f"best coverage={best[0]}/{current['eligible_cases']} weight={best[1]:.2f} missing={','.join(best[2])}")
    if best[0] < current["hit_cases"]:
        raise SystemExit("source-specificity experiment regressed current retrieval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
