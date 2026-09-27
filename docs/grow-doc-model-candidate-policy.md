# Grow Doc open-weight model candidate policy

Grow Doc promotes models by measured domain performance, not by generic leaderboard rank.

## Required comparison order

1. Evaluate the untouched instruct/base candidate on the permanent held-out suite.
2. Evaluate the same candidate with the frozen Grow Doc retrieval snapshot.
3. Only train a LoRA/QLoRA adapter if retrieval alone does not satisfy the target behavior.
4. Evaluate adapter + the identical retrieval snapshot against base + retrieval.
5. Promote an adapter only when it improves the aggregate score without a material regression in factuality, diagnostic calibration/abstention, hallucination resistance, citation precision/recall, or deterministic regression cases.
6. Do not merge adapters or create a model soup unless every candidate has comparable exact-head evaluation artifacts and the combination improves the permanent held-out suite.

## Candidate tiers

### Tier A: efficient text baseline

- Qwen3 8B-class instruct/base checkpoint.
- Purpose: low-cost reproducible baseline for SFT/QLoRA and RAG experiments.
- Verify the exact upstream model card, license, tokenizer/chat template, context limit, and Transformers compatibility before pinning a revision.

### Tier B: stronger local generalist

- Mistral Small 3.1 24B-class instruct/base checkpoint.
- Purpose: higher-capacity comparison for grounded QA and diagnostic reasoning where hardware permits.
- Upstream release is Apache-2.0 and advertises a 128k context window; pin an exact downloadable checkpoint/revision before evaluation.

### Tier C: newer multimodal candidate

- Mistral Small 4-class checkpoint.
- Purpose: future image+text diagnostic comparison after the visual dataset has enough rights-cleared, human-reviewed, source-isolated training/evaluation material.
- Do not use reference imagery as supervised diagnosis labels merely because a multimodal base model is available.

## Permanent evaluation lanes

Every candidate must use the same frozen evaluation inputs and retrieval snapshot. Record at minimum:

- factuality / scientific correctness;
- grounded-QA answer support;
- citation precision and citation recall;
- diagnostic differential quality;
- diagnostic calibration and abstention when evidence is insufficient;
- hallucination / unsupported-claim rate;
- regression-suite pass rate;
- latency, peak memory, context settings, quantization, model revision, tokenizer revision, and retrieval snapshot ID.

Never train on permanent held-out examples, expected answers, grader rationales, or their close paraphrases.

## Promotion rule

A candidate is not "better" because its aggregate score rises while a safety-critical lane falls. Promotion requires no material regression in diagnostic calibration, unsupported-claim behavior, or citation support. Store per-lane results and deltas so the decision is auditable.

## RAG-first boundary

Stable response style, reasoning procedure, diagnostic workflow, output schema, evidence-ranking behavior, and domain terminology are reasonable adapter targets. Facts that can change, detailed cultivation reference values, source-dependent claims, citations, product/legal information, and encyclopedia-style knowledge should normally remain retrieval-grounded.

## Adapter-combination rule

Do not average or stack adapters speculatively. First evaluate each adapter independently on identical artifacts. A proposed combination must be evaluated as a new candidate and must outperform the best constituent under the same promotion rule. If it does not, reject it.
