# Grow Doc model-tuning lane

This directory is intentionally separate from the vision/reference-media admission lane.

## Current gate

`data/model-training-readiness.json` currently reports zero training-eligible vision samples. Do not train a Cannabis visual-diagnosis adapter from reference crops or display-only media. Vision supervision stays blocked until rights, human review, confirmation evidence, source-group isolation, and duplicate/leakage gates pass.

No real Grow Doc model training, adapter promotion, adapter merge, model soup, or deployment is implied by the files in this directory. The first compute experiment remains the exact Qwen3-8B base-only versus base-plus-frozen-RAG comparison on `heldout_v2`.

## Strategy

1. Keep changing factual knowledge in retrieval, not in model weights.
2. Fine-tune behavior: evidence-grounded answering, diagnostic uncertainty, differential reasoning, citation discipline, educational clarity, and refusal to invent universal thresholds.
3. Preserve source identifiers/DOIs in every training and evaluation record.
4. Keep evaluation locked and separate from SFT data.
5. Compare adapters against the untuned base model. Do not merge adapters or build a model soup unless held-out aggregate and safety-critical slices improve without material regressions.

## Dataset lanes

- `eval/heldout_v2.jsonl`: current locked behavioral/factuality evaluation set. Never use it for training, prompt tuning, adapter-selection example generation, or retrieval demonstrations.
- `generated/splits/train_sft_v1.jsonl` and `generated/splits/dev_sft_v1.jsonl`: source-component-isolated supervised behavior examples.
- `generated/splits/train_grounded_qa_mixture_v1.jsonl`: deterministic, profile-balanced grounded-QA subset used in the actual training mixture. It is capped at 20% of training rows.
- `generated/splits/dev_grounded_qa_v1.jsonl`: development grounded-QA lane; never mixed into training.
- `generated/rag/claims_v1.jsonl`: retrieval knowledge with provenance, claim boundaries, dates, limitations, and source identifiers. Changing or measurement-heavy factual knowledge belongs here by default.
- `generated/quarantine/quarantine_v1.jsonl`: low-confidence, outdated, rights-unclear, weakly sourced, conflicting, or otherwise training-ineligible material. Quarantine content must not silently enter SFT.
- `generated/splits/split_manifest_v1.json`: deterministic source-component train/dev split over all sanitized SFT/GQA candidates.
- `generated/splits/training_split_manifest_v1.json`: the capped training-mixture split manifest used by the QLoRA contract.
- `generated/training_dataset_manifest_v2.json`: leak-safe parent training manifest binding train/dev SFT, capped train grounded-QA, dev grounded-QA, retrieval, quarantine, heldout, and the training split manifest.
- `generated/manifest_v1.json`: corpus build statistics only. It is **not** the training-dataset manifest and must not be used as the QLoRA dataset lock.
- `generated/training_artifact_lock_v3.json`: byte-level freeze report for the supplied-claim-grounded training artifacts.

All 351 candidate SFT/GQA records are rewritten before splitting with `grounding_mode=supplied_claims_only_v1`. Factual assistant bullets must be exact claims physically present in the user evidence, with their source IDs. Task-specific diagnostic, differential, and education behavior is supplied only through fixed non-factual scaffolding. This prevents profile-wide facts from appearing in a training target when those facts were not in the prompt evidence.

Generated artifacts may be materialized during validation or experiment preparation rather than committed. Their byte hashes are pinned before a real run.

## Frozen training contract

Current Qwen3-8B starter contract:

- base/tokenizer revision: `b968826d9c46dd6066d109eabc6255188de91218`
- tokenizer chat-template SHA-256: `a55ee1b1660128b7098723e0abcd92caa0788061051c62d51cbe87d9cf1974d8`
- Qwen3 thinking mode: `enable_thinking=false`
- training split manifest SHA-256: `d1eb2605d1fc825c185e1d2e90171c9cbef8a3a29065f538e0fe965738dc2caf`
- training dataset manifest SHA-256: `cb8c5b58a560439c929e7710ddb2b378ffa29c7994272e5ef5835daaa654a277`
- dependency-lock resolver: `uv==0.12.10`
- dependency-lock SHA-256: `ee386c57e5e3f969e849b0489ad9d171956bf229a80f012518966e887682243e`
- training mixture: 144 SFT + 36 grounded-QA = 180 rows, exactly 20% grounded-QA

The dependency lock is not trusted merely because direct package versions are pinned. CI re-materializes the full transitive lock from `requirements.in` using the exact resolver/version and rejects the run if the resulting bytes do not match the pinned SHA.

## Validation commands

```bash
npm run validate:model-grounding
npm run validate:qlora-config
npm run validate:qlora-dependencies
npm run validate:qlora-trainer
python3 scripts/freeze-model-training-artifacts.py
python3 scripts/verify-qlora-artifacts.py
```

For full dependency-lock materialization, install exactly `uv==0.12.10`, then run:

