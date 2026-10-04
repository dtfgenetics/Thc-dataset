#!/usr/bin/env python3
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
reg=json.loads((ROOT/"dataset/registry/formula_registry_v1.json").read_text())
assert reg["schema_version"]=="thc-formula-registry-v1"
ids=[x["formula_id"] for x in reg["formulas"]]
assert len(ids)==len(set(ids)) and ids
for f in reg["formulas"]:
    assert f["source_ids"] and f["test_vectors"] and f["consumers"]
    for v in f["test_vectors"]:
        i=v["inputs"]
        if f["formula_id"]=="FORM-DLI-PPFD-PHOTOPERIOD":
            actual=i["PPFD_umol_m2_s"]*i["photoperiod_hours"]*3600/1_000_000
        elif f["formula_id"]=="FORM-TDS-FROM-EC-FACTOR":
            actual=i["EC_mS_cm"]*i["factor_ppm_per_mS_cm"]
        else:
            raise AssertionError("unvalidated formula "+f["formula_id"])
        assert math.isclose(actual,v["expected"],abs_tol=v["tolerance"],rel_tol=0), (f["formula_id"],actual,v)
obs=json.loads((ROOT/"dataset/schema/scientific-observation.schema.json").read_text())
required=set(obs["required"])
assert {"observation_id","subject","observed_property","method","measurement","provenance","review_state"} <= required
coverage=json.loads((ROOT/"dataset/coverage/product_data_coverage_v1.json").read_text())
products={x["product"] for x in coverage["domains"]}
assert {"GrowLens","Grow Doc","Tools","Plant Atlas","Terpene Atlas"} <= products
print(f"scientific data platform seed: PASS ({len(ids)} formulas; {len(products)} consumers)")
