#!/usr/bin/env python3
import argparse
import hashlib
import json
import pathlib
import re
import sys
from urllib.parse import urlsplit, urlunsplit

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def fail(message: str) -> None:
    raise ValueError(message)


def canonical_source_identity(value: str) -> str:
    """Canonicalize DOI/URL identities for validation without rewriting stored citation bytes."""
    raw = (value or "").strip()
    if not raw:
        return ""

    lowered = raw.lower()
    if lowered.startswith("url:"):
        return canonical_source_identity(raw[4:].strip())
    if lowered.startswith("doi:"):
        payload = raw[4:].strip()
        if not payload:
            return ""
        if payload.lower().startswith(("http://", "https://")):
            return canonical_source_identity(payload)
        return f"doi:{payload.lower()}"
    if DOI_RE.fullmatch(raw):
        return f"doi:{raw.lower()}"

    parsed = urlsplit(raw)
    if parsed.scheme.lower() in {"http", "https"} and parsed.netloc:
        host = (parsed.hostname or "").lower()
        path = parsed.path or ""
        if host in {"doi.org", "www.doi.org", "dx.doi.org"}:
            payload = path.lstrip("/")
            return f"doi:{payload.lower()}" if payload else ""
        netloc = host
        if parsed.port:
            netloc = f"{host}:{parsed.port}"
        normalized_path = path.rstrip("/") or "/"
        return urlunsplit((parsed.scheme.lower(), netloc, normalized_path, parsed.query, ""))
    return raw


def canonical_sources(values) -> set[str]:
    return {
        identity
        for value in values
        for identity in [canonical_source_identity(str(value))]
        if identity
    }


def metadata_source_identities(metadata: dict) -> set[str]:
    identities = set()
    doi = metadata.get("doi")
    url = metadata.get("url")
    if doi:
        identities.add(canonical_source_identity(f"doi:{doi}"))
    if url:
        identities.add(canonical_source_identity(f"url:{url}"))
    identities.update(canonical_sources(metadata.get("component_sources") or []))
    return {identity for identity in identities if identity}


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


def validate_record_provenance(record: dict) -> None:
    record_id = record["id"]
    must_cite = record.get("must_cite") or []
    cited_identities = canonical_sources(must_cite)
    if len(cited_identities) != len(must_cite):
        fail(f"{record_id}: must_cite contains duplicate canonical source identities")

    source_metadata = record["source_metadata"]
    metadata_identities = metadata_source_identities(source_metadata)
    if not metadata_identities:
        fail(f"{record_id}: source_metadata must expose DOI/URL or component_sources provenance")
    if not metadata_identities.issubset(cited_identities):
        extra = sorted(metadata_identities - cited_identities)
        fail(f"{record_id}: source_metadata provenance is not bound to must_cite: {', '.join(extra)}")
    if not cited_identities.issubset(metadata_identities):
        missing = sorted(cited_identities - metadata_identities)
        fail(f"{record_id}: must_cite sources are missing from source_metadata provenance: {', '.join(missing)}")

    bindings = record.get("claim_source_bindings")
    if bindings is None:
        return
    expected_points = record.get("expected_points") or []
    if not isinstance(bindings, list) or len(bindings) != len(expected_points):
        fail(f"{record_id}: claim_source_bindings must contain exactly one binding per expected point")
    for index, binding in enumerate(bindings, 1):
        if not isinstance(binding, dict):
            fail(f"{record_id}: claim_source_bindings[{index}] must be an object")
        citations = binding.get("citations")
        if not isinstance(citations, list) or not citations:
            fail(f"{record_id}: claim_source_bindings[{index}].citations must be non-empty")
        unknown = canonical_sources(citations) - cited_identities
        if unknown:
            fail(f"{record_id}: claim_source_bindings[{index}] cites sources outside must_cite: {', '.join(sorted(unknown))}")


def self_test() -> None:
    assert canonical_source_identity("doi:10.1234/ABC") == "doi:10.1234/abc"
    assert canonical_source_identity("https://doi.org/10.1234/ABC") == "doi:10.1234/abc"
    assert canonical_source_identity("url:https://EXAMPLE.org/path/") == "https://example.org/path"

    direct = {
        "id": "self-test-direct",
        "expected_points": ["point"],
        "must_cite": ["doi:10.1234/abc"],
        "source_metadata": {"source_id": "source", "doi": "10.1234/ABC"},
    }
    validate_record_provenance(direct)

    composite = {
        "id": "self-test-composite",
        "expected_points": ["point"],
        "must_cite": ["doi:10.1234/abc", "doi:10.5678/def"],
        "source_metadata": {
            "source_id": "composite",
            "component_sources": ["https://doi.org/10.1234/ABC", "doi:10.5678/DEF"],
        },
    }
    validate_record_provenance(composite)

    bad = {
        "id": "self-test-bad",
        "expected_points": ["point"],
        "must_cite": ["doi:10.1234/abc"],
        "source_metadata": {"source_id": "source", "doi": "10.9999/wrong"},
    }
    try:
        validate_record_provenance(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("mismatched source metadata must fail provenance binding")


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
        validate_record_provenance(record)

    if len(ids) != len(set(ids)):
        fail("candidate dataset contains duplicate record ids")

    manifest_source_ids = {
        canonical_source_identity(f"doi:{source['doi']}")
        for source in manifest.get("sources", [])
        if source.get("doi")
    }
    manifest_source_ids.update(
        canonical_source_identity(f"url:{source['url']}")
        for source in manifest.get("sources", [])
        if source.get("url")
    )
    manifest_source_ids.discard("")
    cited_ids = {identity for record in records for identity in canonical_sources(record.get("must_cite", []))}
    missing = sorted(cited_ids - manifest_source_ids)
    if missing:
        fail(f"manifest is missing cited canonical sources: {', '.join(missing)}")

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
        self_test()
        for value in args.manifest:
            validate_manifest(pathlib.Path(value), repo_root)
    except (OSError, ValueError, json.JSONDecodeError, AssertionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