```bash
python3 scripts/verify-qlora-dependency-contract.py --materialize
```

The QLoRA trainer supports a non-training preflight:

```bash
python3 scripts/train-grow-doc-qlora.py --preflight-only
```

A real trainer invocation is intentionally separate and requires CUDA plus the exact pinned runtime packages. The trainer uses assistant-only loss masking and refuses silent sequence truncation. Its output manifest is `trained_not_promoted`; it does not merge or deploy an adapter.

## First benchmark hardware contract

The pinned base-vs-RAG experiment evaluates Qwen3-8B in unquantized `bfloat16`. The launcher fails before model load unless all of the following are true:

- CUDA is available;
- GPU 0 reports at least **20 GiB** VRAM;
- the GPU reports native bfloat16 support;
- exact pinned runtime packages and dependency-lock bytes match;
- the checkout is clean and the exact frozen benchmark/RAG artifacts can be rebuilt.

A T4 does **not** satisfy the current contract. Use an L4/A10G-class 24 GiB GPU or larger that supports BF16. Do not weaken the dtype or memory contract merely to use cheaper hardware; changing dtype/quantization would define a different experiment and requires a separately pinned evaluation contract.

Hardware readiness can be checked without inference:

```bash
python3 scripts/run-base-vs-rag-experiment.py --preflight-only
```

The real benchmark command is:

```bash
python3 scripts/run-base-vs-rag-experiment.py \
  --output-root model_tuning/runs/base_vs_rag_v1
```

Both arms must record the same runtime environment and expected CUDA device. Raw outputs remain `pending_review`; the launcher never claims RAG improvement by itself.

## Blinded base-vs-RAG review

After both inference arms complete, build the deterministic blinded A/B packet. Reviewers score expected semantic points without knowing which arm used retrieval. Response text must not be edited during review.

```bash
python3 scripts/prepare-base-rag-blind-review.py --help
python3 scripts/score-base-vs-rag-eval.py --help
```

The dedicated base-vs-RAG scorer intentionally allows retrieval configuration to differ while requiring the same base model, tokenizer/template contract, decoding, benchmark, scorer revision, and core runtime. This is separate from adapter-promotion scoring, where retrieval must remain identical between candidate and baseline.

## Evaluation slices

Required slices are factuality, diagnostic reasoning, hallucination resistance, citation accuracy, science, education clarity, grounded QA, and regression. A candidate must be compared to its exact base-model revision on the same frozen evaluation set and retrieval snapshot.

Promotion gate:

- no citation-accuracy regression;
- no hallucination-slice regression;
- no safety-critical diagnostic regression;
- aggregate score improves by at least 2 percentage points;
- adapter merge/soup is rejected if gains come only from one slice while another critical slice degrades.

## Base-model shortlist

Start with text-first behavior tuning. Candidate families should be benchmarked before choosing a larger training target:

- Qwen3 8B: pinned primary practical baseline and QLoRA starter target.
- Gemma 3 12B: second-family comparison; multimodal capability is not a reason to bypass the blocked vision-admission gate.
- Mistral/Ministral ~24B class: higher-memory quality ceiling or teacher candidate, not the default first run.

Pin exact license/terms, model revision, tokenizer revision, chat template, dependency lock, decoding contract, and retrieval snapshot before comparing any candidate.

## QLoRA defaults

`config/qlora_8b.yaml` uses NF4 4-bit loading with bfloat16 compute, LoRA rank 32 / alpha 64 over attention and MLP projections, 4096 maximum sequence length, learning rate `1e-4`, two epochs, gradient accumulation 16, and external held-out checkpoint selection. `load_best_model_at_end` remains disabled because promotion belongs to the external evaluation gate.

## Retrieval policy

Answers about measurements, cultivar-specific behavior, disease confirmation, nutrient thresholds, legal/current recommendations, or newly published science should retrieve evidence at inference time. Fine-tuning should teach the model to use supplied evidence and state limitations, not to memorize a changing encyclopedia.

## Experiment order

1. Freeze the exact base model/tokenizer/template/dependency contract, `heldout_v2`, decoding settings, and training artifacts.
2. Materialize the exact frozen `heldout_v2` RAG snapshot.
3. Pass the base-vs-RAG hardware/runtime preflight on BF16-capable CUDA hardware with at least 20 GiB VRAM.
4. Run `scripts/run-base-vs-rag-experiment.py` to compare the untuned pinned base model without retrieval against the identical base model with the frozen snapshot.
5. Blind-review and score both arms using the dedicated base-vs-RAG workflow. Use that result to decide whether QLoRA is justified.
6. Only if behavior gaps remain after retrieval, run `scripts/train-grow-doc-qlora.py` using the leak-safe supplied-claim-grounded train mixture.
7. Evaluate the adapter against the exact frozen baselines and adapter-promotion scorer.
8. Do not promote checkpoints, combine adapters, build model soup, merge weights, or deploy unless the registered aggregate and critical-slice gates are satisfied.
