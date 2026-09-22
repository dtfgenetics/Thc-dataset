# Treatment-Anchor Corpus Regeneration Review

Date: 2026-09-21  
Branch: `grow-doc/treatment-anchor-regeneration-20260921`  
Reviewed candidate head: `40727581416625dafaa516324101d9f4de2acb81`

## Purpose

This review evaluates the deterministic corpus impact of treating `treatment` / treatment-response language as generic experimental context rather than a foreign diagnostic-target anchor during SFT evidence ranking.

It does **not** authorize or claim model training, checkpoint promotion, adapter/model-soup merging, weight merging, or deployment.

## Reproducibility evidence

Baseline artifact:
- workflow run: `35676755036`
- reviewed head: `d568837c04d288d1165717f38c6a67f8df4d302e`
- artifact ID: `10673990558`
- artifact digest: `sha256:9c8b4a176dc3f48662fd2b3347f5c42cdbaacd32b94474ba684a793311b07535`

Candidate artifact:
- workflow run: `35676911909`
- candidate head: `40727581416625dafaa516324101d9f4de2acb81`
- artifact ID: `10672942459`
- artifact digest: `sha256:c573f5a75c97c20b40459b5ede92fad178bc74faadae9821076f491d4af46818`

The candidate reproduced the same post-change manifest hashes previously observed on the superseded mixed branch, providing an independent deterministic reproduction on current `main`.

## Corpus-level invariants

The following values are unchanged between baseline and candidate:

| Metric | Baseline | Candidate |
| --- | ---: | ---: |
| Input profiles | 61 | 61 |
| Duplicate claims removed | 676 | 676 |
| Merged provenance links | 676 | 676 |
| Held-out profiles excluded from SFT | 25 | 25 |
| Held-out source IDs | 8 | 8 |
| Held-out source collision exclusions | 0 | 0 |
| Quarantine records | 25 | 25 |
| RAG claims | 695 | 695 |
| SFT examples | 177 | 177 |
| Differential-and-next-test examples | 59 | 59 |
| Grounded-diagnostic-reasoning examples | 59 | 59 |
| Science-education examples | 59 | 59 |
| Sanitized split records | 332 | 332 |
| Train records | 266 | 266 |
| Dev records | 66 | 66 |
| Train SFT records | 129 | 129 |
| Dev SFT records | 48 | 48 |
| Train grounded-QA records | 137 | 137 |
| Dev grounded-QA records | 18 | 18 |
| Train profiles | 43 | 43 |
| Dev profiles | 16 | 16 |
| Train sources | 134 | 134 |
| Dev sources | 15 | 15 |

Protected split invariants remain unchanged:
- `components_atomic = true`
- `heldout_source_overlap = 0`
- `normalized_conversation_overlap = 0`
- `profile_overlap = 0`
- `source_overlap = 0`

The input, held-out/eval, corpus manifest, grounded-QA, RAG, quarantine, and dedup-audit artifacts remain unchanged.

## Record-level impact

All 177 SFT IDs remain present. Train/dev membership is identical.

Exactly 45 SFT examples change across 15 profiles:
- 15 changed records are in train.
- 30 changed records are in dev.
- all three task variants change together for each affected profile: diagnostic, differential, and education.
- 24 records across 8 profiles only reorder the same selected evidence.
- 21 records across 7 profiles replace exactly one selected evidence claim with another.
- no affected example changes its record ID or split membership.
- 42 of the 45 assistant target answers are byte-for-byte unchanged.
- the three Armyworm assistant targets retain the same interpretation, observations, differentials, confirmation guidance, and limitations; only the citation line changes to match the selected evidence.
- only the three Armyworm examples change the `source_ids` set, dropping the Missouri source after its selected claim is replaced.

Profiles with evidence reordering only:
- `env-heat` (dev)
- `fungal-southern-blight` (train)
- `nut-def-ca` (dev)
- `nut-def-n` (dev)
- `nut-def-zn` (dev)
- `nut-tox-b` (train)
- `nut-tox-mn` (dev)
- `root-white-root-rot` (train)

## Evidence substitutions

Each substitution below occurs identically in the diagnostic, differential, and education variants for that profile.

