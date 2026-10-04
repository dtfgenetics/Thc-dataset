#!/usr/bin/env python3
import json, pathlib, sys
def validate(path):
    d=json.loads(pathlib.Path(path).read_text())
    s=d["source"]; m=d["metrics"]; records=d["records"]; quarantine=d["quarantine"]
    assert s["provider"]=="Crop Ontology" and s["retrieved_from_official_api"] is True
    assert s["endpoint"].startswith("https://cropontology.org/brapi/v1/")
    assert len(s["raw_sha256"])==64 and s["parser_version"]
    assert m["attempted"]==m["fetched"]
    assert m["normalized"]==m["published"]==len(records)
    assert m["quarantined"]==len(quarantine)
    assert m["fetched"]==m["published"]+m["deduped"]+m["quarantined"]
    keys=set()
    for r in records:
        assert r["upstream_id"] and r["name"] and r["source"]=="Crop Ontology"
        assert r["provenance"]["parser_version"]==s["parser_version"]
        k=(r["record_type"],r["upstream_id"]); assert k not in keys; keys.add(k)
if __name__=="__main__":
    for p in sys.argv[1:]: validate(p)
    print("crop ontology snapshot validation: ok")
