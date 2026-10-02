#!/usr/bin/env python3
"""End-to-end contract test: GRIN normalization -> identity graph -> BrAPI germplasm."""
from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
grin=load("grin","scripts/normalize-usda-grin-germplasm.py")
identity=load("identity","scripts/resolve-bioinformatics-identities.py")
brapi=load("brapi","scripts/export-brapi-germplasm.py")

def main():
    raw={"accession":"PI 999999","cultivar":"Contract Example","scientificName":"Cannabis sativa","source_url":"https://npgsweb.ars-grin.gov/","retrieved_at":"2026-10-02T00:00:00Z"}
    n=grin.normalize(raw)
    graph=identity.build([n])
    assert not graph["errors"]
    assert any(x["id"]=="grin_accession:PI 999999" for x in graph["nodes"])
    out=brapi.export([n])
    assert out[0]["germplasmDbId"]=="PI 999999"
    assert out[0]["germplasmName"]=="Contract Example"
    assert out[0]["externalReferences"][0]["referenceSource"]=="USDA-GRIN"
    assert n["weight_training_eligible"] is False\n    assert n["heldout_eligible"] is False\n    assert n["retrieved_at"]=="2026-10-02T00:00:00Z"\n    assert len(n["source_record_sha256"])==64
    print("GRIN -> identity -> BrAPI contract: PASS")
if __name__=="__main__": main()
