# Grow Doc Bioinformatics Architecture v1

Status: implementation research baseline; no model training or genomic import implied.

## Goal
Build a provenance-preserving Cannabis/plant bioinformatics layer that can serve Grow Doc RAG, diagnostics, breeding records, Plant Atlas, and later reviewed model-training candidates without mixing volatile facts into weights or contaminating held-out evaluation.

## Standards contract
- Breeding/germplasm/phenotype/genotype interchange: BrAPI 2.1.
- Germplasm passport identity: USDA GRIN-Global + MCPD-compatible fields where available.
- Plant trait semantics: Crop Ontology identifiers; MIAPPE-compatible experiment metadata where available.
- Taxonomy: NCBI Taxonomy IDs plus provider accession IDs.
- Sequence identities: NCBI RefSeq/GenBank accessions with assembly version required.
- Variant storage/exchange: VCF/BCF for files; GA4GH VRS identifiers for normalized application-level variant identity.
- Alignments: SAM/BAM/CRAM; raw reads remain accession-first/on-demand.
- Source evidence: immutable source_id + canonical URL/accession + retrieval timestamp + content checksum + rights state.
- Model policy: factual/genomic records enter RAG first; weight-training and heldout admission require independent review.

## Canonical entity graph
source -> project -> accession/germplasm -> biological sample -> assembly/reference
-> sequence feature/gene -> variant/genotype -> phenotype/trait -> environment/treatment
-> observation -> pedigree/cross/seed lot -> claim -> citation.

Never join records solely by cultivar/strain display name. Prefer provider accession, BioSample, germplasmDbId, DOI, assembly accession, or other stable identifiers.

## Storage lanes
1. registry/ : manually reviewed source and software identities.
2. raw-manifests/ : remote object metadata, accession, checksum, retrieval timestamp; no automatic bulk sequence mirroring.
3. normalized/ : BrAPI/MIAPPE/VRS-compatible records.
4. reviewed/ : claim-level scientific review with scope and limitations.
5. rag/ : retrieval chunks/claims carrying source IDs and citations.
6. training-candidates/ : behavioral supervision candidates derived from reviewed evidence.
7. quarantine/ : low-confidence, obsolete, ambiguous-identity, conflicting, or rights-unclear records.
8. eval-candidates/ : independently sourced benchmark candidates, physically excluded from training.

## Required collectors
- NCBI Datasets: BioProject, BioSample, Assembly/Genome, Gene/annotation metadata.
- NCBI SRA metadata: run/experiment/sample accession manifests; sequence downloads only by explicit job.
- USDA GRIN-Global: Cannabis taxon/accession/passport/availability/descriptor metadata.
- Cornell/eCommons: scholarly metadata and stable DOI/Handle identities.
- BrAPI: generic client for germplasm, pedigree, crosses, seed lots, studies, observations, traits, samples, references, variants and calls.
- Ontology resolver: Crop Ontology and NCBI Taxonomy identifiers.
- Variant normalizer: reference-version-aware VCF normalization and optional GA4GH VRS computed identifiers.

## Admission gates
A normalized record must fail closed when it lacks source identity, retrieval time, provider accession, reference assembly for sequence coordinates, evidence/rights state, or required biological context.

A scientific claim must preserve:
- source_id(s)
- exact provider/persistent identifier
- study population/genotype
- environment/treatment when material
- measured trait/outcome and units
- claim scope/limitations
- publication/retrieval date
- evidence tier
- contradiction/review state.

No experiment-specific optimum becomes a universal cultivation recommendation.

## Genomic reproducibility
Coordinates are meaningless without assembly version. Store assembly accession with version on every feature/variant. Preserve original representation and normalized representation. Never silently lift variants between assemblies. Any liftover requires source assembly, target assembly, chain/mapping method, software version, status, and QC.

## Software components to evaluate/reuse
- BrAPI OpenAPI schemas and clients.
- Breeding Insight components where repository-level license permits.
- BreedBase as a reference architecture for field trials, phenotypes, genotyping, genomic selection and BrAPI interoperability.
- NCBI Datasets CLI/API rather than HTML scraping.
- bcftools/htslib/samtools for standard genomic file handling.
- GA4GH VRS Python implementation for normalized variant identifiers where plant use is compatible.

Do not vendor or copy third-party code until its exact repository license and dependency implications are recorded.

## First implementation milestones
1. Source/software registry and deterministic validator.
2. NCBI metadata collector with fixture-based tests and snapshot manifest.
3. GRIN accession collector/normalizer.
4. Canonical identity/join schema.
5. BrAPI-compatible normalized JSON records.
6. Trait/ontology resolver.
7. RAG claim builder preserving accession/citation metadata.
8. Quarantine/conflict pipeline.
9. Independent evaluation-candidate builder.
10. Only then derive reviewed SFT/grounded-QA examples and measure training-lane deduplication/concentration.
