#!/usr/bin/env python3
"""Collect and normalize PubChem compound identity/property records.

Default mode is deterministic/offline: provide --input with a saved PubChem
PUG REST property response. --fetch is explicit because external data changes.
"""
from __future__ import annotations
import argparse, hashlib, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path

PARSER_VERSION = "pubchem-pug-rest-v2.0.0"
PROPERTIES = "Title,MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,InChI,InChIKey,IUPACName"

def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def normalize(payload: dict, cid: int, *, retrieved_at: str, source_sha256: str) -> dict:
    rows = (((payload or {}).get("PropertyTable") or {}).get("Properties") or [])
    if len(rows) != 1:
        raise ValueError(f"expected exactly one property row for CID {cid}, got {len(rows)}")
    row = rows[0]
    if int(row.get("CID", 0)) != cid:
        raise ValueError(f"response CID {row.get('CID')} does not match requested CID {cid}")
    return {
        "schema_version": "grow-doc-pubchem-compound-normalized-v1",
        "parser_version": PARSER_VERSION,
        "compound_id": f"pubchem:{cid}",
        "provider": "PubChem",
        "provider_id": str(cid),
        "canonical_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
        "retrieved_at": retrieved_at,
        "source_sha256": source_sha256,
        "title": row.get("Title"),
        "iupac_name": row.get("IUPACName"),
        "molecular_formula": row.get("MolecularFormula"),
        "molecular_weight": row.get("MolecularWeight"),
        "canonical_smiles": row.get("ConnectivitySMILES") or row.get("CanonicalSMILES"),
        "isomeric_smiles": row.get("SMILES") or row.get("IsomericSMILES"),
        "inchi": row.get("InChI"),
        "inchikey": row.get("InChIKey"),
        "evidence_scope": "chemical_identity_and_database_reported_properties",
        "rag_eligible": True,
        "weight_training_eligible": False,
        "heldout_eligible": False,
    }

def normalize_synonyms(payload: dict, cid: int) -> list[str]:
    infos = (((payload or {}).get("InformationList") or {}).get("Information") or [])
    if len(infos) != 1 or int(infos[0].get("CID", 0)) != cid:
        raise ValueError(f"invalid synonym response for CID {cid}")
    return sorted({str(v).strip() for v in infos[0].get("Synonym", []) if str(v).strip()}, key=str.casefold)

def fetch_url(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"Accept":"application/json","User-Agent":"DTF-THC-Grow-Doc/2.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()

def fetch(cid: int) -> bytes:
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/{PROPERTIES}/JSON"
    req = urllib.request.Request(url, headers={"User-Agent": "DTF-THC-Grow-Doc/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()

def self_test() -> None:
    payload = {"PropertyTable":{"Properties":[{
        "CID":16078,"Title":"Tetrahydrocannabinol","MolecularFormula":"C21H30O2",
        "MolecularWeight":"314.5","ConnectivitySMILES":"CC","SMILES":"C[C@H]",
        "InChI":"InChI=1S/example","InChIKey":"EXAMPLE","IUPACName":"example"
    }]}}
    raw = json.dumps(payload, sort_keys=True).encode()
    out = normalize(payload, 16078, retrieved_at="2026-01-01T00:00:00Z", source_sha256=sha256(raw))
    assert out["compound_id"] == "pubchem:16078"
    assert out["molecular_formula"] == "C21H30O2"
    assert out["weight_training_eligible"] is False
    assert out["parser_version"] == PARSER_VERSION
    syn = normalize_synonyms({"InformationList":{"Information":[{"CID":16078,"Synonym":["THC","delta9-THC","THC"]}]}},16078)
    assert syn == ["delta9-THC","THC"]
    try:
        normalize(payload, 644019, retrieved_at="x", source_sha256="y")
        raise AssertionError("CID mismatch was not rejected")
    except ValueError:
        pass
    print("PubChem collector self-test: PASS")

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cid", type=int)
    p.add_argument("--input", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test(); return 0
    if not args.cid or args.cid <= 0:
        p.error("--cid must be a positive integer")
    if bool(args.input) == bool(args.fetch):
        p.error("choose exactly one of --input or --fetch")
    raw = fetch(args.cid) if args.fetch else args.input.read_bytes()
    payload = json.loads(raw)
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    out = normalize(payload, args.cid, retrieved_at=retrieved_at, source_sha256=sha256(raw))
    encoded = (json.dumps(out, indent=2, sort_keys=True) + "\\n").encode()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    else:
        print(encoded.decode(), end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
