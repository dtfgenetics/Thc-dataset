# High-priority public reference image sources

This shortlist complements the repo's acquisition catalog and focuses on public, image-based scientific references that are relevant to cannabis/hemp plant health, nutrient stress, reproduction, water stress, and pathogen diagnostics.

## 1) Nutrient deficiency progression
- Title: Cannabis Single-Element Nutrient Deficiency Supplement
- URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC9920212/
- License: CC BY 4.0
- Why it matters: Strong whole-plant and symptom progression images for N, P, K, Ca, Mg, S, Fe, Mn deficiency. High value for building visual symptom references.
- Best usage: reference-only seed, evidence labels, model explanation support

## 2) Reproductive morphology
- Title: Female / Male / Hermaphrodite Floral Morphology Corpus
- URL: https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2020.00718/full
- License: CC BY 4.0
- Why it matters: Clear visual differences among female, male, and intersex flower structures.
- Best usage: morphological classification and anatomy-for-diagnosis references

## 3) Water stress and plant growth time series
- Title: Industrial Hemp Greenhouse Water-Stress & Growth Image Dataset
- URL: https://data.mendeley.com/datasets/3md2tbx74c/1
- License: CC BY 4.0
- Why it matters: Time-series RGB image dataset for healthy vs water-stressed growth. Helpful for temporal growth analysis and model robustness.
- Best usage: training seed and split-safe comparison set with grouped time-series handling

## 4) HLVd visual references
- Title: HLVd RT-PCR/RT-qPCR Validated Cannabis Visual Reference Corpus
- URL: https://www.mdpi.com/2223-7747/14/5/830
- License: CC BY 4.0
- Why it matters: Visual and molecular reference set for suspected hop latent viroid cases.
- Best usage: evidence-only reference, never visual-only confirmation

## 5) Pathogen and mold reference figures
- Title: Cannabis Pathogens and Molds — Controlled Inoculation & Visual Reference
- URL: https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2019.01120/full
- License: CC BY 4.0
- Why it matters: High-value reference figures for botrytis, powdery mildew, pythium, and fusarium-related symptoms.
- Best usage: plant disease differentiation and image comparison training

## 6) Broad disease and abiotic reference library
- Title: USU Hemp Pests, Diseases & Abiotic Expert Reference Library
- URL: https://extension.usu.edu/planthealth/ipm/notes_ag/faf-list-hemp
- License: source specific / per-image rights
- Why it matters: Useful extension library for broad visual comparison across stress categories.
- Best usage: reference-only; apply per-image rights review before inclusion in public training sets

## 7) Root disease and etiology references
- Title: Cannabis Pythium / Globisporangium / Fusarium Root-Rot Pathogenicity Reference
- URL: https://www.frontiersin.org/journals/agronomy/articles/10.3389/fagro.2021.706138/full
- License: CC BY 4.0
- Why it matters: Root disease visual references tied to pathogenicity.
- Best usage: suspected root-rot comparison and support for conservative diagnosis

## 8) Flower disease and inflorescence rot
- Title: Cannabis Fusarium Inflorescence Infection and Mycotoxin Reference
- URL: https://www.mdpi.com/2309-608X/11/7/528
- License: CC BY 4.0
- Why it matters: Good inflorescence-stage visual references for flower rot and differential diagnosis.
- Best usage: diseased floral structures, training seed, and annotation support

## Notes for acquisition
- Prefer public open-license sources and per-image rights review for extension and non-journal materials.
- For any image used in training, keep metadata: source URL, creator, license, issue label, view, stage/severity, confirmation level, and review status.
- Do not treat visual similarity as final confirmation for viroid, virus, or pathogen diagnosis; use the scientific source evidence and maintain conservative labels.
- On large time-series datasets, keep plant/time-group structure intact when creating train/validation/test splits to avoid leakage.

## Repo status
The repo already contains a richer reference catalog in:
- `dataset/catalog/reference-image-sources.json`

This markdown file is a human-readable shortlist for faster review while building the dataset and the evidence tool.
