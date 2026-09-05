#!/usr/bin/env python3
"""Build a deterministic, provenance-preserving retrieval snapshot for held-out evaluation.

This script does not run a language model and does not claim model performance. It freezes
which reviewed RAG claims are supplied to each held-out prompt so base models and adapters
can be compared against identical retrieval context.

Ranking uses only retrieval-corpus fields that already exist before evaluation: claim text,
profile name/category, and reviewed source titles. It never reads held-out expected_points,
must_cite, forbidden_claims, or source_metadata when choosing claims.
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

ALGORITHM = "grow-doc-lexical-idf-metadata-v2"
TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "is",
    "it", "of", "on", "or", "that", "the", "this", "to", "what", "when", "which", "with",
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


def retrieval_document(row: dict[str, Any]) -> str:
    """Return corpus-side searchable text without touching held-out answer fields."""
    source_titles: list[str] = []
    sources = row.get("sources")
    if isinstance(sources, list):
        for source in sources:
            if isinstance(source, dict) and isinstance(source.get("title"), str):
                source_titles.append(source["title"])
    if not source_titles:
        source = row.get("source")
        if isinstance(source, dict) and isinstance(source.get("title"), str):
            source_titles.append(source["title"])
    fields = [
        str(row.get("claim") or ""),
        str(row.get("profile_name") or ""),
        str(row.get("category") or ""),
        " ".join(source_titles),
    ]
    return " ".join(field for field in fields if field)


def document_frequencies(claims: list[dict[str, Any]]) -> Counter[str]:
    df: Counter[str] = Counter()
    for row in claims:
        df.update(set(tokens(retrieval_document(row))))
    return df


def score(query: list[str], document: str, df: Counter[str], n_docs: int) -> float:
    if not query:
        return 0.0
    tf = Counter(tokens(document))
    total = 0.0
    for term in set(query):
        if term not in tf:
            continue
        idf = math.log((n_docs + 1.0) / (df[term] + 1.0)) + 1.0
        total += idf * (1.0 + math.log(tf[term]))
    return total


def retrieve(claims: list[dict[str, Any]], prompt: str, top_k: int) -> list[dict[str, Any]]:
    df = document_frequencies(claims)
    query = tokens(prompt)
    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for row in claims:
        s = score(query, retrieval_document(row), df, len(claims))
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
        }
        for rank, (s, _rid, row) in enumerate(selected, 1)
    ]


def build(claims: list[dict[str, Any]], cases: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    validate_claims(claims)
    validate_cases(cases)
    return [
        {
            "case_id": case["id"],
            "prompt_sha256": hashlib.sha256(case["prompt"].encode("utf-8")).hexdigest(),
            "retrieved": retrieve(claims, case["prompt"], top_k),
        }
        for case in cases
    ]


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
                "category": "Root disorder",
                "source": {"title": "Root oxygen limitation in controlled crops"},
                "retrieval_only": True,
            },
            {
                "id": "rag-b",
                "claim": "Superficial fungal growth can develop on susceptible foliage.",
                "claim_sha256": "b" * 64,
                "source_ids": ["doi:10.0000/pm"],
                "profile_ids": ["powdery-mildew"],
                "profile_name": "Powdery mildew",
                "category": "Fungal pathogen",
                "source": {"title": "Powdery mildew of Cannabis"},
                "retrieval_only": True,
            },
            {
                "id": "rag-c",
                "claim": "The isolate reproduced lesions after inoculation and was reisolated from the host.",
                "claim_sha256": "c" * 64,
                "source_ids": ["doi:10.0000/serratia"],
                "profile_ids": ["bacterial-serratia-leaf-spot"],
                "profile_name": "Serratia bacterial leaf spot",
                "category": "Bacterial pathogen",
                "source": {"title": "First report of Serratia marcescens causing leaf spot on hemp"},
                "retrieval_only": True,
            },
        ]
        cases = [
            {"id": "case-root", "prompt": "How can root oxygen limitation resemble nutrient stress?"},
            {"id": "case-serratia", "prompt": "What evidence supports Serratia marcescens on hemp?"},
        ]
        write_jsonl(claims_path, claims)
        write_jsonl(bench_path, cases)
        first = build(load_jsonl(claims_path), load_jsonl(bench_path), 2)
        second = build(load_jsonl(claims_path), load_jsonl(bench_path), 2)
        assert first == second
        assert first[0]["retrieved"][0]["claim_id"] == "rag-a"
        assert first[0]["retrieved"][0]["source_ids"] == ["doi:10.0000/root"]
        assert first[0]["retrieved"][0]["profile_ids"] == ["root-hypoxia", "root-stress"]
        assert first[1]["retrieved"][0]["claim_id"] == "rag-c"
        assert "serratia" in tokens(retrieval_document(claims[2]))
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
    rows = build(claims, cases, args.top_k)
    write_jsonl(args.output, rows)
    manifest = {
        "schema_version": "grow-doc-rag-snapshot-v1",
        "algorithm": ALGORITHM,
        "index_fields": ["claim", "profile_name", "category", "source_title"],
        "query_fields": ["prompt"],
        "heldout_answer_fields_used_for_ranking": False,
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
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    print("Retrieval snapshot only; no model performance claim is made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
