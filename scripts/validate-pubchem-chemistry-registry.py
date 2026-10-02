#!/usr/bin/env python3
"""Validate the canonical PubChem chemistry registry before ingestion."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse

PATH = Path("dataset/sources/pubchem_chemistry_registry_v1.json")

def validate(data: dict) -> list[str]:
    errors: list[str] = []
    policy = data.get("policy") or {}
    if policy.get("rag_first") is not True:
        errors.append("registry must preserve rag_first=true")
    if policy.get("weight_training_default") is not False:
        errors.append("weight_training_default must be false")
    if policy.get("heldout_default") is not False:
        errors.append("heldout_default must be false")
    provider = data.get("provider") or {}
    required_provider = {
        "source_id", "organization", "title", "source_type", "canonical_url",
        "api_base", "evidence_tier", "rag_eligible", "weight_training_eligible",
        "heldout_eligible", "rights_status",
    }
    missing = sorted(required_provider - set(provider))
    if missing:
        errors.append("provider missing: " + ", ".join(missing))
    else:
        for key in ("canonical_url", "api_base"):
            parsed = urlparse(str(provider[key]))
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"provider.{key} must be absolute HTTPS")
        if provider["rag_eligible"] is not True:
            errors.append("provider must be RAG-eligible")
        if provider["weight_training_eligible"] is not False:
            errors.append("provider cannot enter weights before review")
        if provider["heldout_eligible"] is not False:
            errors.append("provider cannot enter heldout by default")
        if "review" not in str(provider["rights_status"]).lower():
            errors.append("provider rights_status must explicitly require review")

    compounds = data.get("seed_compounds")
    if not isinstance(compounds, list) or not compounds:
        return errors + ["seed_compounds must be a non-empty list"]
    seen_cids: set[int] = set()
    seen_ids: set[str] = set()
    for i, compound in enumerate(compounds):
        required = {"compound_id", "cid", "preferred_name", "aliases", "class", "canonical_url"}
        missing = sorted(required - set(compound))
        if missing:
            errors.append(f"seed_compounds[{i}] missing: {', '.join(missing)}")
            continue
        cid = compound["cid"]
        if not isinstance(cid, int) or cid <= 0:
            errors.append(f"seed_compounds[{i}].cid must be a positive integer")
            continue
        expected_id = f"pubchem:{cid}"
        if compound["compound_id"] != expected_id:
            errors.append(f"CID {cid}: compound_id must be {expected_id}")
        if cid in seen_cids:
            errors.append(f"duplicate CID: {cid}")
        seen_cids.add(cid)
        sid = str(compound["compound_id"])
        if sid in seen_ids:
            errors.append(f"duplicate compound_id: {sid}")
        seen_ids.add(sid)
        expected_url = f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"
        if compound["canonical_url"] != expected_url:
            errors.append(f"CID {cid}: canonical_url must be {expected_url}")
        if not str(compound["preferred_name"]).strip():
            errors.append(f"CID {cid}: preferred_name must not be empty")
        if not isinstance(compound["aliases"], list):
            errors.append(f"CID {cid}: aliases must be a list")
        if not str(compound["class"]).strip():
            errors.append(f"CID {cid}: class must not be empty")
    return errors

def main() -> int:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"PubChem chemistry registry: PASS ({len(data['seed_compounds'])} seed compounds)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
