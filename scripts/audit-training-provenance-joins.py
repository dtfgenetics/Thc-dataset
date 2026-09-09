#!/usr/bin/env python3
"""Fail closed when generated Grow Doc supervision loses citation provenance joins."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_BUILDER = ROOT / "scripts/build-model-corpus.py"
GQA_BUILDER = ROOT / "scripts/build-grounded-qa.py"
INPUT = ROOT / "data/diagnostic-profiles.jsonl"
HELDOUT = ROOT / "model_tuning/eval/heldout_v2.jsonl"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def has_locator(source: dict) -> bool:
    return bool((source.get("doi") or "").strip() or (source.get("url") or "").strip())


def audit_rows(rag_rows: list[dict], sft_rows: list[dict], gqa_rows: list[dict]) -> list[str]:
    errors: list[str] = []
    rag_source_records: dict[str, list[dict]] = {}
    for row in rag_rows:
        for source in row.get("sources") or []:
            sid = str(source.get("source_id") or "").strip()
            if sid:
                rag_source_records.setdefault(sid, []).append(source)

    for row in sft_rows:
        rid = row.get("id") or "<missing-id>"
        source_ids = [str(x).strip() for x in (row.get("source_ids") or []) if str(x).strip()]
        if not source_ids:
            errors.append(f"{rid}: missing source_ids")
            continue
        assistant_text = "\n".join(
            str(m.get("content") or "") for m in (row.get("messages") or []) if m.get("role") == "assistant"
        )
        for sid in source_ids:
            records = rag_source_records.get(sid) or []
            if not records:
                errors.append(f"{rid}: source_id {sid!r} has no matching RAG provenance record")
            elif not any(has_locator(source) for source in records):
                errors.append(f"{rid}: source_id {sid!r} lacks DOI/URL provenance")
            if sid not in assistant_text:
                errors.append(f"{rid}: source_id {sid!r} is not cited in assistant output")

    for row in gqa_rows:
        rid = row.get("id") or "<missing-id>"
        source_ids = [str(x).strip() for x in (row.get("source_ids") or []) if str(x).strip()]
        must_cite = [str(x).strip() for x in (row.get("must_cite") or []) if str(x).strip()]
        sources = row.get("sources") or []
        source_map = {str(source.get("source_id") or "").strip(): source for source in sources}
        if not source_ids:
            errors.append(f"{rid}: missing source_ids")
        if set(source_ids) != set(must_cite):
            errors.append(f"{rid}: source_ids and must_cite differ")
        for sid in source_ids:
            source = source_map.get(sid)
            if source is None:
                errors.append(f"{rid}: source_id {sid!r} missing from sources metadata")
            elif not has_locator(source):
                errors.append(f"{rid}: source_id {sid!r} lacks DOI/URL provenance")

    return errors


def self_test() -> None:
    rag = [{"sources": [{"source_id": "doi:10.x/a", "doi": "10.x/a"}]}]
    sft = [{
        "id": "s1",
        "source_ids": ["doi:10.x/a"],
        "messages": [{"role": "assistant", "content": "Supported. Citations: doi:10.x/a"}],
    }]
    gqa = [{
        "id": "g1",
        "source_ids": ["doi:10.x/a"],
        "must_cite": ["doi:10.x/a"],
        "sources": [{"source_id": "doi:10.x/a", "doi": "10.x/a"}],
    }]
    assert audit_rows(rag, sft, gqa) == []
    broken = [{"id": "s2", "source_ids": ["doi:10.x/missing"], "messages": [{"role": "assistant", "content": "uncited"}]}]
    errors = audit_rows(rag, broken, gqa)
    assert any("no matching RAG provenance" in error for error in errors)
    assert any("not cited in assistant output" in error for error in errors)
    bad_gqa = [{"id": "g2", "source_ids": ["doi:10.x/a"], "must_cite": [], "sources": []}]
    errors = audit_rows(rag, sft, bad_gqa)
    assert any("source_ids and must_cite differ" in error for error in errors)
    assert any("missing from sources metadata" in error for error in errors)
    print("training provenance join audit self-test: PASS")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0

    corpus = load_module(CORPUS_BUILDER, "growdoc_corpus")
    gqa_builder = load_module(GQA_BUILDER, "growdoc_gqa")
    rag_rows, sft_rows, _quarantine, _stats = corpus.build(INPUT, HELDOUT)
    gqa_rows, _gqa_stats = gqa_builder.build(INPUT, HELDOUT)
    errors = audit_rows(rag_rows, sft_rows, gqa_rows)
    if errors:
        print("training provenance join audit: FAIL")
        for error in errors[:50]:
            print(f"- {error}")
        if len(errors) > 50:
            print(f"- ... {len(errors) - 50} additional errors")
        return 1
    print(f"training provenance join audit: PASS ({len(sft_rows)} SFT, {len(gqa_rows)} grounded-QA, {len(rag_rows)} RAG claims)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
