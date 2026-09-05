#!/usr/bin/env python3
"""Run the first controlled Grow Doc base-only vs frozen-RAG experiment.

This wrapper intentionally does not fine-tune or merge anything. It prepares the
same immutable benchmark/retrieval inputs, verifies the exact model runtime contract,
invokes the same pinned Qwen3-8B revision twice, and leaves both arms pending review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_REPO = "Qwen/Qwen3-8B"
MODEL_REVISION = "b968826d9c46dd6066d109eabc6255188de91218"
TOKENIZER_REVISION = MODEL_REVISION
CHAT_TEMPLATE_SHA256 = "a55ee1b1660128b7098723e0abcd92caa0788061051c62d51cbe87d9cf1974d8"
DEPENDENCY_LOCK_SHA256 = "ee386c57e5e3f969e849b0489ad9d171956bf229a80f012518966e887682243e"
BENCHMARK = "model_tuning/eval/heldout_v2.jsonl"
RAG_SNAPSHOT = "model_tuning/rag_snapshots/heldout_v2.jsonl"
RAG_MANIFEST = "model_tuning/rag_snapshots/heldout_v2.manifest.json"
REQUIREMENTS = ROOT / "model_tuning/requirements.in"
DIRECT_PACKAGES = ("torch", "transformers", "peft", "bitsandbytes", "accelerate")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(root: Path = ROOT) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def ensure_clean_checkout(root: Path = ROOT) -> str:
    head = git_head(root)
    if len(head) != 40 or any(c not in "0123456789abcdef" for c in head.lower()):
        raise RuntimeError("experiment requires a full 40-character git commit SHA")
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True)
    if dirty.strip():
        raise RuntimeError("experiment requires a clean git checkout")
    return head


def direct_requirements(path: Path = REQUIREMENTS) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise RuntimeError(f"runtime dependency must be exact-pinned: {line}")
        name, pinned = line.split("==", 1)
        if not name or not pinned:
            raise RuntimeError(f"invalid exact dependency pin: {line}")
        pins[name.lower().replace("_", "-")] = pinned
    return pins


def verify_installed_runtime() -> dict[str, str]:
    expected = direct_requirements()
    actual: dict[str, str] = {}
    for name in DIRECT_PACKAGES:
        key = name.lower().replace("_", "-")
        want = expected.get(key)
        if not want:
            raise RuntimeError(f"missing exact runtime pin for {name}")
        try:
            got = package_version(name)
        except PackageNotFoundError as exc:
            raise RuntimeError(f"required evaluation package is not installed: {name}=={want}") from exc
        if got != want:
            raise RuntimeError(f"evaluation runtime mismatch for {name}: expected {want}, got {got}")
        actual[name] = got
    return actual


def verify_dependency_contract() -> str:
    try:
        subprocess.check_output(["uv", "--version"], text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("uv==0.12.10 is required for the evaluation dependency preflight") from exc
    completed = subprocess.run(
        [sys.executable, "scripts/verify-qlora-dependency-contract.py", "--materialize"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    if DEPENDENCY_LOCK_SHA256 not in completed.stdout:
        raise RuntimeError("dependency verifier did not confirm the pinned lock SHA")
    return DEPENDENCY_LOCK_SHA256


def runtime_preflight() -> dict[str, object]:
    lock_sha = verify_dependency_contract()
    packages = verify_installed_runtime()
    return {"dependency_lock_sha256": lock_sha, "packages": packages}


def common_eval_args(repo_revision: str, output_dir: Path, run_id: str) -> list[str]:
    return [
        sys.executable,
        str(ROOT / "scripts/run-model-eval.py"),
        "--benchmark", BENCHMARK,
        "--model-repo", MODEL_REPO,
        "--model-revision", MODEL_REVISION,
        "--tokenizer-repo", MODEL_REPO,
        "--tokenizer-revision", TOKENIZER_REVISION,
        "--tokenizer-chat-template-sha256", CHAT_TEMPLATE_SHA256,
        "--disable-thinking",
        "--dtype", "bfloat16",
        "--temperature", "0.0",
        "--top-p", "1.0",
        "--max-new-tokens", "512",
        "--seed", "420",
        "--scorer-revision", repo_revision,
        "--output-dir", str(output_dir),
        "--run-id", run_id,
    ]


def prepare_inputs() -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts/freeze-model-training-artifacts.py")], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/verify-qlora-artifacts.py")], cwd=ROOT, check=True)
    subprocess.run([
        sys.executable,
        str(ROOT / "scripts/build-rag-eval-snapshot.py"),
        "--claims", "model_tuning/generated/rag/claims_v1.jsonl",
        "--benchmark", BENCHMARK,
        "--output", RAG_SNAPSHOT,
        "--manifest", RAG_MANIFEST,
        "--top-k", "5",
    ], cwd=ROOT, check=True)


def run_preflight() -> dict[str, object]:
    repo_revision = ensure_clean_checkout()
    runtime_contract = runtime_preflight()
    prepare_inputs()
    return {"repo_revision": repo_revision, **runtime_contract}


def run_experiment(output_root: Path) -> Path:
    preflight = run_preflight()
    repo_revision = str(preflight["repo_revision"])
    output_root.mkdir(parents=True, exist_ok=True)

    base_dir = output_root / "base_only"
    rag_dir = output_root / "base_plus_rag"
    subprocess.run(common_eval_args(repo_revision, base_dir, "qwen3-8b-base-heldout-v2"), cwd=ROOT, check=True)
    rag_cmd = common_eval_args(repo_revision, rag_dir, "qwen3-8b-base-rag-heldout-v2") + [
        "--retrieval-snapshot", RAG_SNAPSHOT,
        "--retrieval-manifest", RAG_MANIFEST,
    ]
    subprocess.run(rag_cmd, cwd=ROOT, check=True)

    base_run = json.loads((base_dir / "run-manifest.json").read_text(encoding="utf-8"))
    rag_run = json.loads((rag_dir / "run-manifest.json").read_text(encoding="utf-8"))
    if base_run.get("runtime") != rag_run.get("runtime"):
        raise RuntimeError("base and RAG arms used different recorded runtime environments")

    manifest = {
        "schema_version": "grow-doc-base-vs-rag-experiment-v2",
        "status": "pending_review",
        "promotion_eligible": False,
        "repo_revision": repo_revision,
        "model": {"repository": MODEL_REPO, "revision": MODEL_REVISION},
        "tokenizer": {
            "revision": TOKENIZER_REVISION,
            "chat_template_sha256": CHAT_TEMPLATE_SHA256,
            "enable_thinking": False,
        },
        "runtime_contract": {
            "dependency_lock_sha256": preflight["dependency_lock_sha256"],
            "direct_packages": preflight["packages"],
            "both_arms_runtime_identical": True,
        },
        "decoding": {"do_sample": False, "temperature": 0.0, "top_p": 1.0, "max_new_tokens": 512, "seed": 420},
        "benchmark": {"path": BENCHMARK, "sha256": sha256(ROOT / BENCHMARK)},
        "retrieval": {
            "snapshot_path": RAG_SNAPSHOT,
            "snapshot_sha256": sha256(ROOT / RAG_SNAPSHOT),
            "manifest_path": RAG_MANIFEST,
            "manifest_sha256": sha256(ROOT / RAG_MANIFEST),
        },
        "arms": {
            "base_only": {
                "responses_sha256": sha256(base_dir / "responses.jsonl"),
                "run_manifest_sha256": sha256(base_dir / "run-manifest.json"),
            },
            "base_plus_rag": {
                "responses_sha256": sha256(rag_dir / "responses.jsonl"),
                "run_manifest_sha256": sha256(rag_dir / "run-manifest.json"),
            },
        },
    }
    out = output_root / "experiment-manifest.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"experiment manifest: {out}")
    print("Raw comparison complete; human/scorer review is still required before any promotion claim.")
    return out


def self_test() -> None:
    assert len(MODEL_REVISION) == 40
    assert len(CHAT_TEMPLATE_SHA256) == 64
    assert len(DEPENDENCY_LOCK_SHA256) == 64
    pins = direct_requirements()
    assert pins["torch"] == "2.14.0"
    assert pins["transformers"] == "5.16.1"
    cmd = common_eval_args("a" * 40, Path("out"), "test-run")
    assert "--disable-thinking" in cmd
    assert "--do-sample" not in cmd
    assert cmd[cmd.index("--model-revision") + 1] == MODEL_REVISION
    assert cmd[cmd.index("--tokenizer-chat-template-sha256") + 1] == CHAT_TEMPLATE_SHA256
    assert cmd[cmd.index("--scorer-revision") + 1] == "a" * 40
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        p = root / "x"
        p.write_bytes(b"grow-doc")
        assert sha256(p) == hashlib.sha256(b"grow-doc").hexdigest()
    print("base-vs-RAG experiment launcher self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--output-root", type=Path, default=Path("model_tuning/runs/base_vs_rag_v1"))
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.preflight_only:
        result = run_preflight()
        print(json.dumps({"status": "ready_for_inference", **result}, sort_keys=True))
        print("No model inference, training, adapter merge, or deployment was run.")
        return 0
    run_experiment(args.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
