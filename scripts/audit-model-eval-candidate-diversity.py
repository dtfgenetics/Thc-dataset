#!/usr/bin/env python3
"""Audit Grow Doc evaluation candidates for internal duplication and concentration.

Hard failure:
- exact normalized prompt duplicates inside the candidate pool.

Report-only review signals:
- reused canonical sources across multiple candidate cases;
- high-similarity semantic candidate pairs.

Scientifically distinct cases can legitimately share a source or vocabulary, so
those signals are never auto-deleted or auto-rebalanced by this audit.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import defaultdict

from source_identity import canonical_source_identity

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MANIFESTS = (
    ROOT / "model_tuning/eval/candidates/pathogen_expansion_v1.manifest.json",
    ROOT / "model_tuning/eval/candidates/heldout_v3_expansion_v1.manifest.json",
)
DEFAULT_DIRECT_DATASETS = (
    ROOT / "model_tuning/eval/heldout_v3_candidates.jsonl",
)
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def load_candidate_rows(manifests: list[pathlib.Path], direct_datasets: list[pathlib.Path]) -> list[dict]:
    rows: list[dict] = []
    seen_ids: set[str] = set()

    def add_rows(dataset_path: pathlib.Path) -> None:
        for row in load_jsonl(dataset_path):
            rid = row.get("id")
            if not isinstance(rid, str) or not rid.strip():
                raise ValueError(f"{dataset_path}: candidate missing id")
            if rid in seen_ids:
                raise ValueError(f"duplicate candidate id across candidate datasets: {rid}")
            seen_ids.add(rid)
            rows.append(row)

    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        dataset_rel = manifest.get("dataset")
        if not isinstance(dataset_rel, str) or not dataset_rel:
            raise ValueError(f"{manifest_path}: missing dataset")
        add_rows(ROOT / dataset_rel)

    for dataset_path in direct_datasets:
        add_rows(dataset_path)
    return rows


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())).strip()


def tokens(text: str) -> set[str]:
    return set(norm(text).split())


def eval_text(row: dict) -> str:
    parts = [row.get("prompt") or ""]
    parts.extend(str(value) for value in row.get("expected_points") or [])
    return "\n".join(parts).strip()


def similarity(left: str, right: str) -> tuple[float, float, float]:
    lt, rt = tokens(left), tokens(right)
    if not lt or not rt:
        return 0.0, 0.0, 0.0
    overlap = len(lt & rt)
    containment = overlap / min(len(lt), len(rt))
    jaccard = overlap / len(lt | rt)
    length_ratio = min(len(lt), len(rt)) / max(len(lt), len(rt))
    return containment, jaccard, length_ratio


def audit(rows: list[dict], *, near_limit: int = 25) -> dict:
    prompt_groups: dict[str, list[str]] = defaultdict(list)
    source_groups: dict[str, list[str]] = defaultdict(list)
    errors: list[str] = []
    near: list[dict] = []

    for row in rows:
        rid = row.get("id") or "<missing>"
        prompt_key = norm(row.get("prompt") or "")
        if prompt_key:
            prompt_groups[prompt_key].append(rid)
        for source in row.get("must_cite") or []:
            identity = canonical_source_identity(str(source))
            if identity:
                source_groups[identity].append(rid)

    exact_prompt_groups = [sorted(ids) for ids in prompt_groups.values() if len(ids) > 1]
    exact_prompt_groups.sort()
    for ids in exact_prompt_groups:
        errors.append(f"exact normalized candidate prompt duplicate: {ids}")

    reused_sources = [
        {"source": source, "candidate_ids": sorted(set(ids)), "candidate_count": len(set(ids))}
        for source, ids in source_groups.items()
        if len(set(ids)) > 1
    ]
    reused_sources.sort(key=lambda item: (-item["candidate_count"], item["source"]))

    for index, left in enumerate(rows):
        left_text = eval_text(left)
        if len(tokens(left_text)) < 8:
            continue
        for right in rows[index + 1 :]:
            right_text = eval_text(right)
            if len(tokens(right_text)) < 8:
                continue
            containment, jaccard, length_ratio = similarity(left_text, right_text)
            if containment >= 0.78 and jaccard >= 0.50 and length_ratio >= 0.45:
                near.append(
                    {
                        "left_id": left.get("id") or "<missing>",
                        "right_id": right.get("id") or "<missing>",
                        "containment": round(containment, 3),
                        "jaccard": round(jaccard, 3),
                        "length_ratio": round(length_ratio, 3),
                    }
                )

    near.sort(key=lambda item: (-item["jaccard"], -item["containment"], item["left_id"], item["right_id"]))
    return {
        "candidate_records": len(rows),
        "unique_canonical_sources": len(source_groups),
        "hard_duplicate_errors": len(errors),
        "errors": errors,
        "reused_source_groups": len(reused_sources),
        "reused_source_examples": reused_sources[:near_limit],
        "semantic_near_duplicate_pairs": len(near),
        "semantic_near_duplicate_examples": near[:near_limit],
        "policy": {
            "exact_normalized_prompt_duplicate": "fail",
            "canonical_source_reuse": "report_for_independent_review",
            "semantic_near_duplicate": "report_for_independent_review",
            "auto_delete_or_rebalance": False,
            "candidate_status_after_pass": "candidate_only_not_promotion_eligible",
        },
    }


def self_test() -> None:
    clean = [
        {"id": "a", "prompt": "Explain source-bounded evidence.", "expected_points": ["Keep limits."], "must_cite": ["doi:10.1/a"]},
        {"id": "b", "prompt": "Explain diagnostic uncertainty.", "expected_points": ["Request measurements."], "must_cite": ["doi:10.1/b"]},
    ]
    assert audit(clean)["hard_duplicate_errors"] == 0

    duplicate = clean + [
        {"id": "c", "prompt": "Explain, source bounded evidence!", "expected_points": ["Different wording."], "must_cite": ["doi:10.1/c"]}
    ]
    assert audit(duplicate)["hard_duplicate_errors"] == 1

    reused = clean + [
        {"id": "c", "prompt": "A distinct question using the same paper.", "expected_points": ["Keep context."], "must_cite": ["https://doi.org/10.1/A"]}
    ]
    report = audit(reused)
    assert report["hard_duplicate_errors"] == 0
    assert report["reused_source_groups"] == 1
    print("model eval candidate diversity self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", action="append", type=pathlib.Path, dest="manifests")
    parser.add_argument("--candidate-dataset", action="append", type=pathlib.Path, dest="candidate_datasets")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    manifests = args.manifests or list(DEFAULT_MANIFESTS)
    direct_datasets = args.candidate_datasets or list(DEFAULT_DIRECT_DATASETS)
    try:
        rows = load_candidate_rows(manifests, direct_datasets)
        report = audit(rows)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    if report["hard_duplicate_errors"]:
        print(f"candidate diversity audit: FAIL ({report['hard_duplicate_errors']} hard errors)", file=sys.stderr)
        return 1
    print("candidate diversity audit: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
