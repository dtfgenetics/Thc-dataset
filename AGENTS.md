# Repository agent instructions

These instructions apply to the entire `dtfgenetics/Thc-dataset` repository.

## Repository role

This repository is the canonical source for the THC Grow Doc application and its diagnostic/training dataset. Keep application code, dataset provenance, source validation, acquisition/transfer controls, and Grow Doc build logic here.

The current whole-site production orchestration and route-ownership authority for `dtfseeds.com` lives in `dtfgenetics/Thc`. Do not treat this repository as authority for unrelated WordPress pages, genetics pages, games, or other site routes.

## Validation first

Before merging source or dataset changes, use the existing CI contract in `.github/workflows/ci.yml`. At minimum, preserve the source/acquisition/transfer validators, type checks, tests, PHP proxy lint, and production build.

A successful build or repository commit is not proof that `https://dtfseeds.com/thc-grow-doc/` changed.

## Production deployment

`.github/workflows/deploy-dtfseeds.yml` is a production mutation lane and must remain explicit/manual unless a reviewed deployment-ownership decision replaces this rule.

Before any production write:

1. Confirm the requested change belongs to `/thc-grow-doc/`.
2. Confirm the exact source commit has passed repository validation.
3. Use protected credentials; never print, copy, or commit them.
4. Preserve existing remote files unless the deployment plan explicitly requires replacement.
5. Verify the visitor-facing `/thc-grow-doc/` route after deployment before reporting the change live.

If deployment credentials are unavailable, report the deployment as blocked; do not weaken validation or invent credential values.

## Dataset safety

- Preserve provenance and licensing/source metadata.
- Do not silently replace canonical samples or labels to make a validator pass.
- Keep generated/derived artifacts distinguishable from canonical source data.
- Treat large-scale deduplication, deletion, relabeling, or provenance rewrites as destructive changes requiring explicit evidence and review.
- Never commit secrets, private user data, credentials, tokens, or `.env` files.

## Failure protocol

When CI or deployment fails, inspect the exact failed job and log first. Fix the root cause, rerun the relevant validation, and distinguish code/data failures from credentials, networking, or production-host failures. Do not repeatedly rerun the same failing production mutation without new evidence.
