# Label taxonomy review checklist

This checklist is meant to convert path-derived labels into reviewed scientific labels before production training.

## Priority classes

1. healthy
2. water_stress_3_days
3. water_stress_6_days
4. water_stress_9_days
5. growth_time_series

## Review steps

- Confirm each class matches the article and crop stage.
- Check time-series continuity for DS-090 across plant IDs and dates.
- Keep the same plant and time frame together in train/val/test.
- Document whether the label is a plant state, symptom state, or classification task.
- If uncertain, downgrade the label to `needs_review` and exclude it from a training run.

## Rules

- Path-derived labels are not ground truth.
- Visual symptoms alone do not prove the underlying cause.
- Keep benchmark and production splits separate.
- Use conservative labels in any early training pass.
