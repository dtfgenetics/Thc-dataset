#!/usr/bin/env python3
"""Build deterministic human-review queues for potentially corroborating RAG claims.

The strict queue surfaces only claims that meet production similarity thresholds. The discovery
queue surfaces weaker same-profile, cross-source near matches for evidence-expansion review.
Neither queue merges claims, upgrades evidence, or makes examples training-eligible automatically.
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
DEFAULT_DISCOVERY_OUTPUT = ROOT / "model_tuning/generated/corroboration/discovery_queue_v1.jsonl"
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


def claim_rows(profile: dict) -> list[tuple[str, str, dict]]:
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
    return claims


def pair_row(profile: dict, left: tuple[str, str, dict], right: tuple[str, str, dict], jac: float, seq: float, *, discovery: bool) -> dict:
    left, right = sorted([left, right], key=lambda x: (x[0], norm(x[1])))
    row = {
        "profile_id": profile.get("id"),
        "profile_name": profile.get("name"),
        "category": profile.get("category"),
        "review_status": "discovery_only_not_evidence" if discovery else "pending_proposition_equivalence_review",
        "claim_a": left[1],
        "claim_b": right[1],
        "source_a": {"canonical_source_id": left[0], **left[2]},
        "source_b": {"canonical_source_id": right[0], **right[2]},
        "similarity": {
            "token_jaccard": round(jac, 6),
            "sequence_ratio": round(seq, 6),
            "mean_score": round((jac + seq) / 2.0, 6),
        },
        "auto_merge": False,
    }
    if discovery:
        row["eligible_for_corroboration"] = False
        row["eligible_for_training"] = False
        row["discovery_reason"] = "below_strict_corroboration_thresholds"
    return row


def candidate_pairs(profiles: list[dict], min_jaccard: float, min_sequence: float) -> list[dict]:
    out = []
    for profile in profiles:
        if profile.get("reviewStatus") != "reviewed":
            continue
        claims = claim_rows(profile)
        for i, left in enumerate(claims):
            for right in claims[i + 1 :]:
                sid_a, claim_a, _ = left
                sid_b, claim_b, _ = right
                if sid_a == sid_b:
                    continue
                jac = token_jaccard(claim_a, claim_b)
                seq = SequenceMatcher(None, norm(claim_a), norm(claim_b)).ratio()
                if jac < min_jaccard or seq < min_sequence:
                    continue
                out.append(pair_row(profile, left, right, jac, seq, discovery=False))
    unique = {}
    for row in out:
        key = (row["profile_id"], row["source_a"]["canonical_source_id"], row["source_b"]["canonical_source_id"], norm(row["claim_a"]), norm(row["claim_b"]))
        unique[key] = row
    return [unique[k] for k in sorted(unique)]


def discovery_pairs(
    profiles: list[dict],
    strict_jaccard: float,
    strict_sequence: float,
    discovery_jaccard: float,
    discovery_sequence: float,
    top_k: int,
) -> list[dict]:
    """Rank near matches below strict thresholds without upgrading their evidence status."""
    out = []
    for profile in profiles:
        if profile.get("reviewStatus") != "reviewed":
            continue
        claims = claim_rows(profile)
        for i, left in enumerate(claims):
            for right in claims[i + 1 :]:
                sid_a, claim_a, _ = left
                sid_b, claim_b, _ = right
                if sid_a == sid_b:
                    continue
                jac = token_jaccard(claim_a, claim_b)
                seq = SequenceMatcher(None, norm(claim_a), norm(claim_b)).ratio()
                if jac >= strict_jaccard and seq >= strict_sequence:
                    continue
                if jac < discovery_jaccard or seq < discovery_sequence:
                    continue
                out.append(pair_row(profile, left, right, jac, seq, discovery=True))
    unique = {}
    for row in out:
        key = (row["profile_id"], row["source_a"]["canonical_source_id"], row["source_b"]["canonical_source_id"], norm(row["claim_a"]), norm(row["claim_b"]))
        unique[key] = row
    rows = list(unique.values())
    rows.sort(
        key=lambda row: (
            -row["similarity"]["mean_score"],
            -row["similarity"]["token_jaccard"],
            -row["similarity"]["sequence_ratio"],
            row["profile_id"] or "",
            row["source_a"]["canonical_source_id"],
            row["source_b"]["canonical_source_id"],
            norm(row["claim_a"]),
            norm(row["claim_b"]),
        )
    )
    return rows[:top_k]


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
    exact_claim = "Older lower leaves first develop yellow-green lesions that later become necrotic."
    profile = {
        "id": "p1", "name": "Leaf spot", "category": "pathogen", "reviewStatus": "reviewed",
        "sources": [
            {"title": "A", "doi": "10.1234/a", "supportedClaims": [exact_claim, exact_claim]},
            {"title": "B", "url": "https://doi.org/10.5678/b", "supportedClaims": ["Older lower leaves first develop yellow-green lesions that later progress to necrosis."]},
            {"title": "C", "doi": "10.9999/c", "supportedClaims": ["This unrelated sentence describes a different mechanism entirely."]},
            {"title": "D", "doi": "10.7777/d", "supportedClaims": [exact_claim]},
            {"title": "E", "doi": "10.2468/e", "supportedClaims": ["Lower leaves show chlorotic spotting before affected tissue browns and dies."]},
        ],
    }
    rows = candidate_pairs([profile], 0.45, 0.55)
    assert len(rows) >= 3
    assert all(row["auto_merge"] is False for row in rows)
    assert all(row["review_status"] == "pending_proposition_equivalence_review" for row in rows)
    exact_rows = [row for row in rows if norm(row["claim_a"]) == norm(row["claim_b"])]
    assert len(exact_rows) == 1
    exact_row = exact_rows[0]
    exact_ids = {
        exact_row["source_a"]["canonical_source_id"],
        exact_row["source_b"]["canonical_source_id"],
    }
    assert exact_ids == {"doi:10.1234/a", "doi:10.7777/d"}

    discovery = discovery_pairs([profile], 0.45, 0.55, 0.10, 0.25, 10)
    assert discovery
    assert all(row["auto_merge"] is False for row in discovery)
    assert all(row["eligible_for_corroboration"] is False for row in discovery)
    assert all(row["eligible_for_training"] is False for row in discovery)
    assert all(row["review_status"] == "discovery_only_not_evidence" for row in discovery)
    assert all(not (row["similarity"]["token_jaccard"] >= 0.45 and row["similarity"]["sequence_ratio"] >= 0.55) for row in discovery)
    print("Corroboration review queue self-test: PASS")


def write_jsonl(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--discovery-output", type=pathlib.Path, default=DEFAULT_DISCOVERY_OUTPUT)
    parser.add_argument("--min-jaccard", type=float, default=0.45)
    parser.add_argument("--min-sequence", type=float, default=0.55)
    parser.add_argument("--discovery-min-jaccard", type=float, default=0.10)
    parser.add_argument("--discovery-min-sequence", type=float, default=0.25)
    parser.add_argument("--discovery-top-k", type=int, default=100)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    profiles = load_jsonl(args.input)
    rows = candidate_pairs(profiles, args.min_jaccard, args.min_sequence)
    discovery = discovery_pairs(
        profiles,
        args.min_jaccard,
        args.min_sequence,
        args.discovery_min_jaccard,
        args.discovery_min_sequence,
        args.discovery_top_k,
    )
    if not args.check_only:
        write_jsonl(args.output, rows)
        write_jsonl(args.discovery_output, discovery)
    print(json.dumps({
        "corroboration_review_candidates": len(rows),
        "discovery_only_candidates": len(discovery),
        "auto_merged": 0,
        "training_promoted": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
