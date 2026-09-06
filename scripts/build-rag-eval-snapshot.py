#!/usr/bin/env python3
"""Build a deterministic, provenance-preserving retrieval snapshot for held-out evaluation.

This script does not run a language model and does not claim model performance. It freezes
which reviewed RAG claims are supplied to each held-out prompt so base models and adapters
can be compared against identical retrieval context.

Retrieval uses only prompt text plus corpus-side claim/profile/source metadata. Held-out
answers, expected points, must-cite labels, and forbidden claims are never retrieval inputs.
The held-out must-cite field is used only after retrieval to audit required-source coverage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ALGORITHM = "grow-doc-field-weighted-idf-v3"
BASELINE_ALGORITHM = "grow-doc-lexical-idf-v1"
TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "is",
    "it", "of", "on", "or", "that", "the", "this", "to", "what", "when", "which", "with",
}
FIELD_WEIGHTS = {
    "claim": 1.0,
    "profile_name": 1.35,
    "profile_alias": 1.0,
    "category": 0.7,
    "source_title": 0.55,
    "source_organization": 0.35,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{lineno}: expected object")
        rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def tokens(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall((text or "").lower()) if t not in STOPWORDS and len(t) > 1]


def validate_claims(rows: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for n, row in enumerate(rows, 1):
        required = {"id", "claim", "claim_sha256", "source_ids", "profile_ids", "retrieval_only"}
        missing = required - row.keys()
        if missing:
            raise ValueError(f"claim row {n}: missing {sorted(missing)}")
        if row["id"] in seen:
            raise ValueError(f"claim row {n}: duplicate id {row['id']}")
        seen.add(row["id"])
        if not row["retrieval_only"]:
            raise ValueError(f"claim row {n}: non-retrieval record cannot enter frozen RAG snapshot")
        if not row["source_ids"] or not row["profile_ids"]:
            raise ValueError(f"claim row {n}: provenance is required")


def validate_cases(rows: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for n, row in enumerate(rows, 1):
        if not row.get("id") or not row.get("prompt"):
            raise ValueError(f"benchmark row {n}: id and prompt are required")
        if row["id"] in seen:
            raise ValueError(f"benchmark row {n}: duplicate id {row['id']}")
        seen.add(row["id"])


def row_fields(row: dict[str, Any]) -> dict[str, str]:
    sources = row.get("sources") or []
    source_titles = " ".join(str(source.get("title") or "") for source in sources if isinstance(source, dict))
    source_orgs = " ".join(
        " ".join(str(source.get(key) or "") for key in ("organization", "publisher"))
        for source in sources
        if isinstance(source, dict)
    )
    if not source_titles and isinstance(row.get("source"), dict):
        source_titles = str(row["source"].get("title") or "")
    if not source_orgs and isinstance(row.get("source"), dict):
        source_orgs = " ".join(str(row["source"].get(key) or "") for key in ("organization", "publisher"))
    profile_aliases = " ".join(
        str(profile_id or "").replace("-", " ").replace("_", " ")
        for profile_id in (row.get("profile_ids") or [])
    )
    return {
        "claim": str(row.get("claim") or ""),
        "profile_name": str(row.get("profile_name") or ""),
        "profile_alias": profile_aliases,
        "category": str(row.get("category") or ""),
        "source_title": source_titles,
        "source_organization": source_orgs,
    }


def document_frequencies(claims: list[dict[str, Any]]) -> Counter[str]:
    df: Counter[str] = Counter()
    for row in claims:
        combined: set[str] = set()
        for value in row_fields(row).values():
            combined.update(tokens(value))
        df.update(combined)
    return df


def lexical_score(query: list[str], claim: str, df: Counter[str], n_docs: int) -> float:
    if not query:
        return 0.0
    tf = Counter(tokens(claim))
    total = 0.0
    for term in set(query):
        if term not in tf:
            continue
        idf = math.log((n_docs + 1.0) / (df[term] + 1.0)) + 1.0
        total += idf * (1.0 + math.log(tf[term]))
    return total


def weighted_score(query: list[str], row: dict[str, Any], df: Counter[str], n_docs: int) -> float:
    if not query:
        return 0.0
    fields = row_fields(row)
    total = 0.0
    for field_name, value in fields.items():
        weight = FIELD_WEIGHTS[field_name]
        if not value or weight <= 0:
            continue
        tf = Counter(tokens(value))
        for term in set(query):
            if term not in tf:
                continue
            idf = math.log((n_docs + 1.0) / (df[term] + 1.0)) + 1.0
            total += weight * idf * (1.0 + math.log(tf[term]))
    return total


def retrieve(
    claims: list[dict[str, Any]],
    prompt: str,
    top_k: int,
    *,
    metadata_aware: bool = True,
) -> list[dict[str, Any]]:
    df = document_frequencies(claims)
    query = tokens(prompt)
    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for row in claims:
        s = weighted_score(query, row, df, len(claims)) if metadata_aware else lexical_score(query, row["claim"], df, len(claims))
        ranked.append((s, row["id"], row))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    selected = [item for item in ranked if item[0] > 0][:top_k]
    return [
        {
            "rank": rank,
            "score": round(s, 8),
            "claim_id": row["id"],
            "claim_sha256": row["claim_sha256"],
            "claim": row["claim"],
            "source_ids": list(row["source_ids"]),
            "profile_ids": list(row["profile_ids"]),
            "profile_name": row.get("profile_name"),
            "category": row.get("category"),
            "sources": list(row.get("sources") or ([row["source"]] if row.get("source") else [])),
        }
        for rank, (s, _rid, row) in enumerate(selected, 1)
    ]


def build(
    claims: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    top_k: int,
    *,
    metadata_aware: bool = True,
) -> list[dict[str, Any]]:
    validate_claims(claims)
    validate_cases(cases)
    return [
        {
            "case_id": case["id"],
            "prompt_sha256": hashlib.sha256(case["prompt"].encode("utf-8")).hexdigest(),
            "retrieved": retrieve(claims, case["prompt"], top_k, metadata_aware=metadata_aware),
        }
        for case in cases
    ]


def required_source_coverage(cases: list[dict[str, Any]], snapshot: list[dict[str, Any]]) -> dict[str, Any]:
    by_case = {row["case_id"]: row for row in snapshot}
    eligible = 0
    hit = 0
    missing: list[str] = []
    for case in cases:
        required = {str(value).strip() for value in (case.get("must_cite") or []) if str(value).strip()}
        if not required:
            continue
        eligible += 1
        retrieved_sources = {
            str(source_id).strip()
            for item in by_case.get(case["id"], {}).get("retrieved", [])
            for source_id in (item.get("source_ids") or [])
            if str(source_id).strip()
        }
        if required.issubset(retrieved_sources):
            hit += 1
        else:
            missing.append(case["id"])
    return {
        "eligible_cases": eligible,
        "hit_cases": hit,
        "hit_rate": round(hit / eligible, 6) if eligible else None,
        "missing_case_ids": missing,
    }


def self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        claims_path = root / "claims.jsonl"
        bench_path = root / "heldout.jsonl"
        claims = [
            {
                "id": "rag-a",
                "claim": "Root-zone oxygen limitation can impair root function and mimic nutrient stress.",
                "claim_sha256": "a" * 64,
                "source_ids": ["doi:10.0000/root"],
                "profile_ids": ["root-hypoxia", "root-stress"],
                "profile_name": "Root hypoxia",
                "category": "abiotic",
                "sources": [{"source_id": "doi:10.0000/root", "title": "Root Oxygen Limitation", "organization": "Plant Lab"}],
                "retrieval_only": True,
            },
            {
                "id": "rag-b",
                "claim": "Superficial growth can occur on susceptible foliage.",
                "claim_sha256": "b" * 64,
                "source_ids": ["doi:10.0000/pm"],
                "profile_ids": ["powdery-mildew"],
                "profile_name": "Foliar disease",
                "category": "fungal disease",
                "sources": [{"source_id": "doi:10.0000/pm", "title": "Cannabis Disease Study", "organization": "Plant Pathology Lab"}],
                "retrieval_only": True,
            },
        ]
        cases = [
            {
                "id": "case-root",
                "prompt": "How can root oxygen limitation resemble nutrient stress?",
                "must_cite": ["doi:10.0000/root"],
            },
            {
                "id": "case-pm",
                "prompt": "What should a grower know about powdery mildew?",
                "must_cite": ["doi:10.0000/pm"],
            },
        ]
        write_jsonl(claims_path, claims)
        write_jsonl(bench_path, cases)
        first = build(load_jsonl(claims_path), load_jsonl(bench_path), 1)
        second = build(load_jsonl(claims_path), load_jsonl(bench_path), 1)
        assert first == second
        assert first[0]["retrieved"][0]["claim_id"] == "rag-a"
        assert first[0]["retrieved"][0]["source_ids"] == ["doi:10.0000/root"]
        assert first[0]["retrieved"][0]["profile_ids"] == ["root-hypoxia", "root-stress"]
        assert first[0]["retrieved"][0]["sources"][0]["title"] == "Root Oxygen Limitation"
        assert first[1]["retrieved"][0]["claim_id"] == "rag-b", "profile-id aliases should support prompt matching after claim deduplication"
        coverage = required_source_coverage(cases, first)
        assert coverage["eligible_cases"] == 2
        assert coverage["hit_cases"] == 2
        assert coverage["missing_case_ids"] == []
        assert all(item["score"] > 0 for row in first for item in row["retrieved"])
    print("frozen RAG snapshot self-test: PASS")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--claims", type=Path, default=Path("model_tuning/generated/rag/claims_v1.jsonl"))
    ap.add_argument("--benchmark", type=Path, default=Path("model_tuning/eval/heldout_v2.jsonl"))
    ap.add_argument("--output", type=Path, default=Path("model_tuning/rag_snapshots/heldout_v2.jsonl"))
    ap.add_argument("--manifest", type=Path, default=Path("model_tuning/rag_snapshots/heldout_v2.manifest.json"))
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.top_k < 1 or args.top_k > 20:
        raise SystemExit("top-k must be between 1 and 20")
    claims = load_jsonl(args.claims)
    cases = load_jsonl(args.benchmark)
    rows = build(claims, cases, args.top_k, metadata_aware=True)
    baseline_rows = build(claims, cases, args.top_k, metadata_aware=False)
    coverage = required_source_coverage(cases, rows)
    baseline_coverage = required_source_coverage(cases, baseline_rows)
    if coverage["hit_cases"] < baseline_coverage["hit_cases"]:
        raise SystemExit(
            "metadata-aware retrieval regressed required-source coverage: "
            f"{coverage['hit_cases']}/{coverage['eligible_cases']} vs lexical baseline "
            f"{baseline_coverage['hit_cases']}/{baseline_coverage['eligible_cases']}"
        )
    write_jsonl(args.output, rows)
    manifest = {
        "schema_version": "grow-doc-rag-snapshot-v2",
        "algorithm": ALGORITHM,
        "baseline_algorithm": BASELINE_ALGORITHM,
        "field_weights": FIELD_WEIGHTS,
        "retrieval_inputs": ["prompt", "claim", "profile_name", "profile_alias", "category", "source_title", "source_organization"],
        "heldout_labels_used_for_retrieval": False,
        "top_k": args.top_k,
        "claims_path": str(args.claims),
        "claims_sha256": sha256(args.claims),
        "benchmark_path": str(args.benchmark),
        "benchmark_sha256": sha256(args.benchmark),
        "snapshot_path": str(args.output),
        "snapshot_sha256": sha256(args.output),
        "cases": len(rows),
        "retrieved_claims": sum(len(row["retrieved"]) for row in rows),
        "zero_hit_cases": sum(1 for row in rows if not row["retrieved"]),
        "required_source_coverage": coverage,
        "lexical_baseline_required_source_coverage": baseline_coverage,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    print("Retrieval snapshot only; no model performance claim is made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())