#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import tarfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bulk_acquisition" / "phase3_ds090"
WORK = ROOT / "bulk_acquisition" / "work_ds090_phase3"
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)

RELEASE_TAG = "bulk-acquisition-phase1-2026-08-14"
ARCHIVE_NAME = "DS-090_hemp-water-stress_pinned-86cec1c.tar.gz"
PINNED_COMMIT = "86cec1c30494c23c1d9b724ceb1a3aec68709250"


def run(args: list[str], cwd: Path | None = None) -> str:
    p = subprocess.run(args, cwd=cwd, text=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.stdout.strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash64(path: Path) -> int:
    with Image.open(path) as im:
        im = im.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        px = list(im.getdata())
    bits = 0
    for y in range(8):
        row = px[y * 9:(y + 1) * 9]
        for x in range(8):
            bits = (bits << 1) | int(row[x] > row[x + 1])
    return bits


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def parse_plant_id(name: str, rel: str) -> str:
    m = re.search(r"(?:^|_)(C[1-5])(?:_|\.)", name, flags=re.I)
    if m:
        return m.group(1).upper()
    parts = rel.split("/")
    if len(parts) > 1 and parts[0] == "Hemp_growth" and re.fullmatch(r"C[1-5]", parts[1], flags=re.I):
        return parts[1].upper()
    return "UNKNOWN"


def source_class(rel: str) -> str:
    p = rel.split("/")
    if rel.startswith("Hemp_growth/"):
        return "temporal-growth"
    if len(p) >= 4 and p[0] == "Hemp_water_stress" and p[1] in {"train", "test"}:
        return p[2]
    return ""


def source_split(rel: str) -> str:
    if rel.startswith("Hemp_water_stress/train/"):
        return "publisher-train"
    if rel.startswith("Hemp_water_stress/test/"):
        return "publisher-test"
    return "growth-series"


def group_id(plant: str) -> str:
    return f"DS090-{plant}" if plant != "UNKNOWN" else "DS090-UNKNOWN"


class UF:
    def __init__(self, n: int):
        self.p = list(range(n))
    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x
    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def split_score(groups: dict[str, dict], train: set[str], val: set[str], test: set[str]) -> float:
    classes = sorted({c for g in groups.values() for c in g["stressClasses"]})
    total = Counter()
    for g in groups.values():
        total.update(g["stressClasses"])
    total_n = sum(total.values()) or 1
    global_dist = {c: total[c] / total_n for c in classes}

    def dist(ids: set[str]) -> tuple[dict[str, float], int]:
        cc = Counter()
        for gid in ids:
            cc.update(groups[gid]["stressClasses"])
        n = sum(cc.values())
        if n == 0:
            return {c: 0.0 for c in classes}, 0
        return {c: cc[c] / n for c in classes}, n

    penalty = 0.0
    for ids, target_weight in [(train, 0.6), (val, 0.2), (test, 0.2)]:
        d, n = dist(ids)
        if n == 0:
            penalty += 1000.0
            continue
        penalty += sum(abs(d[c] - global_dist[c]) for c in classes)
        penalty += abs((n / total_n) - target_weight) * 0.5
    return penalty


def choose_split(groups: dict[str, dict]) -> dict:
    eligible = sorted(g for g in groups if g != "DS090-UNKNOWN" and groups[g]["imageCount"] > 0)
    if len(eligible) < 3:
        return {"status": "insufficient-groups", "groups": eligible}
    best = None
    # One group locked-eval and one group validation; remaining groups train.
    for test_gid in eligible:
        for val_gid in eligible:
            if val_gid == test_gid:
                continue
            test = {test_gid}
            val = {val_gid}
            train = set(eligible) - test - val
            if not train:
                continue
            score = split_score(groups, train, val, test)
            cand = (score, sorted(train), sorted(val), sorted(test))
            if best is None or cand < best:
                best = cand
    assert best is not None
    return {
        "status": "candidate-only-human-review-required",
        "method": "exhaustive plant-group assignment minimizing water-stress class-distribution divergence; one plant group validation, one plant group locked evaluation, remaining plant groups training",
        "score": best[0],
        "trainGroups": best[1],
        "validationGroups": best[2],
        "lockedEvaluationGroups": best[3],
        "warning": "This is a leakage-safe candidate assignment, not a released benchmark. Human review and cross-dataset duplicate checks are still required before lock."
    }


def main() -> int:
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.rmtree(WORK, ignore_errors=True)
    OUT.mkdir(parents=True)
    WORK.mkdir(parents=True)

    archive = WORK / ARCHIVE_NAME
    run(["gh", "release", "download", RELEASE_TAG, "--repo", "dtfgenetics/Thc-dataset", "--pattern", ARCHIVE_NAME, "--dir", str(WORK)])
    if not archive.exists():
        raise RuntimeError(f"Release asset {ARCHIVE_NAME} not downloaded")
    archive_sha = sha256(archive)

    extracted = WORK / "extracted"
    extracted.mkdir()
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(extracted)

    images = sorted(p for p in extracted.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if len(images) != 1252:
        raise RuntimeError(f"Expected 1252 images from phase-1 truth state, found {len(images)}")

    rows = []
    sha_buckets: dict[str, list[int]] = defaultdict(list)
    group_stats: dict[str, dict] = defaultdict(lambda: {
        "imageCount": 0,
        "growthFrames": 0,
        "waterStressFrames": 0,
        "publisherSplits": Counter(),
        "stressClasses": Counter(),
    })

    for idx, p in enumerate(images):
        rel = p.relative_to(extracted).as_posix()
        plant = parse_plant_id(p.name, rel)
        gid = group_id(plant)
        cls = source_class(rel)
        pub_split = source_split(rel)
        s256 = sha256(p)
        dh = dhash64(p)
        role = "water-stress" if rel.startswith("Hemp_water_stress/") else "growth-series"
        row = {
            "assetIndex": idx,
            "relativePath": rel,
            "filename": p.name,
            "sizeBytes": p.stat().st_size,
            "sha256": s256,
            "dhash64": f"{dh:016x}",
            "plantId": plant,
            "sourceGroupId": gid,
            "sourceRole": role,
            "sourceClass": cls,
            "publisherSplit": pub_split,
        }
        rows.append(row)
        sha_buckets[s256].append(idx)
        st = group_stats[gid]
        st["imageCount"] += 1
        st["publisherSplits"][pub_split] += 1
        if role == "growth-series":
            st["growthFrames"] += 1
        else:
            st["waterStressFrames"] += 1
            st["stressClasses"][cls] += 1

    # Exact duplicate groups.
    exact_groups = [idxs for idxs in sha_buckets.values() if len(idxs) > 1]

    # Perceptual near-duplicate components. Compare all 1,252 images; this is ~783k comparisons.
    hashes = [int(r["dhash64"], 16) for r in rows]
    uf = UF(len(rows))
    cross_group_edges = []
    near_edge_count = 0
    threshold = 4
    for i in range(len(rows)):
        hi = hashes[i]
        gi = rows[i]["sourceGroupId"]
        for j in range(i + 1, len(rows)):
            d = hamming(hi, hashes[j])
            if d <= threshold:
                near_edge_count += 1
                uf.union(i, j)
                gj = rows[j]["sourceGroupId"]
                if gi != gj:
                    cross_group_edges.append({
                        "a": rows[i]["relativePath"],
                        "b": rows[j]["relativePath"],
                        "groupA": gi,
                        "groupB": gj,
                        "hamming": d,
                    })

    comps: dict[int, list[int]] = defaultdict(list)
    for i in range(len(rows)):
        comps[uf.find(i)].append(i)
    near_components = [members for members in comps.values() if len(members) > 1]

    # Publisher split leakage by plant identity.
    publisher_leakage = []
    for gid, st in sorted(group_stats.items()):
        ps = st["publisherSplits"]
        if ps.get("publisher-train", 0) and ps.get("publisher-test", 0):
            publisher_leakage.append({
                "sourceGroupId": gid,
                "publisherTrainFrames": ps["publisher-train"],
                "publisherTestFrames": ps["publisher-test"],
                "finding": "same plant/source group appears in both publisher train and publisher test"
            })

    group_json = {}
    for gid, st in sorted(group_stats.items()):
        group_json[gid] = {
            "imageCount": st["imageCount"],
            "growthFrames": st["growthFrames"],
            "waterStressFrames": st["waterStressFrames"],
            "publisherSplits": dict(st["publisherSplits"]),
            "stressClasses": dict(st["stressClasses"]),
        }

    candidate = choose_split(group_json)

    with (OUT / "DS-090_dedup_inventory.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    duplicate_payload = {
        "datasetId": "DS-090",
        "dhashAlgorithm": "64-bit horizontal difference hash on 9x8 grayscale LANCZOS resize",
        "nearDuplicateThresholdHamming": threshold,
        "exactDuplicateGroupCount": len(exact_groups),
        "exactDuplicateGroups": [[rows[i]["relativePath"] for i in g] for g in exact_groups],
        "nearDuplicateEdgeCount": near_edge_count,
        "nearDuplicateComponentCount": len(near_components),
        "crossSourceGroupNearDuplicateEdgeCount": len(cross_group_edges),
        "crossSourceGroupNearDuplicateEdges": cross_group_edges,
        "rule": "Near-duplicate flags are review candidates, not automatic deletions. Temporal neighbors within one plant group may be biologically valid serial observations."
    }
    (OUT / "DS-090_duplicate_groups.json").write_text(json.dumps(duplicate_payload, indent=2), encoding="utf-8")
    (OUT / "DS-090_group_summary.json").write_text(json.dumps({
        "datasetId": "DS-090",
        "sourceArchiveSha256": archive_sha,
        "imageCount": len(rows),
        "groups": group_json,
        "publisherSplitLeakage": publisher_leakage,
        "guardrail": "All images and derivatives sharing a plant/sourceGroupId must remain in exactly one project split."
    }, indent=2), encoding="utf-8")
    (OUT / "DS-090_candidate_split.json").write_text(json.dumps(candidate, indent=2), encoding="utf-8")

    manifest = {
        "schemaVersion": "1.0",
        "phase": "ds090-dedup-grouping-phase3",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "datasetId": "DS-090",
        "sourceReleaseTag": RELEASE_TAG,
        "sourceArchive": ARCHIVE_NAME,
        "sourceArchiveSha256": archive_sha,
        "pinnedUpstreamCommit": PINNED_COMMIT,
        "imageCount": len(rows),
        "exactDuplicateGroupCount": len(exact_groups),
        "nearDuplicateComponentCount": len(near_components),
        "crossSourceGroupNearDuplicateEdgeCount": len(cross_group_edges),
        "publisherSplitLeakageGroupCount": len(publisher_leakage),
        "candidateSplitStatus": candidate.get("status"),
        "truthRule": "No split is considered locked until group-level assignment, cross-dataset duplicate review, and human QA are complete."
    }
    (OUT / "phase3-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    summary = [
        "# DS-090 Phase 3 — Deduplication and leakage-safe grouping",
        "",
        f"Images audited: **{len(rows)}**",
        f"Exact duplicate groups: **{len(exact_groups)}**",
        f"Perceptual near-duplicate components (dHash ≤ {threshold}): **{len(near_components)}**",
        f"Cross-source-group near-duplicate edges: **{len(cross_group_edges)}**",
        f"Publisher train/test plant-group leakage findings: **{len(publisher_leakage)}**",
        "",
        "The publisher train/test assignment remains source metadata only. The generated split is candidate-only until human QA and cross-dataset duplicate checks are complete.",
    ]
    (OUT / "phase3-summary.md").write_text("\n".join(summary), encoding="utf-8")

    checks = []
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name != "phase3-checksums.sha256":
            checks.append(f"{sha256(p)}  {p.name}")
    (OUT / "phase3-checksums.sha256").write_text("\n".join(checks) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
