#!/usr/bin/env python3
"""Audit redundancy inside the strong-evidence Grow Doc supervision lane.

This is intentionally conservative. It fails on exact normalized assistant-response duplication
across distinct examples, but only reports high-overlap semantic candidates for review. It does
not delete, rewrite, or repin training artifacts. Comparisons are task-local and exclude pairs
from the same profile so the three intentionally different SFT task templates do not create false
cross-task/profile alarms.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import sys
from collections import Counter
from types import ModuleType

ROOT = pathlib.Path(__file__).resolve().parents[1]
ELIGIBLE_BUILDER = ROOT / "scripts/build-training-eligible-supervision.py"
TOKEN_RE = re.compile(r"[a-z0-9]+")
SOURCE_ID_RE = re.compile(r"(?:doi|url|source):\S+", re.IGNORECASE)
STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "if",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "use", "with", "without",
    "evidence", "citations", "citation", "supplied", "supported", "supporting", "important",
}
DEFAULT_THRESHOLD = 0.82


def load_module(path: pathlib.Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assistant_text(record: dict) -> str:
    return "\n".join(
        str(message.get("content") or "")
        for message in (record.get("messages") or [])
        if message.get("role") == "assistant"
    ).strip()


def normalized_text(text: str) -> str:
    text = SOURCE_ID_RE.sub(" ", (text or "").lower())
    return " ".join(TOKEN_RE.findall(text))


def token_set(text: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(SOURCE_ID_RE.sub(" ", (text or "").lower())) if token not in STOP}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def audit(records: list[dict], threshold: float = DEFAULT_THRESHOLD) -> dict:
    exact_index: dict[tuple[str, str], list[dict]] = {}
    prepared = []
    by_task = Counter()

    for record in records:
        record_id = str(record.get("id") or "<missing-id>")
        task = str(record.get("task") or "<missing-task>")
        profile_id = str(record.get("profile_id") or "<missing-profile>")
        response = assistant_text(record)
        normalized = normalized_text(response)
        tokens = token_set(response)
        by_task[task] += 1
        prepared.append(
            {
                "id": record_id,
                "task": task,
                "profile_id": profile_id,
                "normalized": normalized,
                "tokens": tokens,
            }
        )
        if normalized:
            exact_index.setdefault((task, normalized), []).append(prepared[-1])

    exact_groups = []
    for (task, _), rows in exact_index.items():
        distinct_ids = sorted({row["id"] for row in rows})
        distinct_profiles = sorted({row["profile_id"] for row in rows})
        if len(distinct_ids) > 1:
            exact_groups.append(
                {
                    "task": task,
                    "record_ids": distinct_ids,
                    "profile_ids": distinct_profiles,
                }
            )

    near_pairs = []
    for idx, left in enumerate(prepared):
        for right in prepared[idx + 1 :]:
            if left["task"] != right["task"]:
                continue
            if left["profile_id"] == right["profile_id"]:
                continue
            if len(left["tokens"]) < 12 or len(right["tokens"]) < 12:
                continue
            score = jaccard(left["tokens"], right["tokens"])
            if score >= threshold:
                near_pairs.append(
                    {
                        "task": left["task"],
                        "left_id": left["id"],
                        "right_id": right["id"],
                        "left_profile_id": left["profile_id"],
                        "right_profile_id": right["profile_id"],
                        "token_jaccard": round(score, 4),
                    }
                )

    near_pairs.sort(key=lambda row: (-row["token_jaccard"], row["task"], row["left_id"], row["right_id"]))
    compared_pairs = sum(
        1
        for idx, left in enumerate(prepared)
        for right in prepared[idx + 1 :]
        if left["task"] == right["task"] and left["profile_id"] != right["profile_id"]
    )
    near_rate = (len(near_pairs) / compared_pairs) if compared_pairs else 0.0

    return {
        "schema_version": "grow-doc-training-supervision-redundancy-v1",
        "policy": {
            "scope": "strong-evidence training-eligible SFT and grounded-QA candidates",
            "rag_first": True,
            "automatic_deletion": False,
            "exact_duplicate_behavior": "hard error",
            "near_duplicate_behavior": "review queue only",
            "comparison_scope": "same task, different profile",
            "near_duplicate_threshold": threshold,
        },
        "candidate_examples": len(records),
        "by_task": dict(sorted(by_task.items())),
        "compared_pairs": compared_pairs,
        "exact_duplicate_groups": exact_groups,
        "exact_duplicate_group_count": len(exact_groups),
        "near_duplicate_pair_count": len(near_pairs),
        "near_duplicate_pair_rate": round(near_rate, 6),
        "near_duplicate_review_queue": near_pairs[:100],
        "hard_errors": len(exact_groups),
    }


def run() -> dict:
    eligible = load_module(ELIGIBLE_BUILDER, "grow_doc_training_supervision_redundancy")
    sft, qa, eligibility_report = eligible.run(eligible.DEFAULT_INPUT, eligible.DEFAULT_EVAL)
    report = audit(sft + qa)
    report["eligibility_snapshot"] = {
        "candidate_examples": eligibility_report["candidate_examples"],
        "training_eligible_examples": eligibility_report["training_eligible_examples"],
        "mixed_tier_examples": eligibility_report["mixed_tier_examples"],
        "weak_only_examples": eligibility_report["weak_only_examples"],
        "unknown_provenance_examples": eligibility_report["unknown_provenance_examples"],
    }
    return report


def self_test() -> None:
    records = [
        {
            "id": "a",
            "task": "science_education",
            "profile_id": "p1",
            "messages": [{"role": "assistant", "content": "Magnesium supports chlorophyll function and deficiency can cause interveinal chlorosis on older leaves. Citations: doi:10.x/a"}],
        },
        {
            "id": "b",
            "task": "science_education",
            "profile_id": "p2",
            "messages": [{"role": "assistant", "content": "Magnesium supports chlorophyll function and deficiency can cause interveinal chlorosis on older leaves. Citations: doi:10.x/b"}],
        },
        {
            "id": "c",
            "task": "science_education",
            "profile_id": "p3",
            "messages": [{"role": "assistant", "content": "Magnesium deficiency often presents with interveinal chlorosis on older foliage because Mg is mobile and participates in chlorophyll-related physiology."}],
        },
        {
            "id": "d",
            "task": "grounded_qa",
            "profile_id": "p4",
            "messages": [{"role": "assistant", "content": "A distinct answer in another task should not be compared."}],
        },
    ]
    report = audit(records, threshold=0.5)
    assert report["exact_duplicate_group_count"] == 1
    assert report["hard_errors"] == 1
    assert report["near_duplicate_pair_count"] >= 1
    assert report["by_task"]["science_education"] == 3
    print("training supervision redundancy self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit redundancy in training-eligible Grow Doc supervision.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if not 0.0 < args.threshold <= 1.0:
        print("ERROR: --threshold must be in (0, 1]", file=sys.stderr)
        return 2

    try:
        report = run()
        if args.threshold != DEFAULT_THRESHOLD:
            eligible = load_module(ELIGIBLE_BUILDER, "grow_doc_training_supervision_redundancy_custom")
            sft, qa, _ = eligible.run(eligible.DEFAULT_INPUT, eligible.DEFAULT_EVAL)
            report = audit(sft + qa, threshold=args.threshold)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    if report["hard_errors"]:
        print(
            f"training supervision redundancy: FAIL ({report['hard_errors']} exact duplicate groups)",
            file=sys.stderr,
        )
        return 1
    print("training supervision redundancy: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
