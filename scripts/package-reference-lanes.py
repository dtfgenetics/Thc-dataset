#!/usr/bin/env python3
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "images" / "reference" / "manifest.json"
OUT = ROOT / "build" / "reference-lanes"

LANES = {
    "01_NUTRIENT_AND_ROOTZONE": "Cannabis-confirmed nutrient, fertility, salinity and root-zone reference evidence",
    "02_PESTS_AND_ARTHROPODS": "Cannabis-confirmed arthropod/pest reference evidence",
    "03_PATHOGENS_AND_DISEASE": "Cannabis-confirmed fungal, oomycete, bacterial and root/crown disease reference evidence",
    "04_VIRUS_VIROID_MOLECULAR": "Cannabis-confirmed virus/viroid references with molecular-confirmation ceilings",
    "05_SEX_REPRODUCTIVE_MORPHOLOGY": "Cannabis reproductive sex/intersex/flower morphology reference evidence",
    "06_HEALTHY_DEVELOPMENTAL_HARD_NEGATIVES": "Healthy, normal, genetic and developmental morphology hard negatives",
    "07_ABIOTIC_ENVIRONMENTAL_STRESS": "Cannabis abiotic/light/water/temperature/chemical-stress reference evidence",
    "EXPERT_ITEM_GATED": "Rights-cleared organism-only or expert reference that is not Cannabis-host symptom ground truth",
    "CROSS_CROP_TRANSFER": "Non-Cannabis transfer evidence; never Cannabis causal ground truth",
}

NUTRIENT = (
    "nitrogen", "phosph", "potassium", "calcium", "magnesium", "sulfur", "iron", "zinc",
    "manganese", "boron", "copper", "nutrient", "salinity", "root-zone", "rootzone", "ammonium"
)
PEST = ("mite", "aphid", "thrip", "whitefly", "caterpillar", "earworm", "leafhopper", "lygus", "stink", "beetle", "gnat", "arthropod")
PATHOGEN = ("fusarium", "botrytis", "powdery", "mildew", "pythium", "septoria", "cercospora", "curvularia", "bipolaris", "rust", "sclerot", "diaporthe", "xanthomon", "damping", "rot", "mold", "pathogen")
VIRUS = ("hlvd", "viroid", "virus", "bctv", "curly-top", "curly top", "mosaic")
SEX = ("sex", "male", "female", "intersex", "hermaph", "flower-morph", "reproductive")
HEALTHY = ("healthy", "senescence", "varieg", "reveget", "foxtail", "fasciat", "polyploid", "development", "trichome", "maturity", "normal")
ABIOTIC = ("light", "heat", "cold", "drought", "waterlog", "underwater", "overwater", "wind", "edema", "phytotoxic", "herbicide", "mechanical", "vpd", "environment")


def text_blob(record):
    vals = [
        record.get("id", ""), record.get("issue_slug", ""), record.get("diagnostic_label", ""),
        record.get("caption", ""), record.get("host_context", ""), record.get("host_species", ""),
        record.get("stage", ""), record.get("source_article", "")
    ]
    return " ".join(str(v).lower() for v in vals)


def classify(record):
    blob = text_blob(record)
    host = str(record.get("host_context", "")).lower().strip()
    species = str(record.get("host_species", "")).lower().strip()

    # Cannabis/hemp identity is inferred from the complete provenance record, not only optional host fields.
    # This matters for explicit scientific candidates that predate host_context/host_species fields.
    cannabis_domain = any(term in blob for term in ("cannabis", "hemp"))

    if "cross-crop" in host:
        return "CROSS_CROP_TRANSFER"
    if host == "organism-only":
        return "EXPERT_ITEM_GATED"
    if not cannabis_domain:
        # Known non-Cannabis host records are transfer data; metadata-poor unknowns remain expert-gated.
        if host or species:
            return "CROSS_CROP_TRANSFER"
        return "EXPERT_ITEM_GATED"

    if any(k in blob for k in VIRUS):
        return "04_VIRUS_VIROID_MOLECULAR"
    if any(k in blob for k in SEX):
        return "05_SEX_REPRODUCTIVE_MORPHOLOGY"
    if any(k in blob for k in PATHOGEN):
        return "03_PATHOGENS_AND_DISEASE"
    if any(k in blob for k in PEST):
        return "02_PESTS_AND_ARTHROPODS"
    if any(k in blob for k in HEALTHY):
        return "06_HEALTHY_DEVELOPMENTAL_HARD_NEGATIVES"
    if any(k in blob for k in ABIOTIC):
        return "07_ABIOTIC_ENVIRONMENTAL_STRESS"
    if any(k in blob for k in NUTRIENT):
        return "01_NUTRIENT_AND_ROOTZONE"
    return "EXPERT_ITEM_GATED"


def main():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = data.get("records", [])
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    lane_records = {k: [] for k in LANES}
    missing = []

    for rec in records:
        lane = classify(rec)
        blob = text_blob(rec)
        if lane == "CROSS_CROP_TRANSFER" and any(term in blob for term in ("cannabis", "hemp")):
            raise SystemExit(f"Cannabis/hemp reference misrouted to cross-crop lane: {rec.get('id')}")

        src = ROOT / rec["repository_path"]
        if not src.exists():
            missing.append(rec["repository_path"])
            continue
        lane_dir = OUT / lane
        lane_dir.mkdir(parents=True, exist_ok=True)
        dst = lane_dir / src.name
        shutil.copy2(src, dst)
        routed = dict(rec)
        routed["storage_lane"] = lane
        routed["storage_policy"] = LANES[lane]
        routed["trainingEligible"] = False if rec.get("intended_use") == "reference-only" else bool(rec.get("trainingEligible", False))
        lane_records[lane].append(routed)

    if missing:
        raise SystemExit("Missing persisted reference files: " + ", ".join(missing))

    summary = {
        "schemaVersion": "1.1.0",
        "sourceManifest": str(MANIFEST.relative_to(ROOT)),
        "policy": "Storage routing does not promote reference-only media to training ground truth. Cannabis/hemp references are recognized from complete provenance text when legacy records lack explicit host fields. Item rights, panel review, source grouping and leakage-safe split assignment remain separate gates.",
        "lanes": {},
    }

    for lane, recs in lane_records.items():
        lane_dir = OUT / lane
        lane_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "lane": lane,
            "description": LANES[lane],
            "recordCount": len(recs),
            "records": recs,
        }
        (lane_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        summary["lanes"][lane] = {"recordCount": len(recs), "description": LANES[lane]}

    (OUT / "routing-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
