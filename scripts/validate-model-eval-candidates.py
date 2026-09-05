#!/usr/bin/env python3
import argparse
import hashlib
import json
import pathlib
import sys


def fail(message: str) -> None:
    raise ValueError(message)


def load_jsonl(path: pathlib.Path):
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                records.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                fail(f"{path}:{lineno}: invalid JSON: {exc}")
    return records


def validate_manifest(manifest_path: pathlib.Path, repo_root: pathlib.Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "grow-doc-eval-candidate-manifest-v1":
        fail("unexpected candidate manifest schema_version")
    if manifest.get("status") != "candidate_only_not_promotion_eligible":
        fail("candidate dataset must remain non-promotion-eligible")

    policy = manifest.get("source_policy") or {}
    required_true = (
        "require_primary_or_peer_reviewed_source",
        "preserve_source_metadata",
        "require_human_review_before_heldout_admission",
        "forbid_training_use",
        "forbid_train_dev_overlap",
    )
    for key in required_true:
        if policy.get(key) is not True:
            fail(f"source_policy.{key} must be true")

    dataset_rel = manifest.get("dataset")
    if not isinstance(dataset_rel, str) or not dataset_rel:
        fail("manifest.dataset must be a repository-relative path")
    dataset_path = repo_root / dataset_rel
    if not dataset_path.is_file():
        fail(f"candidate dataset does not exist: {dataset_rel}")

    raw = dataset_path.read_bytes()
    expected_sha = manifest.get("content_sha256")
    actual_sha = hashlib.sha256(raw).hexdigest()
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        fail("manifest.content_sha256 must be a 64-character SHA-256")
    if expected_sha != actual_sha:
        fail(f"candidate dataset SHA-256 mismatch: expected {expected_sha}, got {actual_sha}")

    records = load_jsonl(dataset_path)
    if manifest.get("record_count") != len(records):
        fail(f"record_count mismatch: manifest={manifest.get('record_count')} actual={len(records)}")

    ids = []
    for index, record in enumerate(records, 1):
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            fail(f"record {index}: missing id")
        ids.append(record_id)
        if not record.get("prompt") or not record.get("expected_points"):
            fail(f"{record_id}: prompt and expected_points are required")
        must_cite = record.get("must_cite")
        if not isinstance(must_cite, list) or not must_cite:
            fail(f"{record_id}: must_cite must contain at least one source")
        source_metadata = record.get("source_metadata")
        if not isinstance(source_metadata, dict) or not source_metadata.get("source_id"):
            fail(f"{record_id}: source_metadata.source_id is required")
        if not source_metadata.get("review_state", "").startswith("candidate_verified_source"):
            fail(f"{record_id}: source metadata must retain candidate verification state")

    if len(ids) != len(set(ids)):
        fail("candidate dataset contains duplicate record ids")

    source_dois = {f"doi:{source['doi']}" for source in manifest.get("sources", []) if source.get("doi")}
    cited_dois = {citation for record in records for citation in record.get("must_cite", []) if citation.startswith("doi:")}
    missing = sorted(cited_dois - source_dois)
    if missing:
        fail(f"manifest is missing cited DOI sources: {', '.join(missing)}")

    requirements = set(manifest.get("admission_requirements", []))
    required_requirements = {
        "independent human factual review",
        "check semantic near-duplicates against heldout_v2 and training/dev corpora",
        "confirm no source-group leakage into training",
        "freeze content hash before benchmark promotion",
    }
    if not required_requirements.issubset(requirements):
        fail("candidate manifest is missing benchmark-admission safeguards")

    print(f"validated candidate eval dataset: {dataset_rel} ({len(records)} records, sha256={actual_sha})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Grow Doc held-out evaluation candidate manifests.")
    parser.add_argument("manifest", nargs="+", help="candidate manifest JSON files")
    args = parser.parse_args()
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    try:
        for value in args.manifest:
            validate_manifest(pathlib.Path(value), repo_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
