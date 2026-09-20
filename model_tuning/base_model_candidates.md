# Grow Doc base-model candidate matrix

Status: evaluation planning only. This document does **not** record a training run, benchmark win, adapter merge, or deployment.

## Decision rule

Grow Doc should select base models and adapters from measured held-out performance, not general leaderboard reputation. Factual cultivation knowledge that changes with evidence should remain retrieval-grounded. SFT/LoRA should primarily teach diagnostic process, uncertainty calibration, citation behavior, evidence use, educational structure, and tool/RAG behavior.

A candidate is promotable only when it is evaluated on the frozen Grow Doc held-out suite and does not regress any protected slice. Protected slices are factuality, diagnostics, hallucination resistance, citation accuracy, science, education, grounded QA, and regression cases. Adapter/model-soup combinations must be evaluated as new candidates; do not combine them merely because their parents score well independently.

## Candidate tiers

| Candidate | Size | Why evaluate | Main concern | Role |
| --- | ---: | --- | --- | --- |
| Qwen3-8B | 8.2B | Current practical QLoRA target; strong instruction/reasoning/tool behavior; long-context support | Thinking/non-thinking template must be frozen consistently across train/eval | Primary 8B baseline |
| Llama 3.1 8B Instruct | 8B | Mature 8B comparison point with long context and broad runtime support | Different license and older generation; must win Grow Doc slices rather than reputation | Control baseline |
| Mistral Small 3.1 24B | 24B | Larger-capacity Apache-2.0 comparison with 128k context | Higher VRAM/training cost; multimodal architecture is unnecessary for text-only tuning unless vision is intentionally evaluated | Capacity ceiling / later-stage candidate |

Do not add a model to the training queue until its exact repository, revision/commit, tokenizer revision, chat-template hash, license, context policy, quantization recipe, dependency lock, and evaluation generation settings are pinned.

## Required evaluation protocol

1. Freeze the corpus manifest, held-out manifests, retrieval snapshot, tokenizer/chat template, prompt format, generation settings, and evaluator versions.
2. Evaluate the untouched base/instruct candidate first. This establishes whether fine-tuning actually improves Grow Doc rather than masking a weak base.
3. Train one adapter at a time from the same frozen data split and record exact artifact hashes.
4. Score factuality, diagnostic differential quality, uncertainty calibration, hallucination resistance, citation precision/recall, grounded-QA faithfulness, science/education quality, and regression cases separately.
5. Require citation claims to be supported by retrieved evidence; do not reward plausible unsupported answers.
6. Reject any checkpoint with a protected-slice regression even when aggregate score improves.
7. Compare checkpoints from the same run before considering cross-run adapter arithmetic or model soup.
8. Evaluate every adapter combination as an independent candidate. Keep it only if it improves measured held-out performance without protected-slice regression.

## Data policy before the next GPU run

The corpus builder must use the shared `scripts/source_identity.py` comparison contract before corpus regeneration. After that migration passes parity/leakage/citation gates, regenerate deterministically and report: exact-claim duplicates removed, canonical source aliases consolidated, held-out source exclusions, quarantine counts/reasons, citation retention, task distribution, and retrieval-vs-SFT composition.

Low-confidence, incomplete-provenance, superseded, or unreviewed material belongs in quarantine/retrieval review, not SFT. Preserve original citation metadata even when canonical identities are used for comparison and leakage prevention.

## Current recommendation

Keep Qwen3-8B as the first measured QLoRA baseline because the repository already has a reviewed 8B training contract around it. Use Llama 3.1 8B Instruct as the same-size control and Mistral Small 3.1 24B only after the corpus/provenance gate is clean and sufficient compute is available. No model is declared superior until the Grow Doc held-out suite says so.
