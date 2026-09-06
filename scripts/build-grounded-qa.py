#!/usr/bin/env python3
"""Build citation-grounded QA records from reviewed Grow Doc diagnostic evidence.

The QA lane is deliberately retrieval-conditioned: answers are generated only from supplied
source claims, carry source metadata, and exclude every provenance identifier reserved by the
held-out benchmark. This is not a place to encode the whole knowledge base into weights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import tempfile
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v2.jsonl"
DEFAULT_OUT = ROOT / "model_tuning/generated/grounded_qa/qa_v1.jsonl"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def canonical_doi(raw: str) -> str:
    """Return one DOI identity for bare, doi:-prefixed, and doi.org forms."""
    value = (raw or "").strip()
    value = re.sub(r"(?i)^doi:\s*", "", value)
    value = re.sub(r"(?i)^https?://(?:dx\.)?doi\.org/", "", value)
    return f"doi:{value.lower()}" if value else ""


def canonical_identifier(raw: str) -> str:
    """Canonicalize DOI aliases for comparison without rewriting ordinary URLs."""
    value = (raw or "").strip()
    if not value:
        return ""
    # Handle historical emitted IDs such as doi:https://doi.org/10.x/example.
    if re.match(r"(?i)^doi:\s*", value):
        return canonical_doi(value)
    if re.match(r"(?i)^https?://(?:dx\.)?doi\.org/", value):
        return canonical_doi(value)
    if re.match(r"(?i)^10\.\d{4,9}/\S+$", value):
        return canonical_doi(value)
    if re.match(r"(?i)^https?://", value):
        return f"url:{value}"
    return value


def source_id(source: dict) -> str:
    """Return the established emitted provenance ID; this is part of frozen dataset bytes."""
    doi = (source.get("doi") or "").strip()
    if doi:
        return f"doi:{doi.lower()}"
    url = (source.get("url") or "").strip()
    if url:
        return f"url:{url}"
    return ""


def source_comparison_id(source: dict) -> str:
    """Return canonical identity used only for held-out isolation and collision checks."""
    doi = (source.get("doi") or "").strip()
    if doi:
        return canonical_doi(doi)
    return canonical_identifier(source_id(source))


def heldout_source_ids(path: pathlib.Path) -> set[str]:
    reserved = set()
    if not path.exists():
        return reserved
    for row in load_jsonl(path):
        for raw in row.get("must_cite") or []:
            sid = canonical_identifier(raw)
            if sid:
                reserved.add(sid)
    return reserved


def source_metadata(source: dict) -> dict:
    return {
        "title": source.get("title"),
        "organization": source.get("organization"),
        "publisher": source.get("publisher"),
        "authors": source.get("authors") or [],
        "publicationDate": source.get("publicationDate"),
        "year": source.get("year"),
        "accessedDate": source.get("accessedDate"),
        "doi": source.get("doi"),
        "url": source.get("url"),
    }


def build(input_path: pathlib.Path, eval_path: pathlib.Path) -> tuple[list[dict], dict]:
    reserved = heldout_source_ids(eval_path)
    records = []
    seen = set()
    skipped = Counter()
    reviewed_profiles = 0

    for profile in load_jsonl(input_path):
        if profile.get("reviewStatus") != "reviewed":
            skipped["profile_not_reviewed"] += 1
            continue
        reviewed_profiles += 1
        profile_id = profile.get("id")
        profile_name = profile.get("name") or profile_id
        for source in profile.get("sources") or []:
            sid = source_id(source)
            comparison_sid = source_comparison_id(source)
            claims = [str(x).strip() for x in (source.get("supportedClaims") or []) if str(x).strip()]
            if not sid or not comparison_sid or not claims:
                skipped["source_missing_provenance_or_claims"] += 1
                continue
            if comparison_sid in reserved:
                skipped["heldout_source"] += 1
                continue

            evidence = "\n".join(f"- {claim}" for claim in claims[:3])
            answer = "\n".join(f"- {claim}" for claim in claims[:3])
            record_id = f"gqa-{profile_id}-{sha(sid + '|' + '|'.join(claims[:3]))[:12]}"
            if record_id in seen:
                skipped["duplicate_record"] += 1
                continue
            seen.add(record_id)
            records.append(
                {
                    "id": record_id,
                    "task": "grounded_qa",
                    "profile_id": profile_id,
                    "profile_name": profile_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Answer only from the supplied evidence. Do not add uncited facts. Cite the source identifier and say when the evidence is insufficient.",
                        },
                        {
                            "role": "user",
                            "content": f"Evidence from [{sid}]:\n{evidence}\n\nBased only on this evidence, what is scientifically supported about {profile_name}?",
                        },
                        {
                            "role": "assistant",
                            "content": f"The supplied evidence supports:\n{answer}\n\nCitation: {sid}\n\nThese statements should not be generalized beyond what this evidence establishes.",
                        },
                    ],
                    "source_ids": [sid],
                    "must_cite": [sid],
                    "sources": [{"source_id": sid, **source_metadata(source)}],
                    "grounded": True,
                    "context_required": True,
                    "heldout_source_excluded": True,
                }
            )

    collisions = [
        r["id"] for r in records
        if any(canonical_identifier(sid) in reserved for sid in (r.get("source_ids") or []))
    ]
    stats = {
        "reviewed_profiles": reviewed_profiles,
        "grounded_qa_examples": len(records),
        "heldout_source_ids": len(reserved),
        "heldout_source_collisions": len(collisions),
        "skipped": dict(skipped),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "eval_sha256": hashlib.sha256(eval_path.read_bytes()).hexdigest() if eval_path.exists() else None,
        "policy": "reviewed profiles only; canonical DOI identity used for held-out isolation; emitted provenance IDs remain byte-stable; context-required QA; held-out source families excluded; source metadata preserved",
    }
    if collisions:
        raise ValueError(f"held-out provenance leaked into grounded QA: {collisions[:3]}")
    return records, stats


def write_jsonl(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def self_test() -> None:
    reviewed = {
        "id": "p1",
        "name": "Example disorder",
        "reviewStatus": "reviewed",
        "sources": [
            {
                "doi": "10.X/TRAIN",
                "title": "Training source",
                "supportedClaims": ["Claim one is supported.", "Claim two is supported."],
            },
            {
                "doi": "https://doi.org/10.X/HELDOUT",
                "title": "Held-out source",
                "supportedClaims": ["This must not enter training QA."],
            },
        ],
    }
    unreviewed = {
        "id": "p2",
        "name": "Unreviewed",
        "reviewStatus": "draft",
        "sources": [{"doi": "10.x/draft", "supportedClaims": ["Draft claim."]}],
    }
    heldout = {"id": "e1", "prompt": "test", "must_cite": ["doi:10.x/heldout"]}
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        input_path = root / "input.jsonl"
        eval_path = root / "eval.jsonl"
        input_path.write_text(json.dumps(reviewed) + "\n" + json.dumps(unreviewed) + "\n", encoding="utf-8")
        eval_path.write_text(json.dumps(heldout) + "\n", encoding="utf-8")
        rows, stats = build(input_path, eval_path)
    assert canonical_doi("10.X/ABC") == "doi:10.x/abc"
    assert canonical_identifier("HTTPS://DOI.ORG/10.X/ABC") == "doi:10.x/abc"
    assert canonical_identifier("doi:10.X/ABC") == "doi:10.x/abc"
    assert canonical_identifier("doi:https://doi.org/10.X/ABC") == "doi:10.x/abc"
    assert len(rows) == 1
    # Emitted ID remains in the historical byte format, while comparison is canonical.
    assert rows[0]["source_ids"] == ["doi:10.x/train"]
    assert source_id({"doi": "https://doi.org/10.X/ABC"}) == "doi:https://doi.org/10.x/abc"
    assert source_comparison_id({"doi": "https://doi.org/10.X/ABC"}) == "doi:10.x/abc"
    assert rows[0]["must_cite"] == ["doi:10.x/train"]
    assert rows[0]["grounded"] is True and rows[0]["context_required"] is True
    assert stats["skipped"]["heldout_source"] == 1
    assert stats["skipped"]["profile_not_reviewed"] == 1
    assert stats["heldout_source_collisions"] == 0
    print("grounded QA builder self-test: PASS")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    ap.add_argument("--eval", type=pathlib.Path, default=DEFAULT_EVAL)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    try:
        rows, stats = build(args.input, args.eval)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not rows:
        print("grounded QA build produced no usable records", file=sys.stderr)
        return 1
    if not args.check_only:
        write_jsonl(args.out, rows)
    print(json.dumps(stats, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
