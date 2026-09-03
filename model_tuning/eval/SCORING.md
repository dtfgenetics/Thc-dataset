# Grow Doc checkpoint scoring and promotion

`heldout_v1.jsonl` is frozen evaluation data and must never be included in SFT, preference, retrieval-training, or adapter-merge inputs.

## Prediction format

One JSON object per benchmark id:

```json
{"id":"fact-n-001","response":"...","point_scores":[1,1,1],"reviewed_by":"reviewer-or-evaluator-id"}
```

`response` is the raw model answer. `point_scores` contains one binary judgment for each `expected_points` entry in the matching held-out case. `reviewed_by` records who or what performed the semantic review.

Deterministic scoring checks exact required source identifiers and forbidden claims. Semantic correctness is deliberately **not** approximated with token overlap or embedding similarity. A promotion comparison requires complete reviewed semantic scores.

## Run

```bash
python3 scripts/score-model-eval.py \
  --predictions results/qwen3-8b-adapter-x.jsonl \
  --baseline results/qwen3-8b-base.jsonl \
  --require-reviewed \
  --out results/qwen3-8b-adapter-x.report.json
```

The default promotion rule requires at least +2.0 percentage points in aggregate score and no aggregate regression on the diagnostic, hallucination, or citation-accuracy slices. The scorer refuses promotion comparisons that lack reviewed semantic judgments.

## Interpretation

The aggregate is 60% reviewed semantic correctness, 20% required-citation accuracy, and 20% forbidden-claim avoidance. Slice scores must be inspected in addition to the aggregate. Adapter merging/model soup remains locked unless pairwise candidate evaluation passes the configured promotion gate.

This harness scores model outputs; it does not run inference itself. Base-model and checkpoint inference must pin the model revision, tokenizer revision, decoding parameters, retrieval snapshot, dependency lock, and hardware/runtime metadata so comparisons are reproducible.
