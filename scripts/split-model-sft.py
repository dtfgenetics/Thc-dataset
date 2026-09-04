#!/usr/bin/env python3
"""Build deterministic, source-component-safe Grow Doc model train/dev splits.

Both SFT and grounded-QA candidates participate in one provenance graph. Records
that share a reviewed profile, normalized source identifier, or normalized full
conversation are inseparable. Components are assigned atomically, preventing a
training lane from leaking the same source family or duplicated behavior into dev.

Dependency-free by design. This validates/materializes data only; no training run
or model checkpoint is implied.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS_BUILDER = ROOT / "scripts/build-model-corpus.py"
GQA_BUILDER = ROOT / "scripts/build-grounded-qa.py"
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v2.jsonl"
DEFAULT_OUT = ROOT / "model_tuning/generated/splits"
ALGORITHM_VERSION = "source-component-v1"
DEFAULT_SEED = 420
DEFAULT_DEV_FRACTION = 0.20


def load_module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def public_row(row: dict) -> dict:
    return {key: value for key, value in row.items() if key != "_split_lane"}


def canonical_jsonl(rows: list[dict]) -> bytes:
    ordered = sorted((public_row(row) for row in rows), key=lambda row: row["id"])
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in ordered)
    return text.encode("utf-8")


def conversation_fingerprint(row: dict, norm) -> str:
    pieces = []
    for message in row.get("messages") or []:
        role = (message.get("role") or "").strip().lower()
        pieces.append(f"{role}:{norm(message.get('content') or '')}")
    if not pieces:
        return ""
    return digest("\n".join(pieces).encode("utf-8"))


class DSU:
    def __init__(self, size: int):
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value: int) -> int:
        if self.parent[value] != value:
            self.parent[value] = self.find(self.parent[value])
        return self.parent[value]

    def union(self, left: int, right: int) -> None:
        a, b = self.find(left), self.find(right)
        if a == b:
            return
        if self.rank[a] < self.rank[b]:
            a, b = b, a
        self.parent[b] = a
        if self.rank[a] == self.rank[b]:
            self.rank[a] += 1


def validate_records(rows: list[dict], heldout_sources: set[str], norm) -> None:
    seen_ids = set()
    for row in rows:
        rid = row.get("id")
        if not rid or rid in seen_ids:
            raise ValueError(f"duplicate or missing model record id: {rid!r}")
        seen_ids.add(rid)
        if row.get("_split_lane") not in {"sft", "grounded_qa"}:
            raise ValueError(f"{rid}: split lane is missing or invalid")
        if not row.get("profile_id"):
            raise ValueError(f"{rid}: profile_id is required")
        source_ids = set(row.get("source_ids") or [])
        if not source_ids:
            raise ValueError(f"{rid}: source_ids are required")
        overlap = sorted(source_ids & heldout_sources)
        if overlap:
            raise ValueError(f"{rid}: held-out source leakage: {overlap}")
        if row.get("grounded") is not True or row.get("context_required") is not True:
            raise ValueError(f"{rid}: only grounded, context-required records may be split")
        if not conversation_fingerprint(row, norm):
            raise ValueError(f"{rid}: messages are required")


def make_components(rows: list[dict], norm) -> list[dict]:
    dsu = DSU(len(rows))
    first_for_key: dict[str, int] = {}
    for index, row in enumerate(rows):
        keys = [f"profile:{row['profile_id']}"]
        keys.extend(f"source:{sid}" for sid in sorted(set(row.get("source_ids") or [])))
        keys.append(f"conversation:{conversation_fingerprint(row, norm)}")
        for key in keys:
            previous = first_for_key.setdefault(key, index)
            if previous != index:
                dsu.union(index, previous)

    grouped: dict[int, list[dict]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[dsu.find(index)].append(row)

    components = []
    for group in grouped.values():
        ordered = sorted(group, key=lambda row: row["id"])
        identity = digest("|".join(row["id"] for row in ordered).encode("utf-8"))
        components.append(
            {
                "id": identity,
                "rows": ordered,
                "profiles": sorted({row["profile_id"] for row in ordered}),
                "sources": sorted({sid for row in ordered for sid in row.get("source_ids") or []}),
                "conversations": sorted({conversation_fingerprint(row, norm) for row in ordered}),
            }
        )
    return sorted(components, key=lambda component: component["id"])


def choose_dev_components(components: list[dict], target: int, seed: int) -> set[str]:
    if len(components) < 2:
        raise ValueError("fewer than two source-connected components; leak-safe train/dev split is impossible")
    ranked = sorted(
        components,
        key=lambda component: digest(f"{ALGORITHM_VERSION}|{seed}|{component['id']}".encode("utf-8")),
    )
    total = sum(len(component["rows"]) for component in ranked)
    reachable: dict[int, tuple[int, ...]] = {0: ()}
    for index, component in enumerate(ranked):
        size = len(component["rows"])
        updates = dict(reachable)
        for current, selection in reachable.items():
            count = current + size
            candidate = selection + (index,)
            prior = updates.get(count)
            if prior is None or candidate < prior:
                updates[count] = candidate
        reachable = updates
    valid = [(count, selection) for count, selection in reachable.items() if 0 < count < total]
    if not valid:
        raise ValueError("no non-empty leak-safe train/dev partition exists")
    count, selection = min(valid, key=lambda item: (abs(item[0] - target), item[0], item[1]))
    if not 0 < count < total:
        raise AssertionError("invalid dev subset selected")
    return {ranked[index]["id"] for index in selection}


def split_records(rows: list[dict], heldout_sources: set[str], norm, *, seed: int, dev_fraction: float) -> tuple[list[dict], list[dict], dict]:
    if not 0 < dev_fraction < 1:
        raise ValueError("dev_fraction must be between 0 and 1")
    validate_records(rows, heldout_sources, norm)
    components = make_components(rows, norm)
    target_dev = max(1, min(len(rows) - 1, round(len(rows) * dev_fraction)))
    dev_component_ids = choose_dev_components(components, target_dev, seed)

    train: list[dict] = []
    dev: list[dict] = []
    component_manifest = []
    for component in components:
        split = "dev" if component["id"] in dev_component_ids else "train"
        (dev if split == "dev" else train).extend(component["rows"])
        component_manifest.append(
            {
                "component_id": component["id"],
                "split": split,
                "records": len(component["rows"]),
                "profiles": len(component["profiles"]),
                "sources": len(component["sources"]),
                "sft_records": sum(row["_split_lane"] == "sft" for row in component["rows"]),
                "grounded_qa_records": sum(row["_split_lane"] == "grounded_qa" for row in component["rows"]),
            }
        )

    train = sorted(train, key=lambda row: row["id"])
    dev = sorted(dev, key=lambda row: row["id"])
    if not train or not dev:
        raise ValueError("train and dev must both be non-empty")

    def values(records: list[dict], key: str) -> set[str]:
        if key == "source":
            return {sid for row in records for sid in row.get("source_ids") or []}
        if key == "profile":
            return {row["profile_id"] for row in records}
        return {conversation_fingerprint(row, norm) for row in records}

    train_sources, dev_sources = values(train, "source"), values(dev, "source")
    train_profiles, dev_profiles = values(train, "profile"), values(dev, "profile")
    train_conversations, dev_conversations = values(train, "conversation"), values(dev, "conversation")
    if train_sources & dev_sources:
        raise ValueError(f"source leakage across train/dev: {sorted(train_sources & dev_sources)}")
    if train_profiles & dev_profiles:
        raise ValueError(f"profile leakage across train/dev: {sorted(train_profiles & dev_profiles)}")
    if train_conversations & dev_conversations:
        raise ValueError("normalized conversation leakage across train/dev")
    if (train_sources | dev_sources) & heldout_sources:
        raise ValueError("held-out source leakage into train/dev")

    manifest = {
        "schema_version": "grow-doc-model-split-v1",
        "algorithm": ALGORITHM_VERSION,
        "seed": seed,
        "requested_dev_fraction": dev_fraction,
        "target_dev_records": target_dev,
        "total_records": len(rows),
        "component_count": len(components),
        "largest_component_records": max(len(component["rows"]) for component in components),
        "train_records": len(train),
        "dev_records": len(dev),
        "actual_dev_fraction": round(len(dev) / len(rows), 6),
        "train_profiles": len(train_profiles),
        "dev_profiles": len(dev_profiles),
        "train_sources": len(train_sources),
        "dev_sources": len(dev_sources),
        "heldout_sources": len(heldout_sources),
        "train_tasks": dict(sorted(Counter(row.get("task") for row in train).items())),
        "dev_tasks": dict(sorted(Counter(row.get("task") for row in dev).items())),
        "components": component_manifest,
        "invariants": {
            "source_overlap": 0,
            "profile_overlap": 0,
            "normalized_conversation_overlap": 0,
            "heldout_source_overlap": 0,
            "components_atomic": True,
        },
    }
    return train, dev, manifest


def lane_rows(rows: list[dict], lane: str) -> list[dict]:
    return [public_row(row) for row in rows if row["_split_lane"] == lane]


def add_hashes(manifest: dict, train: list[dict], dev: list[dict]) -> dict:
    train_sft, dev_sft = lane_rows(train, "sft"), lane_rows(dev, "sft")
    train_gqa, dev_gqa = lane_rows(train, "grounded_qa"), lane_rows(dev, "grounded_qa")
    manifest.update(
        {
            "train_sft_records": len(train_sft),
            "dev_sft_records": len(dev_sft),
            "train_grounded_qa_records": len(train_gqa),
            "dev_grounded_qa_records": len(dev_gqa),
            "train_sft_sha256": digest(canonical_jsonl(train_sft)),
            "dev_sft_sha256": digest(canonical_jsonl(dev_sft)),
            "train_grounded_qa_sha256": digest(canonical_jsonl(train_gqa)),
            "dev_grounded_qa_sha256": digest(canonical_jsonl(dev_gqa)),
        }
    )
    if min(len(train_sft), len(dev_sft), len(train_gqa), len(dev_gqa)) <= 0:
        raise ValueError("both SFT and grounded-QA lanes must have non-empty train/dev partitions")
    return manifest


def materialize(out_dir: pathlib.Path, train: list[dict], dev: list[dict], manifest: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "train_sft_v1.jsonl": lane_rows(train, "sft"),
        "dev_sft_v1.jsonl": lane_rows(dev, "sft"),
        "train_grounded_qa_v1.jsonl": lane_rows(train, "grounded_qa"),
        "dev_grounded_qa_v1.jsonl": lane_rows(dev, "grounded_qa"),
    }
    for name, rows in outputs.items():
        (out_dir / name).write_bytes(canonical_jsonl(rows))
    (out_dir / "split_manifest_v1.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def self_test() -> None:
    def norm(text: str) -> str:
        return " ".join((text or "").lower().split())

    def row(rid: str, profile: str, sources: list[str], text: str, lane: str = "sft") -> dict:
        return {
            "id": rid,
            "profile_id": profile,
            "source_ids": sources,
            "task": "grounded_qa" if lane == "grounded_qa" else "grounded_diagnostic_reasoning",
            "grounded": True,
            "context_required": True,
            "_split_lane": lane,
            "messages": [
                {"role": "user", "content": text},
                {"role": "assistant", "content": f"answer {rid}"},
            ],
        }

    rows = [
        row("a1", "p1", ["doi:one"], "alpha"),
        row("a2", "p1", ["doi:one"], "beta", "grounded_qa"),
        row("b1", "p2", ["doi:one", "doi:two"], "gamma"),
        row("c1", "p3", ["doi:three"], "delta"),
        row("c2", "p3", ["doi:three"], "delta qa", "grounded_qa"),
        row("d1", "p4", ["doi:four"], "epsilon"),
        row("d2", "p4", ["doi:four"], "epsilon qa", "grounded_qa"),
    ]
    train, dev, manifest = split_records(rows, set(), norm, seed=420, dev_fraction=0.4)
    where = {item["id"]: "train" for item in train} | {item["id"]: "dev" for item in dev}
    assert where["a1"] == where["a2"] == where["b1"], "shared profile/source component was split"
    assert manifest["invariants"]["source_overlap"] == 0

    duplicate_rows = [
        row("x1", "x", ["doi:x"], "same"),
        row("y1", "y", ["doi:y"], "same"),
        row("z1", "z", ["doi:z"], "different"),
    ]
    duplicate_rows[1]["messages"] = [dict(message) for message in duplicate_rows[0]["messages"]]
    train, dev, _ = split_records(duplicate_rows, set(), norm, seed=1, dev_fraction=0.34)
    where = {item["id"]: "train" for item in train} | {item["id"]: "dev" for item in dev}
    assert where["x1"] == where["y1"], "duplicate conversation component was split"

    try:
        split_records([row("h1", "h", ["doi:held"], "held")], {"doi:held"}, norm, seed=1, dev_fraction=0.2)
    except ValueError as exc:
        assert "held-out source leakage" in str(exc)
    else:
        raise AssertionError("held-out source leakage was not rejected")
    print("model source-component split self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    parser.add_argument("--eval", type=pathlib.Path, default=DEFAULT_EVAL)
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--dev-fraction", type=float, default=DEFAULT_DEV_FRACTION)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0

    try:
        corpus = load_module(CORPUS_BUILDER, "grow_doc_build_model_corpus")
        gqa_builder = load_module(GQA_BUILDER, "grow_doc_build_grounded_qa")
        _, sft, _, corpus_stats = corpus.build(args.input, args.eval)
        grounded_qa, gqa_stats = gqa_builder.build(args.input, args.eval)
        combined = [dict(row, _split_lane="sft") for row in sft]
        combined.extend(dict(row, _split_lane="grounded_qa") for row in grounded_qa)
        heldout_sources = corpus.eval_source_ids(args.eval)
        train, dev, manifest = split_records(
            combined,
            heldout_sources,
            corpus.norm,
            seed=args.seed,
            dev_fraction=args.dev_fraction,
        )
        add_hashes(manifest, train, dev)
        manifest.update(
            {
                "input_sha256": corpus_stats["input_sha256"],
                "eval_sha256": corpus_stats["eval_sha256"],
                "source_sft_records": corpus_stats["sft_examples"],
                "source_grounded_qa_records": gqa_stats["grounded_qa_examples"],
                "source_corpus_policy": corpus_stats["policy"],
                "grounded_qa_policy": gqa_stats["policy"],
            }
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.check_only:
        materialize(args.out, train, dev, manifest)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
