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

- `eval/heldout_v1.jsonl`: locked behavioral/factuality evaluation examples. Never use for training, prompt tuning, adapter selection-example generation, or retrieval demonstrations.
- Future `sft/`: citation-preserving supervised examples generated only from reviewed knowledge records.
- Future `rag/`: retrieval documents/chunks with provenance, claim boundaries, dates, and source identifiers.
- Future `quarantine/`: low-confidence, outdated, rights-unclear, weakly sourced, or conflicting material. Quarantine content must not silently enter SFT.

## Evaluation slices

Required slices are factuality, diagnostic reasoning, hallucination resistance, citation accuracy, education clarity, grounded QA, and regression. A candidate must be compared to its exact base model on the same frozen evaluation set.

Recommended promotion gate:
- no citation-accuracy regression;
- no hallucination-slice regression;
- no safety-critical diagnostic regression;
- aggregate score improves by >= 2 percentage points or a pre-registered practical threshold;
- adapter merge/soup is rejected if gains come only from one slice while another critical slice degrades.

## Base-model shortlist

Start with text-first behavior tuning. Candidate families should be benchmarked locally before choosing a training target:
- Qwen3 8B class: strong small-model candidate for QLoRA and long-context RAG.
- Gemma 3 12B class: larger candidate with 128K context and multimodal capability, useful later if a rights-cleared vision lane unlocks.
- Mistral Small 3.1 24B class: higher-memory candidate; useful as a quality ceiling or teacher/evaluator if hardware permits.

Pin exact license/terms and model revision before training.

## QLoRA defaults

The config in `config/qlora_8b.yaml` is a conservative starting point, not a claim of an executed run. It prefers behavior tuning over memorization, uses a low learning rate, and does not enable long-context scaling by default.

Before any real run, pin model revision, dependency versions, tokenizer/chat template, dataset manifest hashes, random seeds, and hardware/CUDA details.

## Retrieval policy

Answers about measurements, cultivar-specific behavior, disease confirmation, nutrient thresholds, legal/current recommendations, or newly published science should retrieve evidence at inference time. Fine-tuning should teach the model to use supplied evidence and state limitations, not to memorize a changing encyclopedia.
