#!/usr/bin/env python3
"""Fail closed when generated Grow Doc supervision loses citation provenance joins."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from urllib.parse import urlsplit

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


def canonical_source_identity(value: str) -> str:
    """Canonicalize DOI/URL aliases when counting independent source support."""
    raw = (value or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered.startswith("doi:"):
        return f"doi:{raw[4:].strip().lower()}"
    if lowered.startswith("url:"):
        raw = raw[4:].strip()
        lowered = raw.lower()
    if lowered.startswith("10.") and "/" in raw:
        return f"doi:{lowered}"
    parsed = urlsplit(raw)
    if parsed.scheme.lower() in {"http", "https"} and parsed.netloc:
        host = (parsed.hostname or "").lower()
        if host in {"doi.org", "www.doi.org", "dx.doi.org"}:
            doi = parsed.path.lstrip("/").strip().lower()
            return f"doi:{doi}" if doi else ""
        path = (parsed.path or "/").rstrip("/") or "/"
        query = f"?{parsed.query}" if parsed.query else ""
        return f"url:{parsed.scheme.lower()}://{host}{path}{query}"
    return lowered


def source_record_identity(source: dict) -> str:
    doi = str(source.get("doi") or "").strip()
    if doi:
        return canonical_source_identity(f"doi:{doi}")
    url = str(source.get("url") or "").strip()
    if url:
        return canonical_source_identity(url)
    return canonical_source_identity(str(source.get("source_id") or ""))


def audit_rows(rag_rows: list[dict], sft_rows: list[dict], gqa_rows: list[dict]) -> list[str]:
    errors: list[str] = []
    rag_source_records: dict[str, list[dict]] = {}
    for row in rag_rows:
        rid = row.get("id") or "<missing-rag-id>"
        source_ids = [str(x).strip() for x in (row.get("source_ids") or []) if str(x).strip()]
        sources = row.get("sources") or []
        source_identities = {canonical_source_identity(sid) for sid in source_ids if canonical_source_identity(sid)}
        metadata_identities = {source_record_identity(source) for source in sources if source_record_identity(source)}
        if not source_ids:
            errors.append(f"{rid}: RAG row missing source_ids")
        if not sources:
            errors.append(f"{rid}: RAG row missing sources metadata")
        if source_identities != metadata_identities:
            errors.append(f"{rid}: RAG source_ids and sources metadata differ canonically")
        for source in sources:
            sid = str(source.get("source_id") or "").strip()
            if not sid:
                errors.append(f"{rid}: RAG source metadata missing source_id")
                continue
            if not has_locator(source):
                errors.append(f"{rid}: RAG source_id {sid!r} lacks DOI/URL provenance")
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


def support_counts(rag_rows: list[dict]) -> tuple[int, int]:
    single_source = 0
    multi_source = 0
    for row in rag_rows:
        identities = {
            canonical_source_identity(str(source_id))
            for source_id in (row.get("source_ids") or [])
            if canonical_source_identity(str(source_id))
        }
        if len(identities) >= 2:
            multi_source += 1
        elif len(identities) == 1:
            single_source += 1
    return single_source, multi_source


def self_test() -> None:
    rag = [{
        "id": "r1",
        "source_ids": ["doi:10.x/a"],
        "sources": [{"source_id": "doi:10.x/a", "doi": "10.x/a"}],
    }]
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
    assert support_counts(rag) == (1, 0)

    alias_rag = [{
        "id": "r-alias",
        "source_ids": ["doi:10.x/a", "url:https://doi.org/10.x/A"],
        "sources": [
            {"source_id": "doi:10.x/a", "doi": "10.x/a"},
            {"source_id": "url:https://doi.org/10.x/A", "url": "https://doi.org/10.x/A"},
        ],
    }]
    assert audit_rows(alias_rag, [], []) == []
    assert support_counts(alias_rag) == (1, 0), "DOI URL aliases must not count as independent corroboration"

    corroborated_rag = [{
        "id": "r2",
        "source_ids": ["doi:10.x/a", "doi:10.x/b"],
        "sources": [
            {"source_id": "doi:10.x/a", "doi": "10.x/a"},
            {"source_id": "doi:10.x/b", "doi": "10.x/b"},
        ],
    }]
    assert audit_rows(corroborated_rag, [], []) == []
    assert support_counts(corroborated_rag) == (0, 1)

    mismatched_rag = [{
        "id": "r-bad",
        "source_ids": ["doi:10.x/a", "doi:10.x/b"],
        "sources": [{"source_id": "doi:10.x/a", "doi": "10.x/a"}],
    }]
    errors = audit_rows(mismatched_rag, [], [])
    assert any("source_ids and sources metadata differ canonically" in error for error in errors)

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
    single_source, multi_source = support_counts(rag_rows)
    print(
        "training provenance join audit: PASS "
        f"({len(sft_rows)} SFT, {len(gqa_rows)} grounded-QA, {len(rag_rows)} RAG claims; "
        f"{single_source} single-source, {multi_source} independently multi-source)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
