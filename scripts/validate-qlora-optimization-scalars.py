#!/usr/bin/env python3
"""Fail closed on malformed Grow Doc QLoRA optimization scalars.

This validator is dependency-free and complements validate-qlora-config.py by
checking numeric types, finiteness, broad safety ranges, and seed consistency
before a training launcher can consume the configuration.
"""
from __future__ import annotations

import argparse
import math
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "model_tuning/config/qlora_8b.yaml"


def section(text: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(name)}:\s*\n(.*?)(?=^[A-Za-z_][A-Za-z0-9_]*:\s*(?:#.*)?$|\Z)",
        text,
    )
    return match.group(1) if match else ""


def scalar(block: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*([^#\n]+?)\s*$", block)
    return match.group(1).strip().strip('"\'') if match else None


def parse_int(value: str | None) -> int | None:
    if value is None or value.lower() in {"true", "false"}:
        return None
    if not re.fullmatch(r"[+-]?\d+", value):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_float(value: str | None) -> float | None:
    if value is None or value.lower() in {"true", "false"}:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def require_positive_int(errors: list[str], block: str, key: str, prefix: str) -> None:
    value = parse_int(scalar(block, key))
    if value is None or value <= 0:
        errors.append(f"{prefix}.{key} must be a positive integer")


def require_nonnegative_int(errors: list[str], block: str, key: str, prefix: str) -> None:
    value = parse_int(scalar(block, key))
    if value is None or value < 0:
        errors.append(f"{prefix}.{key} must be a non-negative integer")


def require_positive_float(errors: list[str], block: str, key: str, prefix: str, *, maximum: float | None = None) -> None:
    value = parse_float(scalar(block, key))
    if value is None or value <= 0 or (maximum is not None and value > maximum):
        suffix = f" and <= {maximum:g}" if maximum is not None else ""
        errors.append(f"{prefix}.{key} must be a finite number > 0{suffix}")


def require_fraction(errors: list[str], block: str, key: str, prefix: str, *, upper_inclusive: bool) -> None:
    value = parse_float(scalar(block, key))
    valid = value is not None and value >= 0 and (value <= 1 if upper_inclusive else value < 1)
    if not valid:
        comparator = "<= 1" if upper_inclusive else "< 1"
        errors.append(f"{prefix}.{key} must be a finite fraction >= 0 and {comparator}")


def validate_text(text: str) -> list[str]:
    errors: list[str] = []
    reproducibility = section(text, "reproducibility")
    lora = section(text, "lora")
    training = section(text, "training")

    require_nonnegative_int(errors, reproducibility, "seed", "reproducibility")

    require_positive_int(errors, lora, "r", "lora")
    require_positive_float(errors, lora, "alpha", "lora")
    require_fraction(errors, lora, "dropout", "lora", upper_inclusive=False)

    for key in (
        "max_seq_length",
        "per_device_train_batch_size",
        "gradient_accumulation_steps",
        "logging_steps",
        "eval_steps",
        "save_steps",
        "save_total_limit",
    ):
        require_positive_int(errors, training, key, "training")

    require_positive_float(errors, training, "learning_rate", "training", maximum=1.0)
    require_fraction(errors, training, "warmup_ratio", "training", upper_inclusive=False)
    require_positive_float(errors, training, "num_train_epochs", "training")
    require_positive_float(errors, training, "max_grad_norm", "training")

    weight_decay = parse_float(scalar(training, "weight_decay"))
    if weight_decay is None or weight_decay < 0 or weight_decay > 1:
        errors.append("training.weight_decay must be a finite number between 0 and 1")

    require_nonnegative_int(errors, training, "seed", "training")

    reproducibility_seed = parse_int(scalar(reproducibility, "seed"))
    training_seed = parse_int(scalar(training, "seed"))
    if (
        reproducibility_seed is not None
        and reproducibility_seed >= 0
        and training_seed is not None
        and training_seed >= 0
        and reproducibility_seed != training_seed
    ):
        errors.append("training.seed must match reproducibility.seed")

    return errors


def validate_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"config not found: {path}"]
    return validate_text(path.read_text(encoding="utf-8"))


def self_test() -> None:
    base = DEFAULT_CONFIG.read_text(encoding="utf-8")
    assert not validate_text(base), validate_text(base)

    cases = (
        ("r: 32", "r: true", "lora.r"),
        ("r: 32", "r: 0", "lora.r"),
        ("alpha: 64", "alpha: nan", "lora.alpha"),
        ("dropout: 0.05", "dropout: 1.0", "lora.dropout"),
        ("max_seq_length: 4096", "max_seq_length: 4096.5", "training.max_seq_length"),
        ("learning_rate: 0.0001", "learning_rate: inf", "training.learning_rate"),
        ("warmup_ratio: 0.05", "warmup_ratio: -0.01", "training.warmup_ratio"),
        ("num_train_epochs: 2", "num_train_epochs: false", "training.num_train_epochs"),
        ("per_device_train_batch_size: 1", "per_device_train_batch_size: 0", "training.per_device_train_batch_size"),
        ("gradient_accumulation_steps: 16", "gradient_accumulation_steps: true", "training.gradient_accumulation_steps"),
        ("max_grad_norm: 1.0", "max_grad_norm: 0", "training.max_grad_norm"),
        ("weight_decay: 0.01", "weight_decay: nan", "training.weight_decay"),
        ("eval_steps: 100", "eval_steps: 1.5", "training.eval_steps"),
        ("save_total_limit: 3", "save_total_limit: -1", "training.save_total_limit"),
        ("seed: 420", "seed: true", "seed"),
    )
    for old, new, expected in cases:
        tampered = base.replace(old, new, 1)
        assert tampered != base, f"self-test fixture failed to mutate {old}"
        errors = validate_text(tampered)
        assert any(expected in error for error in errors), (expected, errors)

    training_seed_tampered = base.replace(
        "  seed: 420\n  bf16: true",
        "  seed: 421\n  bf16: true",
        1,
    )
    assert training_seed_tampered != base, "self-test fixture failed to mutate training.seed"
    seed_errors = validate_text(training_seed_tampered)
    assert any("training.seed must match reproducibility.seed" in error for error in seed_errors), seed_errors

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "qlora.yaml"
        path.write_text(base, encoding="utf-8")
        assert not validate_file(path)
    print("QLoRA optimization scalar validator self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    errors = validate_file(args.config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"QLoRA optimization scalars valid: {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
