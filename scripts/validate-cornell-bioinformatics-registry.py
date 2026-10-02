#!/usr/bin/env python3
"""Validate external bioinformatics source registries before Grow Doc ingestion."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse

PATH = Path("dataset/sources/cornell_bioinformatics_registry_v1.json")
REQUIRED = {
    "source_id", "organization", "title", "source_type", "canonical_url",
    "retrieval_topics", "evidence_tier", "rag_eligible",
    "weight_training_eligible", "heldout_eligible", "rights_status",
}

def validate(data: dict) -> list[str]:
    errors: list[str] = []
    policy = data.get("policy") or {}
    if policy.get("rag_first") is not True:
        errors.append("registry must preserve rag_first=true")
    if policy.get("weight_training_default") is not False:
        errors.append("weight_training_default must be false")
    if policy.get("heldout_default") is not False:
        errors.append("heldout_default must be false")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        return errors + ["sources must be a non-empty list"]
    seen: set[str] = set()
    for i, source in enumerate(sources):
        missing = sorted(REQUIRED - set(source))
        if missing:
            errors.append(f"sources[{i}] missing: {', '.join(missing)}")
            continue
        sid = str(source["source_id"]).strip()
        if not sid or sid in seen:
            errors.append(f"sources[{i}] source_id is empty or duplicate: {sid!r}")
        seen.add(sid)
        parsed = urlparse(str(source["canonical_url"]))
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"{sid}: canonical_url must be absolute HTTPS")
        if source["rag_eligible"] is not True:
            errors.append(f"{sid}: initial registry sources must be RAG-eligible")
        if source["weight_training_eligible"] is not False:
            errors.append(f"{sid}: external source cannot enter weights before review")
        if source["heldout_eligible"] is not False:
            errors.append(f"{sid}: ingestion source cannot enter heldout by default")
        if not source["retrieval_topics"]:
            errors.append(f"{sid}: retrieval_topics must not be empty")
        if "review" not in str(source["rights_status"]).lower():
            errors.append(f"{sid}: rights_status must explicitly require review")
    return errors

def main() -> int:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Cornell bioinformatics source registry: PASS ({len(data['sources'])} sources)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
