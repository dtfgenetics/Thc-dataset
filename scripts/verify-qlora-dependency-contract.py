#!/usr/bin/env python3
"""Validate and intentionally regenerate the Grow Doc QLoRA dependency lock."""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "model_tuning/config/qlora_8b.yaml"
REQUIREMENTS = ROOT / "model_tuning/requirements.in"
LOCK_PATH = ROOT / "model_tuning/requirements.lock"
EXPECTED_RESOLVER = "uv==0.12.10"
EXPECTED_UV_PREFIX = "uv 0.12.10"
EXPECTED_LOCK_SHA = "ee386c57e5e3f969e849b0489ad9d171956bf229a80f012518966e887682243e"
EXPECTED_DIRECT = {
    "torch": "2.14.0",
    "transformers": "5.16.1",
    "peft": "0.20.0",
    "bitsandbytes": "0.50.2",
    "accelerate": "1.14.0",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def scalar(text: str, key: str) -> str | None:
    m = re.search(rf"(?m)^\s*{re.escape(key)}:\s*([^#\n]+?)\s*$", text)
    return m.group(1).strip().strip('"\'') if m else None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def direct_pins(path: Path = REQUIREMENTS) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)", line)
        if not m:
            raise ValueError(f"dependency must be exact-pinned: {line}")
        pins[m.group(1).lower().replace("_", "-")] = m.group(2)
    return pins


def validate() -> list[str]:
    errors: list[str] = []
    text = CONFIG.read_text(encoding="utf-8")
    input_path = scalar(text, "dependency_lock_input_path")
    resolver = scalar(text, "dependency_lock_resolver")
    lock_sha = scalar(text, "dependency_lock_sha256")
    if input_path != "model_tuning/requirements.in":
        errors.append("dependency_lock_input_path must be model_tuning/requirements.in")
    if resolver != EXPECTED_RESOLVER:
        errors.append(f"dependency_lock_resolver must be {EXPECTED_RESOLVER}")
    if lock_sha != EXPECTED_LOCK_SHA or not (lock_sha and HEX64.fullmatch(lock_sha)):
        errors.append("dependency_lock_sha256 does not match the reviewed CI lock")
    try:
        pins = direct_pins()
    except ValueError as exc:
        errors.append(str(exc))
        pins = {}
    if pins != EXPECTED_DIRECT:
        errors.append(f"direct dependency pins drifted: expected {EXPECTED_DIRECT}, got {pins}")
    return errors


def verify_uv() -> str:
    version = subprocess.check_output(["uv", "--version"], text=True).strip()
    if not (version == EXPECTED_UV_PREFIX or version.startswith(EXPECTED_UV_PREFIX + " (")):
        raise RuntimeError(f"expected uv 0.12.10, got {version!r}")
    return version


def compile_lock(output_path: Path) -> str:
    errors = validate()
    if errors:
        raise RuntimeError("; ".join(errors))
    verify_uv()
    output_path = output_path.resolve()
    if output_path.exists():
        raise RuntimeError(f"refusing to overwrite existing lock file: {output_path}")
    subprocess.run([
        "uv", "pip", "compile", "model_tuning/requirements.in",
        "--python-version", "3.12", "--generate-hashes", "--universal",
        "--output-file", str(output_path),
    ], cwd=ROOT, check=True)
    return sha256(output_path)


def materialize() -> str:
    """Legacy verification path for the historical reviewed lock digest.

    This intentionally deletes the temporary lock. New lock refreshes must use
    --generate-candidate-lock and go through review before the digest is changed.
    """
    actual = ""
    try:
        actual = compile_lock(LOCK_PATH)
        if actual != EXPECTED_LOCK_SHA:
            raise RuntimeError(f"dependency lock mismatch: expected {EXPECTED_LOCK_SHA}, got {actual}")
        return actual
    finally:
        LOCK_PATH.unlink(missing_ok=True)


def generate_candidate_lock(output_path: Path) -> str:
    """Generate a review candidate without pretending it matches the frozen digest."""
    if output_path.resolve() == LOCK_PATH.resolve():
        raise RuntimeError("candidate generation must not overwrite the canonical lock path")
    actual = compile_lock(output_path)
    print(f"candidate dependency lock generated: {output_path}")
    print(f"candidate dependency lock sha256: {actual}")
    print("REVIEW REQUIRED: do not update the frozen dependency digest until this file is reviewed and committed.")
    return actual


def self_test() -> None:
    assert not validate(), validate()
    assert direct_pins() == EXPECTED_DIRECT
    assert len(EXPECTED_LOCK_SHA) == 64
    assert EXPECTED_UV_PREFIX == "uv 0.12.10"
    assert "uv 0.12.10 (x86_64-unknown-linux-gnu)".startswith(EXPECTED_UV_PREFIX + " (")
    assert LOCK_PATH.name == "requirements.lock"
    candidate = ROOT / "model_tuning/requirements.lock.candidate"
    assert candidate.resolve() != LOCK_PATH.resolve()
    print("QLoRA dependency contract self-test: PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--materialize", action="store_true")
    p.add_argument("--generate-candidate-lock", type=Path)
    args = p.parse_args()
    requested = sum(bool(x) for x in (args.self_test, args.materialize, args.generate_candidate_lock))
    if requested > 1:
        p.error("choose only one action")
    if args.self_test:
        self_test(); return 0
    errors = validate()
    if errors:
        for error in errors: print(f"ERROR: {error}")
        return 1
    if args.generate_candidate_lock:
        generate_candidate_lock(args.generate_candidate_lock)
    elif args.materialize:
        digest = materialize()
        print(f"QLoRA dependency lock materialized and verified: {digest}")
    else:
        print("QLoRA dependency contract valid")
    return 0


if __name__ == "__main__": raise SystemExit(main())
