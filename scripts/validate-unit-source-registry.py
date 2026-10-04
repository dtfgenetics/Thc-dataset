#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
u=json.loads((ROOT/"dataset/registry/unit_registry_v1.json").read_text())
s=json.loads((ROOT/"dataset/registry/data_platform_source_registry_v1.json").read_text())
assert u["upstream"]["license"]=="CC BY 4.0"
ids=[x["unit_id"] for x in u["units"]]
assert len(ids)==len(set(ids))
for x in u["units"]:
    assert x["qudt_iri"].startswith("http://qudt.org/vocab/unit/")
assert "ppm" not in ids
source_ids={x["source_id"] for x in s["sources"]}
formula=json.loads((ROOT/"dataset/registry/formula_registry_v1.json").read_text())
for f in formula["formulas"]:
    assert set(f["source_ids"]) <= source_ids
print(f"unit/source registry: PASS ({len(ids)} curated units; {len(source_ids)} sources)")
