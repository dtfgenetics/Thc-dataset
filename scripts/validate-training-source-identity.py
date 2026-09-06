#!/usr/bin/env python3
"""Fail closed on canonical source leakage in frozen Grow Doc train/dev artifacts.

The corpus builder canonicalizes DOI source IDs to lowercase. Held-out fixtures may
retain publication-style DOI casing. This audit compares source identity using the
same DOI semantics so a case-only DOI variant cannot evade train/dev or held-out
leakage checks.

This validates data identity only. It does not train, merge, or promote a model.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAIN_SFT = ROOT / "model_tuning/generated/splits/train_sft_v1.jsonl"
DEFAULT_DEV_SFT = ROOT / "model_tuning/generated/splits/dev_sft_v1.jsonl"
DEFAULT_TRAIN_GQA = ROOT / "model_tuning/generated/splits/train_grounded_qa_v1.jsonl"
DEFAULT_DEV_GQA = ROOT / "model_tuning/generated/splits/dev_grounded_qa_v1.jsonl"
DEFAULT_HELDOUT = ROOT / "model_tuning/eval/heldout_v2.jsonl"


def canonical_source_id(value: str) -> str:
    source_id = str(value or "").strip()
    if not source_id:
        return ""
    prefix, sep, rest = source_id.partition(":")
    if not sep:
        return source_id
    prefix_l = prefix.lower()
    rest = rest.strip()
    if prefix_l == "doi":
        return f"doi:{rest.lower()}"
    if prefix_l in {"url", "source"}:
        return f"{prefix_l}:{rest}"
    return source_id


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: expected JSON object")
        rows.append(row)
    return rows


def collect_source_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_l = str(key).lower()
            if key_l in {"source_id", "sourceid"} and isinstance(child, str):
                canonical = canonical_source_id(child)
                if canonical:
                    found.add(canonical)
            elif key_l in {"source_ids", "sourceids", "must_cite"} and isinstance(child, list):
                for item in child:
                    canonical = canonical_source_id(str(item))
                    if canonical:
                        found.add(canonical)
            found.update(collect_source_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(collect_source_ids(child))
    return found


def dataset_sources(path: Path, *, require_every_row: bool) -> tuple[set[str], int, int]:
    rows = load_jsonl(path)
    sources: set[str] = set()
    rows_with_sources = 0
    for row in rows:
        row_sources = collect_source_ids(row)
        if row_sources:
            rows_with_sources += 1
            sources.update(row_sources)
    if require_every_row and rows_with_sources != len(rows):
        raise ValueError(
            f"{path}: every training/dev row must preserve source identifiers "
            f"({rows_with_sources}/{len(rows)} rows have provenance)"
        )
    return sources, len(rows), rows_with_sources


def audit(*, train_sft: Path, dev_sft: Path, train_gqa: Path, dev_gqa: Path, heldout: Path) -> dict[str, Any]:
    train_sft_sources, train_sft_rows, _ = dataset_sources(train_sft, require_every_row=True)
    dev_sft_sources, dev_sft_rows, _ = dataset_sources(dev_sft, require_every_row=True)
    train_gqa_sources, train_gqa_rows, _ = dataset_sources(train_gqa, require_every_row=True)
    dev_gqa_sources, dev_gqa_rows, _ = dataset_sources(dev_gqa, require_every_row=True)
    heldout_sources, heldout_rows, _ = dataset_sources(heldout, require_every_row=False)

    train_sources = train_sft_sources | train_gqa_sources
    dev_sources = dev_sft_sources | dev_gqa_sources
    train_dev_overlap = sorted(train_sources & dev_sources)
    heldout_overlap = sorted((train_sources | dev_sources) & heldout_sources)

    if train_dev_overlap:
        raise ValueError("canonical source leakage across train/dev: " + ", ".join(train_dev_overlap))
    if heldout_overlap:
        raise ValueError("canonical held-out source leakage into train/dev: " + ", ".join(heldout_overlap))

    return {
        "schema_version": "grow-doc-training-source-identity-audit-v1",
        "canonicalization": "doi-lowercase-v1",
        "rows": {
            "train_sft": train_sft_rows,
            "dev_sft": dev_sft_rows,
            "train_grounded_qa": train_gqa_rows,
            "dev_grounded_qa": dev_gqa_rows,
            "heldout": heldout_rows,
        },
        "unique_sources": {
            "train": len(train_sources),
            "dev": len(dev_sources),
            "heldout": len(heldout_sources),
        },
        "train_dev_overlap": 0,
        "heldout_training_overlap": 0,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def self_test() -> None:
    assert canonical_source_id("doi:10.1094/PDIS-04-19-0782-PDN") == "doi:10.1094/pdis-04-19-0782-pdn"
    assert canonical_source_id("DOI:10.1094/pdis-04-19-0782-pdn") == "doi:10.1094/pdis-04-19-0782-pdn"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = {name: root / f"{name}.jsonl" for name in ("train_sft", "dev_sft", "train_gqa", "dev_gqa", "heldout")}
        write_jsonl(paths["train_sft"], [{"id": "s1", "source_ids": ["doi:10.1000/train"]}])
        write_jsonl(paths["dev_sft"], [{"id": "d1", "source_ids": ["doi:10.1000/dev"]}])
        write_jsonl(paths["train_gqa"], [{"id": "q1", "source_ids": ["url:https://example.org/train"]}])
        write_jsonl(paths["dev_gqa"], [{"id": "dq1", "source_ids": ["url:https://example.org/dev"]}])
        write_jsonl(paths["heldout"], [{"id": "h1", "must_cite": ["doi:10.1094/PDIS-04-19-0782-PDN"]}])
        result = audit(**paths)
        assert result["heldout_training_overlap"] == 0

        # A case-only DOI variant must still be recognized as the same held-out source.
        write_jsonl(paths["train_sft"], [{"id": "s1", "source_ids": ["doi:10.1094/pdis-04-19-0782-pdn"]}])
        try:
            audit(**paths)
        except ValueError as exc:
            assert "canonical held-out source leakage" in str(exc)
        else:
            raise AssertionError("case-only DOI leakage was not rejected")

        # Missing provenance in any training/dev row must fail closed.
        write_jsonl(paths["train_sft"], [{"id": "s1"}])
        try:
            audit(**paths)
        except ValueError as exc:
            assert "preserve source identifiers" in str(exc)
        else:
            raise AssertionError("missing training provenance was not rejected")
    print("training source identity self-test: ok")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-sft", type=Path, default=DEFAULT_TRAIN_SFT)
    parser.add_argument("--dev-sft", type=Path, default=DEFAULT_DEV_SFT)
    parser.add_argument("--train-grounded-qa", dest="train_gqa", type=Path, default=DEFAULT_TRAIN_GQA)
    parser.add_argument("--dev-grounded-qa", dest="dev_gqa", type=Path, default=DEFAULT_DEV_GQA)
    parser.add_argument("--heldout", type=Path, default=DEFAULT_HELDOUT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    result = audit(
        train_sft=args.train_sft,
        dev_sft=args.dev_sft,
        train_gqa=args.train_gqa,
        dev_gqa=args.dev_gqa,
        heldout=args.heldout,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
