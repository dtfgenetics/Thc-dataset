# Grow Doc model workstream completion status

Status: **baseline engineering complete; external compute and supervised-vision acquisition remain blocked.**

Verified main baseline before this reconciliation: `b26d42dfe1205b49b0461c4fb34a6a669c90cb75`.

## Completed baseline

- Deterministic reviewed scientific RAG publication with provenance, scope, limitations, rights/review state, and claim hashes.
- 695 retrieval claims in the frozen generated corpus.
- 11 reviewed claim grounded-QA candidates covering Cornell and USDA sources; all remain RAG-first and training-ineligible pending explicit admission.
- Strong-evidence behavior corpus with source-component train/dev isolation, exact/semantic deduplication, quarantine, supplied-claim grounding, and held-out leakage guards.
- Frozen training mixture: 176 rows = 141 SFT + 35 grounded-QA (19.89% grounded-QA).
- Frozen heldout-v3: 16 cases, two cases per protected slice, 16 distinct source identities.
- Protected slices: factuality, diagnostic, hallucination, citation_accuracy, science, education, grounded_qa, regression.
- Development-only diagnostic abstention challenges for insufficient evidence, multifactor ambiguity, and lab-confirmation boundaries.
- Pinned Qwen3-8B base/tokenizer revision, chat-template hash, dependency-lock hash, split/dataset hashes, deterministic seeds, assistant-only loss masking, no silent truncation, dev-only checkpoint selection, and protected held-out promotion gates.
- Base-vs-RAG launcher, strict no-offload evaluator, blinded review packet, scorer, and decision gate all pass repository validation.
- Adapter combination policy is fail-closed: no merge/model soup unless measured aggregate performance improves with zero protected critical-slice regression.
- Persistent autonomous-engineer skill/state contract is repository-enforced.
- README/model contract drift is now CI-gated after artifact freezing.

## Operational task-registry note

`GD-SYS-001`, `GD-GQA-001`, and `GD-EVAL-001` remain `active` in `contributions/tasks.json` even though their current baseline definitions of done are satisfied. This is intentional: the contribution/receipt router only permits active tasks to accept future incremental receipts. Their active routing status is not a release blocker.

## External blockers

### GD-COMPUTE-001 — frozen base-vs-RAG benchmark

Blocked by unavailable qualifying GPU execution. The experiment requires one CUDA GPU with native BF16 and at least 20 GiB VRAM. The GitHub workflow targets `[self-hosted, linux, x64, growdoc-gpu]`. No qualifying online runner has been verified. Managed Hugging Face L4 and Zero-A10G dispatch attempts returned HTTP 402 Payment Required before startup.

Until this benchmark runs, there is no measured basis to claim RAG improvement, authorize QLoRA, compare checkpoints, promote an adapter, merge adapters, or deploy a model.

### GD-VISION-001 — supervised diagnostic vision

Blocked by data admission, not code. Current training-eligible vision samples: 0. Reference media remain reference-only. Supervised vision work requires rights-cleared, human-reviewed, diagnosis-confirmed Cannabis media meeting source-group, duplicate/leakage, control, negative, and class-coverage thresholds in `data/model-training-readiness.json`.

## Non-blocking continuous research lane

`GD-RAG-001` remains active as ongoing scientific content expansion. It is not a blocker to the current text-model baseline release because the RAG, provenance, training-isolation, and evaluation systems are operational and green. Additional reviewed claims should continue through the same fail-closed ingestion/review pipeline.

## Next executable action

1. Provide/enable a qualifying GPU.
2. Run `python3 scripts/run-base-vs-rag-experiment.py --preflight-only`.
3. Run the exact frozen base-vs-RAG experiment.
4. Blind-review and score both arms.
5. Only if measured residual behavior gaps remain after retrieval, run QLoRA.
6. Evaluate any adapter against the exact frozen baseline; do not combine or deploy without passing the protected-slice promotion gate.