| Profile | Split | Removed selected claim | Added selected claim |
| --- | --- | --- | --- |
| `insect-armyworm-complex` | train | Missouri extension: armyworm larvae can create irregular holes/skeletonization and may enter buds/flowers with silk/frass | PNW handbook: regional host/timing/damage/management statements are bounded and do not establish a universal species-level image rule or treatment threshold |
| `nut-def-fe` | dev | Late severe endpoint: most non-inflorescence leaves brown/curled/dry by week seven | Experimental context: three Gelato 29 plants per treatment, DWC, flowering-stage withholding, daily examination/weekly photos, laboratory analysis at symptom onset |
| `nut-def-k` | dev | A nitrogen-withholding symptom claim describing near-total fan-leaf yellowing and sugar-leaf chlorosis | Same experiment-design/context claim above |
| `nut-def-mg` | dev | A prolonged severe endpoint claim describing fan-leaf senescence and progressive sugar-leaf yellowing/browning | Same experiment-design/context claim above |
| `nut-def-mn` | dev | Nitrogen-withheld yield-loss claim | Claim describing progressive fan-leaf yellowing, petiole/stem changes, senescence, and sugar-leaf chlorosis |
| `nut-def-s` | dev | A prolonged severe endpoint claim describing fan-leaf senescence and progressive sugar-leaf yellowing/browning | Same experiment-design/context claim above |
| `stress-salinity-high-ec` | train | 2020 study: 40 mM NaCl reduced growth index/chlorophyll in hydroponics but not aquaponics | 2024 study: cultivar/mesocosm/biostimulant context means EC values are treatment conditions, not universal Cannabis thresholds |

These substitutions are consistent with the intended change: generic words such as “treatment” no longer behave like a diagnostic entity that can incorrectly penalize otherwise useful experiment-context evidence.

## Changed artifact hashes

Only SFT-derived bytes and manifests that transitively hash those bytes change.

| Artifact | Baseline SHA-256 | Candidate SHA-256 |
| --- | --- | --- |
| `splits/train_sft_v1.jsonl` | `c3981b1371934e0cafbf3d134b1071456d809c954ef76bb280b86e50c7af7f48` | `f6b8d80d307cc342fbf0ab50bca282939ad4064a50869bb0df3eeaee3d61b1ab` |
| `splits/dev_sft_v1.jsonl` | `7a7a14a98d94a87a43b78c11e4ab04a006a0909f440a5bf5342f163c9c09ffcc` | `1e8d52746399616d6f1d8ed20faf327a0487df478d0c294884371b9fcf40080d` |
| `splits/split_manifest_v1.json` | `398a2662395e6f11ceb2f41a1ad4964cfd95b30906ce48c893d2ebed40c78ba4` | `50d29b662f58d0882609adfc4376cc38bc2c83834df59dfad69e0198b86da1ab` |
| `splits/training_split_manifest_v1.json` | `eabe77b07c027d78929852c6cef77993ddd53ceab4b08c76063b793eaa46cac6` | `fcd766964571ac605495514e4a1ce19609bd679895859add7815bad492a8113a` |
| internal `training_dataset_manifest_v2.json` manifest hash | `a8ea0cb9d1497072e1a81d836617e6a2d73e75974c3b7be33ded061d469fdc30` | `0112ca4ce7cadfbf0a3170dabf8a438415ad7aead702e7dcb3fd466371b9a20a` |
| frozen training dataset manifest | `e7049cf59860bcc1620761ba7dfcacd0a6847a8ee80f9c140c2fb0ce11ab62ea` | `b1351cc6d4bf89e57eab070d35cd67756131c8e59e0406f96c216c130f802e02` |

Training SFT byte size changes from 762,809 to 763,193 bytes (+384). Dev SFT changes from 295,853 to 297,977 bytes (+2,124). Counts remain unchanged.

## Gate result

The candidate passes the evaluation and training-evidence workflows. Full validation reaches the frozen-artifact verifier and fails only because `model_tuning/config/qlora_8b.yaml` still pins the reviewed baseline hashes:

- old training split manifest: `eabe77b07c027d78929852c6cef77993ddd53ceab4b08c76063b793eaa46cac6`
- candidate training split manifest: `fcd766964571ac605495514e4a1ce19609bd679895859add7815bad492a8113a`
- old training dataset manifest: `e7049cf59860bcc1620761ba7dfcacd0a6847a8ee80f9c140c2fb0ce11ab62ea`
- candidate training dataset manifest: `b1351cc6d4bf89e57eab070d35cd67756131c8e59e0406f96c216c130f802e02`

Because the candidate is deterministically reproduced, record membership/counts are unchanged, protected leakage/provenance invariants remain clean, and the record-level changes match the intended ranking correction, these two frozen pins may be advanced to the candidate values. Full validation must then rerun on the exact updated head before this draft can be promoted or merged.
