#!/usr/bin/env python3
"""Create deterministic Grow Doc train/dev SFT splits without provenance leakage.

The splitter rebuilds the canonical SFT corpus from reviewed profiles, then treats
records as connected when they share a profile, a normalized source identifier,
or normalized conversation content. Connected components are assigned atomically
to train or dev. This prevents row-level splitting from leaking the same scientific
source family or duplicated prompt/answer behavior across model-selection splits.

Dependency-free by design so the split contract can run in CI before any GPU stack
is installed. No training run is implied.
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
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v2.jsonl"
DEFAULT_OUT = ROOT / "model_tuning/generated/splits"
ALGORITHM_VERSION = "source-component-v1"
DEFAULT_SEED = 420
DEFAULT_DEV_FRACTION = 0.20


def load_builder():
    spec = importlib.util.spec_from_file_location("grow_doc_build_model_corpus", CORPUS_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load corpus builder: {CORPUS_BUILDER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_jsonl(rows: list[dict]) -> bytes:
    ordered = sorted(rows, key=lambda row: row["id"])
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in ordered)
    return text.encode("utf-8")


def normalized_conversation_fingerprint(item: dict, norm) -> str:
    pieces = []
    for message in item.get("messages") or []:
        role = (message.get("role") or "").strip().lower()
        content = norm(message.get("content") or "")
        pieces.append(f"{role}:{content}")
    return sha256_bytes("\n".join(pieces).encode("utf-8"))


class DSU:
    def __init__(self, size: int):
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        a, b = self.find(left), self.find(right)
        if a == b:
            return
        if self.rank[a] < self.rank[b]:
            a, b = b, a
        self.parent[b] = a
        if self.rank[a] == self.rank[b]:
            self.rank[a] += 1


def validate_sft_rows(rows: list[dict], heldout_sources: set[str], norm) -> None:
    ids = set()
    for row in rows:
        rid = row.get("id")
        if not rid or rid in ids:
            raise ValueError(f"duplicate or missing SFT id: {rid!r}")
        ids.add(rid)
        if not row.get("profile_id"):
            raise ValueError(f"{rid}: profile_id is required")
        source_ids = row.get("source_ids") or []
        if not source_ids:
            raise ValueError(f"{rid}: source_ids are required")
        overlap = sorted(set(source_ids) & heldout_sources)
        if overlap:
            raise ValueError(f"{rid}: held-out source leakage: {overlap}")
        if row.get("grounded") is not True or row.get("context_required") is not True:
            raise ValueError(f"{rid}: only grounded, context-required records may be split")
        if not normalized_conversation_fingerprint(row, norm):
            raise ValueError(f"{rid}: conversation fingerprint is empty")


def connected_components(rows: list[dict], norm) -> list[dict]:
    dsu = DSU(len(rows))
    first_for_key: dict[str, int] = {}

    for index, row in enumerate(rows):
        keys = [f"profile:{row['profile_id']}"]
        keys.extend(f"source:{source_id}" for source_id in sorted(set(row.get("source_ids") or [])))
        keys.append(f"conversation:{normalized_conversation_fingerprint(row, norm)}")
        for key in keys:
            previous = first_for_key.get(key)
            if previous is None:
                first_for_key[key] = index
            else:
                dsu.union(index, previous)

    groups: dict[int, list[dict]] = defaultdict(list)
    for index, row in enumerate(rows):
        groups[dsu.find(index)].append(row)

    components = []
    for group_rows in groups.values():
        ordered = sorted(group_rows, key=lambda row: row["id"])
        source_ids = sorted({sid for row in ordered for sid in row.get("source_ids") or []})
        profile_ids = sorted({row["profile_id"] for row in ordered})
        conversation_fingerprints = sorted({normalized_conversation_fingerprint(row, norm) for row in ordered})
        identity = sha256_bytes(("|".join(row["id"] for row in ordered)).encode("utf-8"))
        components.append(
            {
                "id": identity,
                "rows": ordered,
                "source_ids": source_ids,
                "profile_ids": profile_ids,
                "conversation_fingerprints": conversation_fingerprints,
            }
        )
    return sorted(components, key=lambda component: component["id"])


def choose_dev_components(components: list[dict], target: int, seed: int) -> set[str]:
    if len(components) < 2:
        raise ValueError("source-connected graph has fewer than two components; leak-safe train/dev split is impossible")

    ranked = sorted(
        components,
        key=lambda component: sha256_bytes(f"{ALGORITHM_VERSION}|{seed}|{component['id']}".encode("utf-8")),
    )
    total_records = sum(len(component["rows"]) for component in ranked)

    # Exact deterministic subset-sum over record counts. For each reachable count,
    # retain the lexicographically earliest component-index tuple. The final choice
    # minimizes distance from the requested dev size while forbidding empty splits.
    reachable: dict[int, tuple[int, ...]] = {0: ()}
    for index, component in enumerate(ranked):
        size = len(component["rows"])
        updates = dict(reachable)
        for current, selection in reachable.items():
            candidate_total = current + size
            candidate_selection = selection + (index,)
            prior = updates.get(candidate_total)
            if prior is None or candidate_selection < prior:
                updates[candidate_total] = candidate_selection
        reachable = updates

    valid = [(count, selection) for count, selection in reachable.items() if 0 < count < total_records]
    if not valid:
        raise ValueError("no non-empty leak-safe train/dev partition exists")
    count, selection = min(valid, key=lambda item: (abs(item[0] - target), item[0], item[1]))
    if count <= 0 or count >= total_records:
        raise AssertionError("invalid dev partition selected")
    return {ranked[index]["id"] for index in selection}


def split_rows(rows: list[dict], heldout_sources: set[str], norm, *, seed: int, dev_fraction: float) -> tuple[list[dict], list[dict], dict]:
    if not 0 < dev_fraction < 1:
        raise ValueError("dev_fraction must be between 0 and 1")
    validate_sft_rows(rows, heldout_sources, norm)
    components = connected_components(rows, norm)
    target_dev = max(1, min(len(rows) - 1, round(len(rows) * dev_fraction)))
    dev_component_ids = choose_dev_components(components, target_dev, seed)

    train: list[dict] = []
    dev: list[dict] = []
    component_manifest = []
    for component in components:
        split = "dev" if component["id"] in dev_component_ids else "train"
        destination = dev if split == "dev" else train
        destination.extend(component["rows"])
        component_manifest.append(
            {
                "component_id": component["id"],
                "split": split,
                "records": len(component["rows"]),
                "profiles": len(component["profile_ids"]),
                "sources": len(component["source_ids"]),
            }
        )

    train = sorted(train, key=lambda row: row["id"])
    dev = sorted(dev, key=lambda row: row["id"])
    if not train or not dev:
        raise ValueError("train/dev split must both be non-empty")

    train_sources = {sid for row in train for sid in row.get("source_ids") or []}
    dev_sources = {sid for row in dev for sid in row.get("source_ids") or []}
    train_profiles = {row["profile_id"] for row in train}
    dev_profiles = {row["profile_id"] for row in dev}
    train_conversations = {normalized_conversation_fingerprint(row, norm) for row in train}
    dev_conversations = {normalized_conversation_fingerprint(row, norm) for row in dev}

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
        "train_sha256": sha256_bytes(canonical_jsonl(train)),
        "dev_sha256": sha256_bytes(canonical_jsonl(dev)),
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


def materialize(out_dir: pathlib.Path, train: list[dict], dev: list[dict], manifest: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "train_v1.jsonl").write_bytes(canonical_jsonl(train))
    (out_dir / "dev_v1.jsonl").write_bytes(canonical_jsonl(dev))
    (out_dir / "split_manifest_v1.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def self_test() -> None:
    def norm(text: str) -> str:
        return " ".join((text or "").lower().split())

    def row(rid: str, profile: str, sources: list[str], text: str) -> dict:
        return {
            "id": rid,
            "profile_id": profile,
            "source_ids": sources,
            "task": "grounded_diagnostic_reasoning",
            "grounded": True,
            "context_required": True,
            "messages": [
                {"role": "user", "content": text},
                {"role": "assistant", "content": f"answer {rid}"},
            ],
        }

    rows = [
        row("a1", "p1", ["doi:one"], "alpha"),
        row("a2", "p1", ["doi:one"], "beta"),
        row("b1", "p2", ["doi:one", "doi:two"], "gamma"),
        row("c1", "p3", ["doi:three"], "delta"),
        row("d1", "p4", ["doi:four"], "epsilon"),
    ]
    train, dev, manifest = split_rows(rows, set(), norm, seed=420, dev_fraction=0.4)
    assert train and dev
    where = {item["id"]: "train" for item in train} | {item["id"]: "dev" for item in dev}
    assert where["a1"] == where["a2"] == where["b1"], "shared source/profile component was split"
    assert manifest["invariants"]["source_overlap"] == 0

    duplicate_message_rows = [
        row("x1", "x", ["doi:x"], "same prompt"),
        row("y1", "y", ["doi:y"], "same prompt"),
        row("z1", "z", ["doi:z"], "different prompt"),
    ]
    # Make the entire conversations identical for x/y to exercise the content edge.
    duplicate_message_rows[1]["messages"] = [dict(message) for message in duplicate_message_rows[0]["messages"]]
    duplicate_message_rows[1]["messages"][1]["content"] = duplicate_message_rows[0]["messages"][1]["content"]
    train, dev, _ = split_rows(duplicate_message_rows, set(), norm, seed=1, dev_fraction=0.34)
    where = {item["id"]: "train" for item in train} | {item["id"]: "dev" for item in dev}
    assert where["x1"] == where["y1"], "duplicate conversation component was split"

    try:
        split_rows([row("h1", "h", ["doi:held"], "held")], {"doi:held"}, norm, seed=1, dev_fraction=0.2)
    except ValueError as exc:
        assert "held-out source leakage" in str(exc)
    else:
        raise AssertionError("held-out source leakage was not rejected")

    print("model SFT source-component split self-test: PASS")


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
        builder = load_builder()
        _, sft, _, corpus_stats = builder.build(args.input, args.eval)
        heldout_sources = builder.eval_source_ids(args.eval)
        train, dev, manifest = split_rows(
            sft,
            heldout_sources,
            builder.norm,
            seed=args.seed,
            dev_fraction=args.dev_fraction,
        )
        manifest["input_sha256"] = corpus_stats["input_sha256"]
        manifest["eval_sha256"] = corpus_stats["eval_sha256"]
        manifest["source_sft_records"] = corpus_stats["sft_examples"]
        manifest["source_corpus_policy"] = corpus_stats["policy"]
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not args.check_only:
        materialize(args.out, train, dev, manifest)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
