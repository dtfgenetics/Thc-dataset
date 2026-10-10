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

### Autonomous evidence review and publication

The project owner authorizes agents to complete routine research review, record
enrichment, reference-media review, validation, publication, and squash merge
without a separate human approval step. An agent may approve evidence-backed
content or reference display after checking the relevant source, diagnostic
scope, provenance, and item-level reuse rights. Record the evidence and checks
used for that decision; do not wait for a person solely to approve routine work.

Human verification is not a blanket prerequisite for maintaining this repository.
Existing human-review notes identify unresolved sample evidence, not a requirement
to ask the owner for permission before improving or publishing the dataset.
Agents should resolve those notes when documented evidence satisfies the relevant
criteria, or retain an unresolved classification with the exact missing evidence.
Agent review must not be recorded as an actual human, expert, or laboratory review.

Authorization does not establish missing scientific evidence or media permissions.
Keep species identification, causal attribution, training admission, and production
deployment tied to their documented evidence and validation contracts. Do not
mark unknown rights as permitted, unsupported diagnoses as confirmed, or failed
checks as passed merely to remove a blocker.

- Preserve provenance and licensing/source metadata.
- Do not silently replace canonical samples or labels to make a validator pass.
- Keep generated/derived artifacts distinguishable from canonical source data.
- Treat large-scale deduplication, deletion, relabeling, or provenance rewrites as destructive changes requiring explicit evidence and review.
- Never commit secrets, private user data, credentials, tokens, or `.env` files.

## Failure protocol

When CI or deployment fails, inspect the exact failed job and log first. Fix the root cause, rerun the relevant validation, and distinguish code/data failures from credentials, networking, or production-host failures. Do not repeatedly rerun the same failing production mutation without new evidence.
## Parallel chat/session contract

Every concurrent Grow Doc task must use a unique branch:

`work/grow-doc/<task>/<session-id>`

Separate chats/agents must not share one mutable branch. Start from current `main`, keep application/data/model changes in this canonical repository, and use one PR per session.

Before integration, run at least:

```bash
npm run check
npm test
npm run build
```

Dataset/model work must also preserve the relevant provenance/evaluation validators. If another session touches the same file, dataset slice, model-control artifact, or release package, continue development independently but reconcile that overlap before merge.

After merge, production integration must reference the exact validated canonical commit/artifact. Do not author a permanent fix in the `dtfgenetics/Thc` deployment copy.

## Contribution task claims

Before editing a canonical Grow Doc dataset/model slice, select an active task from `contributions/tasks.json` and record the session in `contributions/claims.json`. One active task may have only one session claim at a time. Blocked tasks cannot be claimed. The claim branch must follow `work/grow-doc/<task>/<session-id>`. Release the claim when the PR is merged/closed. Every data/model contribution should carry a receipt conforming to `contributions/receipt.schema.json`; RAG facts and evaluation cases must remain in their non-training lanes unless a separate reviewed promotion contract explicitly authorizes otherwise.
