#!/usr/bin/env python3
"""Prepare and unblind a deterministic human review packet for base-vs-RAG outputs.

The reviewer sees response A and response B but not which arm produced either answer.
A separate mapping file binds each displayed response to immutable raw response hashes.
Completed review packets can then be unblinded into the reviewed JSONL format expected
by score-base-vs-rag-eval.py without editing model response text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v2.jsonl"
SEED = 420


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no}: expected object")
        rows.append(value)
    return rows


def write_jsonl(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def arm_order(case_id: str) -> tuple[str, str]:
    digest = hashlib.sha256(f"grow-doc-base-rag-blind-v1|{SEED}|{case_id}".encode("utf-8")).digest()
    return ("base", "rag") if digest[0] % 2 == 0 else ("rag", "base")


def index_by_id(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        rid = row.get("id")
        if not rid or rid in result:
            raise ValueError(f"{label}: duplicate or missing id {rid!r}")
        result[str(rid)] = row
    return result


def prepare(eval_path: pathlib.Path, base_raw_path: pathlib.Path, rag_raw_path: pathlib.Path, packet_path: pathlib.Path, map_path: pathlib.Path) -> dict[str, Any]:
    cases = load_jsonl(eval_path)
    base = index_by_id(load_jsonl(base_raw_path), "base raw")
    rag = index_by_id(load_jsonl(rag_raw_path), "rag raw")
    case_ids = [str(case.get("id")) for case in cases]
    if set(case_ids) != set(base) or set(case_ids) != set(rag):
        raise ValueError("benchmark/base/RAG case IDs must match exactly")

    packet_rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    for case in cases:
        rid = str(case["id"])
        first, second = arm_order(rid)
        responses = {"base": str(base[rid].get("response") or ""), "rag": str(rag[rid].get("response") or "")}
        if not responses["base"] or not responses["rag"]:
            raise ValueError(f"{rid}: both raw responses must be non-empty")
        packet_rows.append({
            "id": rid,
            "category": case.get("category"),
            "difficulty": case.get("difficulty"),
            "prompt": case.get("prompt"),
            "expected_points": case.get("expected_points") or [],
            "must_cite": case.get("must_cite") or [],
            "forbidden_claims": case.get("forbidden_claims") or [],
            "response_a": responses[first],
            "response_b": responses[second],
            "point_scores_a": None,
            "point_scores_b": None,
            "reviewed_by": None,
            "review_notes": None,
        })
        mapping_rows.append({
            "id": rid,
            "a_arm": first,
            "b_arm": second,
            "response_a_sha256": sha_text(responses[first]),
            "response_b_sha256": sha_text(responses[second]),
        })

    write_jsonl(packet_path, packet_rows)
    mapping = {
        "schema_version": "grow-doc-base-rag-blind-map-v1",
        "seed": SEED,
        "benchmark_sha256": sha_file(eval_path),
        "base_raw_sha256": sha_file(base_raw_path),
        "rag_raw_sha256": sha_file(rag_raw_path),
        "review_packet_sha256": sha_file(packet_path),
        "rows": mapping_rows,
    }
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return mapping


def validate_scores(scores: Any, expected_count: int, rid: str, label: str) -> list[int]:
    if not isinstance(scores, list) or len(scores) != expected_count or any(value not in (0, 1) for value in scores):
        raise ValueError(f"{rid}: {label} must contain {expected_count} binary point scores")
    return [int(value) for value in scores]


def unblind(packet_path: pathlib.Path, map_path: pathlib.Path, base_out: pathlib.Path, rag_out: pathlib.Path) -> tuple[int, int]:
    packet = index_by_id(load_jsonl(packet_path), "completed review packet")
    mapping = json.loads(map_path.read_text(encoding="utf-8"))
    if mapping.get("schema_version") != "grow-doc-base-rag-blind-map-v1":
        raise ValueError("unsupported blind mapping schema")
    if mapping.get("review_packet_sha256") == sha_file(packet_path):
        # An untouched packet still has null review fields and will fail below. The equality is informational only.
        pass
    map_rows = {str(row["id"]): row for row in mapping.get("rows") or []}
    if set(packet) != set(map_rows):
        raise ValueError("completed review packet IDs differ from blind mapping")

    base_rows: list[dict[str, Any]] = []
    rag_rows: list[dict[str, Any]] = []
    for rid in sorted(packet):
        review = packet[rid]
        mapping_row = map_rows[rid]
        reviewed_by = review.get("reviewed_by")
        if not isinstance(reviewed_by, str) or not reviewed_by.strip():
            raise ValueError(f"{rid}: reviewed_by is required")
        expected_count = len(review.get("expected_points") or [])
        a_scores = validate_scores(review.get("point_scores_a"), expected_count, rid, "point_scores_a")
        b_scores = validate_scores(review.get("point_scores_b"), expected_count, rid, "point_scores_b")
        response_a = str(review.get("response_a") or "")
        response_b = str(review.get("response_b") or "")
        if sha_text(response_a) != mapping_row.get("response_a_sha256") or sha_text(response_b) != mapping_row.get("response_b_sha256"):
            raise ValueError(f"{rid}: response text was modified during review")

        annotated = {
            "a": {"id": rid, "response": response_a, "point_scores": a_scores, "reviewed_by": reviewed_by},
            "b": {"id": rid, "response": response_b, "point_scores": b_scores, "reviewed_by": reviewed_by},
        }
        for side, arm in (("a", mapping_row.get("a_arm")), ("b", mapping_row.get("b_arm"))):
            if arm == "base":
                base_rows.append(annotated[side])
            elif arm == "rag":
                rag_rows.append(annotated[side])
            else:
                raise ValueError(f"{rid}: invalid blind arm mapping")

    write_jsonl(base_out, sorted(base_rows, key=lambda row: row["id"]))
    write_jsonl(rag_out, sorted(rag_rows, key=lambda row: row["id"]))
    return len(base_rows), len(rag_rows)


def self_test() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        eval_path = root / "eval.jsonl"
        base_raw = root / "base.jsonl"
        rag_raw = root / "rag.jsonl"
        packet = root / "packet.jsonl"
        mapping = root / "mapping.json"
        write_jsonl(eval_path, [
            {"id": "x", "category": "science", "prompt": "p", "expected_points": ["one", "two"], "must_cite": [], "forbidden_claims": []},
            {"id": "y", "category": "diagnostic", "prompt": "q", "expected_points": ["one"], "must_cite": [], "forbidden_claims": []},
        ])
        write_jsonl(base_raw, [{"id": "x", "response": "base x"}, {"id": "y", "response": "base y"}])
        write_jsonl(rag_raw, [{"id": "x", "response": "rag x"}, {"id": "y", "response": "rag y"}])
        manifest = prepare(eval_path, base_raw, rag_raw, packet, mapping)
        assert len(manifest["rows"]) == 2
        rows = load_jsonl(packet)
        for row in rows:
            row["reviewed_by"] = "fixture-reviewer"
            row["point_scores_a"] = [1] * len(row["expected_points"])
            row["point_scores_b"] = [0] * len(row["expected_points"])
        write_jsonl(packet, rows)
        base_out, rag_out = root / "base-reviewed.jsonl", root / "rag-reviewed.jsonl"
        counts = unblind(packet, mapping, base_out, rag_out)
        assert counts == (2, 2)
        assert {row["id"] for row in load_jsonl(base_out)} == {"x", "y"}
        assert {row["id"] for row in load_jsonl(rag_out)} == {"x", "y"}

        tampered = load_jsonl(packet)
        tampered[0]["response_a"] += " edited"
        write_jsonl(packet, tampered)
        try:
            unblind(packet, mapping, base_out, rag_out)
        except ValueError as exc:
            assert "modified" in str(exc)
        else:
            raise AssertionError("review response tampering was not rejected")
    assert arm_order("same-id") == arm_order("same-id")
    print("base-vs-RAG blind review self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--eval", type=pathlib.Path, default=DEFAULT_EVAL)
    parser.add_argument("--base-raw", type=pathlib.Path)
    parser.add_argument("--rag-raw", type=pathlib.Path)
    parser.add_argument("--packet", type=pathlib.Path)
    parser.add_argument("--map", dest="map_path", type=pathlib.Path)
    parser.add_argument("--unblind", action="store_true")
    parser.add_argument("--base-reviewed-out", type=pathlib.Path)
    parser.add_argument("--rag-reviewed-out", type=pathlib.Path)
    args = parser.parse_args()
    if args.self_test:
        self_test(); return 0
    try:
        if args.unblind:
            required = (args.packet, args.map_path, args.base_reviewed_out, args.rag_reviewed_out)
            if any(value is None for value in required):
                parser.error("--unblind requires --packet, --map, --base-reviewed-out, and --rag-reviewed-out")
            base_n, rag_n = unblind(args.packet, args.map_path, args.base_reviewed_out, args.rag_reviewed_out)
            print(f"unblinded reviewed predictions: base={base_n} rag={rag_n}")
        else:
            required = (args.base_raw, args.rag_raw, args.packet, args.map_path)
            if any(value is None for value in required):
                parser.error("preparation requires --base-raw, --rag-raw, --packet, and --map")
            mapping = prepare(args.eval, args.base_raw, args.rag_raw, args.packet, args.map_path)
            print(json.dumps({"status": "blind_review_packet_ready", "rows": len(mapping["rows"]), "review_packet_sha256": mapping["review_packet_sha256"]}, sort_keys=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"base-vs-RAG blind review: FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
