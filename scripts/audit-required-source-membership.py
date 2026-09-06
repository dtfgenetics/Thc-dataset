#!/usr/bin/env python3
"""Audit whether held-out required sources survive corpus generation and where they rank.

This diagnostic is evaluation-only. Held-out `must_cite` labels are used after corpus
construction to classify retrieval failures; they never affect corpus generation or ranking.
"""
from __future__ import annotations

import importlib.util
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAG_IMPL = ROOT / "scripts/build-rag-eval-snapshot.py"
CLAIMS = ROOT / "model_tuning/generated/rag/claims_v1.jsonl"
BENCH = ROOT / "model_tuning/eval/heldout_v2.jsonl"

spec = importlib.util.spec_from_file_location("rag_eval", RAG_IMPL)
if spec is None or spec.loader is None:
    raise SystemExit("could not load build-rag-eval-snapshot.py")
rag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rag)


def canonical_source_id(value: Any) -> str:
    sid = str(value or "").strip()
    if sid.lower().startswith("doi:"):
        return "doi:" + sid[4:].strip().lower()
    return sid


def main() -> int:
    claims = rag.load_jsonl(CLAIMS)
    cases = rag.load_jsonl(BENCH)
    rag.validate_claims(claims)
    rag.validate_cases(cases)

    source_claims: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        for raw_sid in claim.get("source_ids") or []:
            sid = canonical_source_id(raw_sid)
            if sid:
                source_claims[sid].append(claim)

    df = rag.document_frequencies(claims)
    rows: list[dict[str, Any]] = []
    status_counts: dict[str, int] = defaultdict(int)

    for case in cases:
        required = sorted({canonical_source_id(x) for x in (case.get("must_cite") or []) if canonical_source_id(x)})
        if not required:
            continue

        query = rag.tokens(case["prompt"])
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for claim in claims:
            score = rag.weighted_score(query, claim, df, len(claims))
            scored.append((score, claim["id"], claim))
        scored.sort(key=lambda item: (-item[0], item[1]))

        for sid in required:
            matching = source_claims.get(sid, [])
            positive_ranks: list[int] = []
            best_score = None
            best_claim_id = None
            best_claim = None
            for rank, (score, _claim_id, claim) in enumerate(scored, 1):
                claim_sources = {canonical_source_id(x) for x in (claim.get("source_ids") or [])}
                if sid not in claim_sources:
                    continue
                if best_score is None:
                    best_score = score
                    best_claim_id = claim["id"]
                    best_claim = claim.get("claim")
                if score > 0:
                    positive_ranks.append(rank)

            if not matching:
                status = "missing_from_generated_corpus"
            elif positive_ranks:
                status = "present_and_ranked"
            else:
                status = "present_but_zero_prompt_overlap"
            status_counts[status] += 1

            rows.append(
                {
                    "case_id": case["id"],
                    "required_source_id": sid,
                    "status": status,
                    "generated_claim_count": len(matching),
                    "first_positive_rank": positive_ranks[0] if positive_ranks else None,
                    "best_score": round(float(best_score), 8) if best_score is not None else None,
                    "best_claim_id": best_claim_id,
                    "best_claim": best_claim,
                }
            )

    print("required_source_membership_summary")
    print(json.dumps(dict(sorted(status_counts.items())), sort_keys=True))
    print("required_source_membership_by_case")
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))

    # The diagnostic itself should fail closed if a benchmark-required source vanished
    # from the generated RAG corpus; rank quality is measured, not hard-coded here.
    missing = [row for row in rows if row["status"] == "missing_from_generated_corpus"]
    if missing:
        ids = ", ".join(f"{row['case_id']}:{row['required_source_id']}" for row in missing)
        raise SystemExit(f"required held-out sources missing from generated RAG corpus: {ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
