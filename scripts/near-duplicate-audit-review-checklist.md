# Near-duplicate audit review checklist

Before merge:

- [ ] Exact branch head passes `Grow Doc Near-Duplicate Audit`.
- [ ] Auditor self-test passes.
- [ ] Standalone regression suite passes.
- [ ] Real training + held-out corpus audit is run without modifying source files.
- [ ] Flagged train/eval pairs are manually reviewed.
- [ ] Prompt and pair thresholds are calibrated from reviewed positives/negatives.
- [ ] Any threshold change adds regression fixtures.
- [ ] Provenance/source IDs remain present in review output.
- [ ] No automatic deletion is introduced.
