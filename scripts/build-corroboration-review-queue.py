#!/usr/bin/env python3
"""Build a deterministic human-review queue for potentially corroborating RAG claims.

This script never merges claims or upgrades evidence automatically. It only surfaces similar
claims from distinct canonical sources inside the same reviewed diagnostic profile so a human
can decide whether they express the same scientific proposition.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
from difflib import SequenceMatcher
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_OUTPUT = ROOT / "model_tuning/generated/corroboration/review_queue_v1.jsonl"
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
BOILERPLATE_RE = re.compile(r"\b(copyright|license|licensed under|terms of use|diagnostic policy|privacy policy)\b", re.IGNORECASE)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())).strip()


def canonical_source(source: dict) -> str:
    doi = (source.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    raw = (source.get("url") or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    if host in {"doi.org", "www.doi.org", "dx.doi.org"}:
        payload = path.lstrip("/").lower()
        return f"doi:{payload}" if DOI_RE.fullmatch(payload) else ""
    if parsed.scheme.lower() in {"http", "https"} and host:
        return f"url:{parsed.scheme.lower()}://{host}{path.rstrip('/') or '/'}"
    return ""


def token_jaccard(a: str, b: str) -> float:
    aa, bb = set(norm(a).split()), set(norm(b).split())
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def source_meta(source: dict) -> dict:
    return {
        "title": source.get("title"),
        "doi": source.get("doi"),
        "url": source.get("url"),
        "year": source.get("year"),
        "publicationDate": source.get("publicationDate"),
    }


def candidate_pairs(profiles: list[dict], min_jaccard: float, min_sequence: float) -> list[dict]:
    out = []
    for profile in profiles:
        if profile.get("reviewStatus") != "reviewed":
            continue
        claims = []
        for source in profile.get("sources") or []:
            sid = canonical_source(source)
            if not sid:
                continue
            seen = set()
            for claim in source.get("supportedClaims") or []:
                key = norm(claim)
                if not key or key in seen or BOILERPLATE_RE.search(claim or ""):
                    continue
                seen.add(key)
                claims.append((sid, claim.strip(), source_meta(source)))
        for i, (sid_a, claim_a, meta_a) in enumerate(claims):
            for sid_b, claim_b, meta_b in claims[i + 1 :]:
                if sid_a == sid_b or norm(claim_a) == norm(claim_b):
                    continue
                jac = token_jaccard(claim_a, claim_b)
                seq = SequenceMatcher(None, norm(claim_a), norm(claim_b)).ratio()
                if jac < min_jaccard or seq < min_sequence:
                    continue
                left, right = sorted([(sid_a, claim_a, meta_a), (sid_b, claim_b, meta_b)], key=lambda x: (x[0], norm(x[1])))
                out.append({
                    "profile_id": profile.get("id"),
                    "profile_name": profile.get("name"),
                    "category": profile.get("category"),
                    "review_status": "pending_proposition_equivalence_review",
                    "claim_a": left[1],
                    "claim_b": right[1],
                    "source_a": {"canonical_source_id": left[0], **left[2]},
                    "source_b": {"canonical_source_id": right[0], **right[2]},
                    "similarity": {"token_jaccard": round(jac, 6), "sequence_ratio": round(seq, 6)},
                    "auto_merge": False,
                })
    unique = {}
    for row in out:
        key = (row["profile_id"], row["source_a"]["canonical_source_id"], row["source_b"]["canonical_source_id"], norm(row["claim_a"]), norm(row["claim_b"]))
        unique[key] = row
    return [unique[k] for k in sorted(unique)]


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def self_test() -> None:
    profile = {
        "id": "p1", "name": "Leaf spot", "category": "pathogen", "reviewStatus": "reviewed",
        "sources": [
            {"title": "A", "doi": "10.1234/a", "supportedClaims": ["Older lower leaves first develop yellow-green lesions that later become necrotic.", "Older lower leaves first develop yellow-green lesions that later become necrotic."]},
            {"title": "B", "url": "https://doi.org/10.5678/b", "supportedClaims": ["Yellow-green lesions often begin on older lower leaves and later progress to necrosis."]},
            {"title": "C", "doi": "10.9999/c", "supportedClaims": ["This unrelated sentence describes a different mechanism entirely."]},
        ],
    }
    rows = candidate_pairs([profile], 0.40, 0.50)
    assert len(rows) == 1
    row = rows[0]
    assert row["source_a"]["canonical_source_id"] == "doi:10.1234/a"
    assert row["source_b"]["canonical_source_id"] == "doi:10.5678/b"
    assert row["auto_merge"] is False
    assert row["review_status"] == "pending_proposition_equivalence_review"
    print("Corroboration review queue self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-jaccard", type=float, default=0.45)
    parser.add_argument("--min-sequence", type=float, default=0.55)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    rows = candidate_pairs(load_jsonl(args.input), args.min_jaccard, args.min_sequence)
    if not args.check_only:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"corroboration_review_candidates": len(rows), "auto_merged": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
