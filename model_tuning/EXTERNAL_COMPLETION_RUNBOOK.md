# Grow Doc external completion runbook

This runbook covers the four external blockers recorded in `model_tuning/project_completion_v1.json`. It does not authorize bypassing CI, training, promotion, or deployment.

## EXT-GOV-001 — protect main

Repository administration must enable branch protection or a repository ruleset for `main`.

Minimum required controls:
- require pull requests for changes to `main`;
- require the current Grow Doc validation/status checks before merge;
- prevent direct unreviewed pushes that bypass CI;
- retain workflow permissions needed for read-only validation and approved release operations.

After enabling protection, re-run the project completion audit and update the blocker only after GitHub reports protection/rulesets in effect.

## EXT-COMPUTE-001 — frozen Qwen3-8B base-vs-RAG benchmark

The self-hosted workflow is manual-only and accepts only an exact 40-character commit already reachable from `main`.

Prepare a dispatch:

```bash
python3 scripts/prepare-grow-doc-gpu-dispatch.py --commit-sha <MAIN_SHA> --run preflight
```

Run the emitted `gh workflow run` command. The target runner must satisfy labels `self-hosted, linux, x64, growdoc-gpu`, expose one CUDA GPU, support native BF16, and meet the pinned memory/runtime contract.

Only after preflight succeeds should the same exact commit be dispatched with `--run benchmark`.

Completion evidence must include:
- runner/preflight diagnostics;
- base and base+RAG run manifests;
- immutable artifact hashes;
- blinded review packet and reviewed scores;
- protected-slice decision output;
- experiment registry update.

Do not run QLoRA solely because compute is available. Retrieval is evaluated first.

## EXT-VISION-001 — supervised diagnostic vision

Start every candidate with:

`dataset/acquisition/supervised-vision-intake-template.json`

A copied intake record must remain `trainingEligible=false` until all required rights, scientific, annotation, grouping, hashing, duplicate/leakage, and class-coverage checks pass.

Required evidence includes:
- Cannabis/hemp host identity;
- source URL/local asset identity and SHA-256;
- perceptual hash;
- source group and plant/capture grouping;
- explicit training permission;
- diagnosis confirmation appropriate to the condition;
- human scientific/rights/annotation approval;
- exact and near-duplicate isolation;
- source-group split isolation;
- healthy controls, look-alike negatives, and class/video coverage thresholds.

Symptom-only imagery, cross-crop images, and rights-unknown media remain reference-only or excluded.

## EXT-DEPLOY-001 — verified production publication

Production deployment remains fail-closed until the four FTP secrets are restored privately in GitHub Actions. Never place credential values in source, logs, PRs, or issues.

The legacy manual fallback now accepts only an exact 40-character commit SHA already reachable from `main`. After credentials are restored, dispatch `.github/workflows/deploy-dtfseeds.yml` with that exact SHA. A successful deployment must build cleanly and publish `dist/deploy-version.txt`; verify the production path `/thc-grow-doc/deploy-version.txt` reports the expected commit before closing issue #95.

## Completion boundary

Until all four blockers are actually cleared, do not claim:
- RAG benchmark improvement;
- QLoRA training success;
- checkpoint superiority;
- adapter promotion or model-soup success;
- supervised vision readiness;
- deployment.
