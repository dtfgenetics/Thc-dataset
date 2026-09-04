# Grow Doc model-tuning lane

This directory is intentionally separate from the vision/reference-media admission lane.

## Current gate

`data/model-training-readiness.json` currently reports zero training-eligible vision samples. Do not train a Cannabis visual-diagnosis adapter from reference crops or display-only media. Vision supervision stays blocked until rights, human review, confirmation evidence, source-group isolation, and duplicate/leakage gates pass.

## Strategy

1. Keep changing factual knowledge in retrieval, not in model weights.
2. Fine-tune behavior: evidence-grounded answering, diagnostic uncertainty, differential reasoning, citation discipline, educational clarity, and refusal to invent universal thresholds.
3. Preserve source identifiers/DOIs in every training and evaluation record.
4. Keep evaluation locked and separate from SFT data.
5. Compare adapters against the untuned base model. Do not merge adapters or build a model soup unless held-out aggregate and safety-critical slices improve without material regressions.

## Dataset lanes

- `eval/heldout_v2.jsonl`: current locked behavioral/factuality evaluation set. Never use it for training, prompt tuning, adapter-selection example generation, or retrieval demonstrations.
- `generated/splits/train_sft_v1.jsonl` and `generated/splits/dev_sft_v1.jsonl`: source-component-isolated supervised behavior examples built only from reviewed knowledge records.
- `generated/splits/train_grounded_qa_v1.jsonl` and `generated/splits/dev_grounded_qa_v1.jsonl`: citation-preserving grounded-QA examples that require supplied context and provenance.
- `generated/rag/claims_v1.jsonl`: retrieval knowledge with provenance, claim boundaries, dates, limitations, and source identifiers. Changing or measurement-heavy factual knowledge belongs here by default.
- `generated/quarantine/quarantine_v1.jsonl`: low-confidence, outdated, rights-unclear, weakly sourced, conflicting, or otherwise training-ineligible material. Quarantine content must not silently enter SFT.
- `generated/splits/split_manifest_v1.json`: deterministic source-component train/dev split manifest.
- `generated/manifest_v1.json`: deterministic parent training-data manifest binding the materialized splits, retrieval, quarantine, held-out set, and source isolation checks.

Generated artifacts may be materialized during validation or experiment preparation rather than committed to the repository. Their hashes must be recorded before any real training run.

## Evaluation slices

Required slices are factuality, diagnostic reasoning, hallucination resistance, citation accuracy, science, education clarity, grounded QA, and regression. A candidate must be compared to its exact base-model revision on the same frozen evaluation set and retrieval snapshot.

Recommended promotion gate:
- no citation-accuracy regression;
- no hallucination-slice regression;
- no safety-critical diagnostic regression;
- aggregate score improves by >= 2 percentage points or a pre-registered practical threshold;
- adapter merge/soup is rejected if gains come only from one slice while another critical slice degrades.

## Base-model shortlist

Start with text-first behavior tuning. Candidate families should be benchmarked locally before choosing a training target:
- Qwen3 8B class: current QLoRA starter target and strong small-model candidate for retrieval-grounded behavior tuning.
- Gemma 3 12B class: larger candidate with multimodal capability, useful later if a rights-cleared vision lane unlocks.
- Mistral Small 3.1 24B class: higher-memory candidate; useful as a quality ceiling or teacher/evaluator if hardware permits.

Pin exact license/terms, model revision, tokenizer revision, chat template, and dependency lock before training or benchmark comparison.

## QLoRA defaults

The config in `config/qlora_8b.yaml` is a conservative starting point, not a claim of an executed run. It uses NF4 QLoRA, keeps grounded QA capped at 20% of the training mixture, requires source-component-isolated train/dev data, requires split and dataset manifest hashes, and leaves best-checkpoint promotion external to the trainer.

Before any real run, pin model and tokenizer revisions, dependency versions, tokenizer/chat template, dataset and split manifest hashes, random seeds, and hardware/CUDA details.

## Retrieval policy

Answers about measurements, cultivar-specific behavior, disease confirmation, nutrient thresholds, legal/current recommendations, or newly published science should retrieve evidence at inference time. Fine-tuning should teach the model to use supplied evidence and state limitations, not to memorize a changing encyclopedia.

## Experiment order

1. Freeze the exact base-model/tokenizer revision, heldout_v2, retrieval snapshot, decoding settings, and dataset/split manifests.
2. Benchmark the untuned base model without retrieval.
3. Benchmark the identical base model with the frozen retrieval snapshot.
4. Only if behavior gaps remain after retrieval, run a QLoRA adapter using the leak-safe train split and compare it against the exact frozen baselines.
5. Do not promote checkpoints, combine adapters, or build model soup unless the registered aggregate and critical-slice gates are satisfied.
