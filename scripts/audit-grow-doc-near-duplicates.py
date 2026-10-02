#!/usr/bin/env python3
"""Deterministic near-duplicate and train/eval contamination audit for Grow Doc.

Inspired by the candidate-generation -> verification separation used by DataTrove,
but implemented dependency-free for the relatively small Grow Doc corpus. No rows
are deleted: this tool emits provenance-bearing review clusters and fails closed
when a verified near-duplicate crosses the training/evaluation boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

DEFAULT_PROMPT_THRESHOLD = 0.82
DEFAULT_PAIR_THRESHOLD = 0.88
DEFAULT_SHINGLE_SIZE = 3


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.findall(r"[\w]+", text, flags=re.UNICODE))


def shingles(text: str, size: int = DEFAULT_SHINGLE_SIZE) -> set[str]:
    tokens = normalize(text).split()
    if not tokens:
        return set()
    if len(tokens) < size:
        return {" ".join(tokens)}
    return {" ".join(tokens[i:i + size]) for i in range(len(tokens) - size + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def lane(path: Path) -> str:
    value = str(path).casefold()
    return "eval" if any(token in value for token in ("eval", "heldout", "held-out", "benchmark", "test")) else "train"


def prompt_text(row: dict[str, Any]) -> str:
    if isinstance(row.get("question"), str):
        return row["question"]
    messages = row.get("messages")
    if isinstance(messages, list):
        values = [str(m.get("content", "")) for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        if values:
            return "\n".join(values)
    for key in ("prompt", "instruction", "input", "task"):
        if isinstance(row.get(key), str) and row[key].strip():
            return row[key]
    return ""


def answer_text(row: dict[str, Any]) -> str:
    for key in ("answer", "response", "output"):
        if isinstance(row.get(key), str):
            return row[key]
    messages = row.get("messages")
    if isinstance(messages, list):
        values = [str(m.get("content", "")) for m in messages if isinstance(m, dict) and m.get("role") == "assistant"]
        if values:
            return "\n".join(values)
    expected = row.get("expected_points")
    if isinstance(expected, list):
        return "\n".join(str(v) for v in expected)
    return ""


def source_ids(row: dict[str, Any]) -> list[str]:
    found: set[str] = set()
    if isinstance(row.get("source_id"), str):
        found.add(row["source_id"])
    sources = row.get("sources")
    if isinstance(sources, list):
        for item in sources:
            if isinstance(item, dict):
                for key in ("id", "source_id", "citation_id"):
                    if isinstance(item.get(key), str):
                        found.add(item[key])
    metadata = row.get("source_metadata")
    if isinstance(metadata, dict):
        for key in ("id", "source_id", "citation_id"):
            if isinstance(metadata.get(key), str):
                found.add(metadata[key])
    must_cite = row.get("must_cite")
    if isinstance(must_cite, list):
        found.update(str(v) for v in must_cite)
    return sorted(found)


def row_id(path: Path, index: int, row: dict[str, Any]) -> str:
    for key in ("id", "example_id", "record_id"):
        if row.get(key) is not None:
            return str(row[key])
    digest = hashlib.sha256((normalize(prompt_text(row)) + "\n" + normalize(answer_text(row))).encode()).hexdigest()[:12]
    return f"{path.name}:{index}:{digest}"


def load(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for index, raw in enumerate(handle, 1):
                if not raw.strip():
                    continue
                row = json.loads(raw)
                records.append({"path": path, "index": index, "lane": lane(path), "row": row})
    return records


def audit(paths: list[Path], prompt_threshold: float = DEFAULT_PROMPT_THRESHOLD,
          pair_threshold: float = DEFAULT_PAIR_THRESHOLD, shingle_size: int = DEFAULT_SHINGLE_SIZE) -> dict[str, Any]:
    records = load(paths)
    prepared = []
    for record in records:
        row = record["row"]
        prompt = prompt_text(row)
        answer = answer_text(row)
        prepared.append({**record, "id": row_id(record["path"], record["index"], row),
                         "sources": source_ids(row), "prompt": shingles(prompt, shingle_size),
                         "pair": shingles(prompt + "\n" + answer, shingle_size)})

    matches = []
    train_eval = 0
    within_training = 0
    for i, left in enumerate(prepared):
        for right in prepared[i + 1:]:
            ps = jaccard(left["prompt"], right["prompt"])
            fs = jaccard(left["pair"], right["pair"])
            reasons = []
            if ps >= prompt_threshold:
                reasons.append("prompt_near_duplicate")
            if fs >= pair_threshold:
                reasons.append("pair_near_duplicate")
            if not reasons:
                continue
            cross = left["lane"] != right["lane"]
            if cross:
                train_eval += 1
            elif left["lane"] == "train":
                within_training += 1
            matches.append({
                "left": {"id": left["id"], "path": str(left["path"]), "line": left["index"], "lane": left["lane"], "source_ids": left["sources"]},
                "right": {"id": right["id"], "path": str(right["path"]), "line": right["index"], "lane": right["lane"], "source_ids": right["sources"]},
                "prompt_jaccard": round(ps, 6), "pair_jaccard": round(fs, 6), "reasons": reasons,
                "train_eval_contamination": cross,
            })
    matches.sort(key=lambda x: (not x["train_eval_contamination"], -max(x["prompt_jaccard"], x["pair_jaccard"]), x["left"]["id"], x["right"]["id"]))
    return {
        "schema_version": "grow-doc-near-duplicate-audit-v1",
        "config": {"prompt_threshold": prompt_threshold, "pair_threshold": pair_threshold, "shingle_size": shingle_size},
        "totals": {"rows": len(records), "matches": len(matches), "train_eval_contamination": train_eval, "within_training_review": within_training},
        "pass": train_eval == 0,
        "matches": matches,
    }


def self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        train = root / "sft.jsonl"
        heldout = root / "heldout_eval.jsonl"
        train_rows = [
            {"id": "train-vpd", "question": "What does vapor pressure deficit describe in a grow room?", "answer": "It describes the vapor-pressure difference driving transpiration.", "sources": [{"id": "src-vpd"}]},
            {"id": "train-light", "question": "Explain photosynthetic photon flux density for growers.", "answer": "PPFD describes photon flux density in the PAR waveband.", "source_id": "src-light"},
            {"id": "train-light-paraphrase", "question": "Explain photosynthetic photon flux density for growers.", "answer": "PPFD describes photon flux density in the PAR waveband for cultivation.", "source_id": "src-light-2"},
        ]
        eval_row = {"id": "eval-vpd", "question": "What does vapor pressure deficit describe in a grow room?", "expected_points": ["It describes the vapor-pressure difference driving transpiration."], "must_cite": ["src-eval"]}
        train.write_text("\n".join(json.dumps(r) for r in train_rows) + "\n", encoding="utf-8")
        heldout.write_text(json.dumps(eval_row) + "\n", encoding="utf-8")
        report = audit([train, heldout], prompt_threshold=0.70, pair_threshold=0.75)
        assert report["pass"] is False
        assert report["totals"]["train_eval_contamination"] >= 1
        assert report["totals"]["within_training_review"] >= 1
        contaminated = [m for m in report["matches"] if m["train_eval_contamination"]]
        assert contaminated[0]["left"]["source_ids"] or contaminated[0]["right"]["source_ids"]

        heldout.write_text(json.dumps({"id": "eval-root", "question": "Which observations distinguish root-zone hypoxia from foliar light stress?", "expected_points": ["Use root-zone and canopy evidence."], "must_cite": ["src-root"]}) + "\n", encoding="utf-8")
        clean = audit([train, heldout], prompt_threshold=0.70, pair_threshold=0.75)
        assert clean["pass"] is True
        assert clean["totals"]["train_eval_contamination"] == 0
    print("Grow Doc near-duplicate audit self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", nargs="*", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--prompt-threshold", type=float, default=DEFAULT_PROMPT_THRESHOLD)
    parser.add_argument("--pair-threshold", type=float, default=DEFAULT_PAIR_THRESHOLD)
    parser.add_argument("--shingle-size", type=int, default=DEFAULT_SHINGLE_SIZE)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.jsonl:
        parser.error("provide JSONL lanes or use --self-test")
    if not (0 <= args.prompt_threshold <= 1 and 0 <= args.pair_threshold <= 1):
        parser.error("thresholds must be between 0 and 1")
    if args.shingle_size < 1:
        parser.error("shingle size must be >= 1")
    report = audit(args.jsonl, args.prompt_threshold, args.pair_threshold, args.shingle_size)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["totals"], sort_keys=True))
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
