#!/usr/bin/env python3
"""Audit Grow Doc JSONL lanes for duplicate supervision and train/eval leakage.

The audit is deliberately schema-tolerant: it extracts common prompt/answer/source
fields without rewriting records. Exact and normalized fingerprints are used to
surface duplicate rows and cross-lane overlap. Evaluation leakage is treated as a
hard failure; within-training duplication is reported separately so cleanup can be
reviewed without silently deleting provenance-bearing examples.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

PROMPT_FIELDS = (
    "prompt", "question", "instruction", "input", "query", "user", "task",
)
ANSWER_FIELDS = (
    "answer", "response", "output", "assistant", "completion", "target",
)
SOURCE_FIELDS = (
    "source_id", "source_ids", "sources", "citations", "citation_ids",
    "source_component_id", "source_component_ids", "provenance",
)
TRAIN_HINTS = ("train", "sft", "grounded_qa_mixture")
EVAL_HINTS = ("eval", "heldout", "benchmark", "test")


def canonical_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def prompt_text(record: dict[str, Any]) -> str:
    for field in PROMPT_FIELDS:
        if field in record and record[field] not in (None, "", [], {}):
            return canonical_text(record[field])
    messages = record.get("messages")
    if isinstance(messages, list):
        parts = []
        for msg in messages:
            if isinstance(msg, dict) and str(msg.get("role", "")).casefold() in {"system", "user"}:
                if msg.get("content") not in (None, ""):
                    parts.append(canonical_text(msg["content"]))
        return "\n".join(parts)
    return ""


def answer_text(record: dict[str, Any]) -> str:
    for field in ANSWER_FIELDS:
        if field in record and record[field] not in (None, "", [], {}):
            return canonical_text(record[field])
    messages = record.get("messages")
    if isinstance(messages, list):
        parts = []
        for msg in messages:
            if isinstance(msg, dict) and str(msg.get("role", "")).casefold() == "assistant":
                if msg.get("content") not in (None, ""):
                    parts.append(canonical_text(msg["content"]))
        return "\n".join(parts)
    return ""


def source_text(record: dict[str, Any]) -> str:
    values: list[str] = []
    for field in SOURCE_FIELDS:
        if field in record and record[field] not in (None, "", [], {}):
            values.append(canonical_text(record[field]))
    return "\n".join(values)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fingerprint(record: dict[str, Any]) -> dict[str, str]:
    prompt = prompt_text(record)
    answer = answer_text(record)
    source = source_text(record)
    return {
        "prompt_sha256": sha(prompt) if prompt else "",
        "answer_sha256": sha(answer) if answer else "",
        "pair_sha256": sha(prompt + "\n<ANSWER>\n" + answer) if prompt or answer else "",
        "source_sha256": sha(source) if source else "",
    }


def lane_role(path: Path) -> str:
    name = path.as_posix().casefold()
    if any(h in name for h in EVAL_HINTS):
        return "eval"
    if any(h in name for h in TRAIN_HINTS):
        return "train"
    return "other"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: each JSONL row must be an object")
        rows.append(row)
    return rows


def audit(paths: list[Path]) -> dict[str, Any]:
    occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
    prompt_occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
    lane_counts: dict[str, int] = {}
    missing_prompt = 0
    missing_answer = 0
    missing_source = 0

    for path in paths:
        rows = load_jsonl(path)
        lane_counts[str(path)] = len(rows)
        role = lane_role(path)
        for idx, row in enumerate(rows, 1):
            fp = fingerprint(row)
            if not fp["prompt_sha256"]:
                missing_prompt += 1
            if not fp["answer_sha256"]:
                missing_answer += 1
            if not fp["source_sha256"]:
                missing_source += 1
            entry = {"path": str(path), "line": idx, "role": role}
            if fp["pair_sha256"]:
                occurrences[fp["pair_sha256"]].append(entry)
            if fp["prompt_sha256"]:
                prompt_occurrences[fp["prompt_sha256"]].append(entry)

    duplicate_pairs = {digest: refs for digest, refs in occurrences.items() if len(refs) > 1}
    duplicate_prompts = {digest: refs for digest, refs in prompt_occurrences.items() if len(refs) > 1}

    def crosses_train_eval(refs: list[dict[str, Any]]) -> bool:
        roles = {r["role"] for r in refs}
        return "train" in roles and "eval" in roles

    pair_leaks = {d: refs for d, refs in duplicate_pairs.items() if crosses_train_eval(refs)}
    prompt_leaks = {d: refs for d, refs in duplicate_prompts.items() if crosses_train_eval(refs)}

    return {
        "schema_version": "grow-doc-dedup-audit-v1",
        "lanes": lane_counts,
        "totals": {
            "rows": sum(lane_counts.values()),
            "missing_prompt": missing_prompt,
            "missing_answer": missing_answer,
            "missing_source_metadata": missing_source,
            "duplicate_pair_groups": len(duplicate_pairs),
            "duplicate_prompt_groups": len(duplicate_prompts),
            "train_eval_pair_leak_groups": len(pair_leaks),
            "train_eval_prompt_leak_groups": len(prompt_leaks),
        },
        "duplicate_pairs": duplicate_pairs,
        "duplicate_prompts": duplicate_prompts,
        "train_eval_pair_leaks": pair_leaks,
        "train_eval_prompt_leaks": prompt_leaks,
        "pass": not pair_leaks and not prompt_leaks,
    }


def self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        train = root / "train_sft.jsonl"
        heldout = root / "heldout_eval.jsonl"

        train_rows = [
            {
                "question": "What does VPD describe?",
                "answer": "The vapor-pressure difference driving plant transpiration.",
                "sources": [{"id": "src-a"}],
            },
            {
                "messages": [
                    {"role": "user", "content": "Explain photoperiod."},
                    {"role": "assistant", "content": "It is the daily light/dark duration."},
                ],
                "source_id": "src-b",
            },
        ]
        heldout_rows = [
            {
                "question": "  WHAT does VPD describe? ",
                "answer": "Different wording is enough to avoid pair duplication, but prompt leakage must still fail.",
                "citations": ["src-c"],
            }
        ]
        train.write_text("\n".join(json.dumps(r) for r in train_rows) + "\n", encoding="utf-8")
        heldout.write_text("\n".join(json.dumps(r) for r in heldout_rows) + "\n", encoding="utf-8")

        report = audit([train, heldout])
        assert report["totals"]["rows"] == 3
        assert report["totals"]["train_eval_pair_leak_groups"] == 0
        assert report["totals"]["train_eval_prompt_leak_groups"] == 1
        assert report["pass"] is False

        heldout.write_text(
            json.dumps({
                "question": "How does photoperiod differ from PPFD?",
                "answer": "They describe duration versus photon flux density.",
                "citations": ["src-c"],
            }) + "\n",
            encoding="utf-8",
        )
        clean = audit([train, heldout])
        assert clean["pass"] is True
        assert clean["totals"]["missing_source_metadata"] == 0
    print("Grow Doc dedup/leakage audit self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", nargs="*", type=Path, help="training/dev/eval JSONL lanes to audit")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--fail-on-missing-provenance",
        action="store_true",
        help="also fail when any row lacks recognizable source/citation metadata",
    )
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if not args.jsonl:
        parser.error("provide one or more JSONL lanes, or use --self-test")

    report = audit(args.jsonl)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["totals"], sort_keys=True))

    fail = not report["pass"]
    if args.fail_on_missing_provenance and report["totals"]["missing_source_metadata"]:
        fail = True
    return 2 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
