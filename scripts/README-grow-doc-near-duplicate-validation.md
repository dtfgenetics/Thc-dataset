# Grow Doc near-duplicate validation command

Run the complete deterministic validation surface with:

```bash
python scripts/run-grow-doc-near-duplicate-validation.py
```

The runner compiles the auditor, executes its built-in contamination/self-test fixtures, and runs the standalone regression suite. GitHub Actions uses this same command so local and CI validation do not drift.
