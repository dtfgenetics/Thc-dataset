# Grow Doc contribution lanes

This directory coordinates safe parallel contributions without bypassing canonical data or model validators.

- `tasks.json` is the machine-readable gap/task registry.
- `receipts/` stores contribution receipts tying work to a task, branch, exact base/head commits, actual Git-changed paths, sources, and completed validation.
- Scientific factual claims default to reviewed claims and RAG, never directly to model weights.
- Behavioral SFT/GQA must pass evidence, deduplication, leakage, and held-out isolation gates.
- Evaluation candidates are evaluation-only.
- Reference media remains reference-only until explicit training-eligibility review passes.

Canonical artifacts remain under `data/`, `dataset/`, and `model_tuning/`.

## Routing

Prepare a contribution manifest containing `contribution_id`, `task_id`, `lane`, `base_commit`, `head_commit`, `branch`, `changed_paths`, and `source_ids`. Run `python3 scripts/grow-doc-contribution.py --route-manifest <manifest.json>`. The router rejects paths outside the selected lane, reports required validators, and emits a deterministic receipt skeleton. Routing never authorizes promotion; existing evidence, leakage, review, training, and evaluation gates remain authoritative.

## Final receipts from Git

Do not hand-type the final changed-path list. After the required validators pass, run `npm run receipt:grow-doc -- --task-id <TASK> --base-commit <BASE_SHA> --head-commit <HEAD_SHA> --branch <work/grow-doc/...> --completed-validator <name> ... --out contributions/receipts/<id>.json`. The generator resolves full commit SHAs, derives the task lane and validator contract, reads the actual `base...head` Git diff, rejects paths outside task/lane ownership, and refuses to produce a final receipt when required validators are missing. Committed receipts are revalidated by CI.
