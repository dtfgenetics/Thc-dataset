# Grow Doc Autonomous Engineer

Use this skill for any Grow Doc model/RAG/fine-tuning repository work.

## Mission
Advance verified repository state. Do not stop at audit/reporting when a safe executable fix is available.

## Startup
1. Read `.agents/state/grow-doc.json`.
2. Read current `main`, active Grow Doc PRs/branches, and latest required checks.
3. Resume `current_work_item` before starting new work unless it is externally blocked.
4. Prefer the existing active branch/PR named in state.

## Priority queue
1. Broken CI/build/runtime or invalid generated artifacts.
2. Deterministic generation/reproducibility.
3. Provenance, citations, rights/review state, source identity, dedup, leakage.
4. RAG / reviewed-grounded-QA synchronization.
5. Evaluation/benchmark infrastructure.
6. QLoRA/LoRA runtime/config/trainer correctness.
7. Bounded data-quality/coverage expansion.
8. Measured base-vs-RAG / checkpoint / adapter comparisons.
9. Adapter combination/model soup only after measured single-adapter gains.

## Execution loop
Repeat until green or truly external:
1. Inspect exact failing files/test/log.
2. Make the smallest root-cause change.
3. Run the narrow validator.
4. Fix failures and rerun.
5. Run the broader Grow Doc gate.
6. Inspect CI job logs on failure, patch, push, rerun.
7. Only merge when the exact PR head is green.

## Canonical commands
Use repository-native commands. Do not replace them with ad-hoc validation.

Core:
- `npm run validate:model-corpus-quality`
- `npm run validate:model-source-evidence-quality`
- `npm run validate:model-semantic-leakage`
- `npm run validate:model-corpus`
- `npm run validate:grounded-qa`
- `npm run validate:reviewed-claim-grounded-qa`
- `npm run validate:model-split`
- `npm run validate:training-dataset-manifest`
- `npm run validate:model-eval`
- `npm run validate:model-eval-coverage`
- `npm run validate:model-experiment-registry`

QLoRA:
- `npm run validate:qlora-config`
- `python3 scripts/validate-qlora-config.py --real-run`
- `python3 scripts/validate-qlora-packing-contract.py`
- `python3 scripts/validate-qlora-runtime-config-binding.py`
- `npm run validate:qlora-dependencies`
- `npm run validate:qlora-trainer`
- `python3 scripts/freeze-model-training-artifacts.py`
- `python3 scripts/verify-qlora-artifacts.py`

RAG / evaluation:
- `npm run validate:rag-snapshot`
- `python3 scripts/run-base-vs-rag-experiment.py --preflight-only`
- `python3 scripts/prepare-base-rag-blind-review.py --self-test`
- `python3 scripts/score-base-vs-rag-eval.py --self-test`
- `python3 scripts/validate-base-vs-rag-decision.py --self-test`

Full repository gate:
- `npm run check`
- `npm test`
- `npm run build`
- GitHub workflow: `Validate THC Grow Doc`

## Data policy
- Keep changing scientific/cultivation facts in retrieval by default.
- Reviewed/citation-verified facts are not automatically training eligible.
- Preserve source IDs, DOI/stable URL, citation locator, scope, limitations, review/rights state, dates where relevant, and hashes.
- Quarantine weak, outdated, conflicting, rights-unclear, anecdotal, or weakly sourced material.
- Regenerate derived artifacts only with canonical builders.
- Protect dev/held-out sources from exact, source-family, and semantic leakage.
- SFT/GQA factual targets must be supported by supplied evidence.

## Evaluation policy
Protected slices: factuality, diagnostic, hallucination, citation_accuracy, science, education, grounded_qa, regression.
Use dev metrics for checkpoint selection. Use held-out only for external promotion decisions.
Run base-vs-RAG before QLoRA when factual grounding is the main gap.

## Compute policy
The current GPU workflow is `.github/workflows/model-base-vs-rag-gpu.yml`.
A real run requires the dedicated `growdoc-gpu` runner and the pinned runtime/hardware contract.
If GPU execution is unavailable, record the blocker and continue the next non-GPU queue item.

## State discipline
Update `.agents/state/grow-doc.json` whenever a substantive work item is completed, blocked, replaced, or moved to a new branch/PR.
Never erase completed work history merely to make the current task look clean.
