#!/usr/bin/env python3
"""Fail closed when the Grow Doc QLoRA packing config and trainer disagree.

The current trainer encodes each conversation independently, pads only within a batch,
and does not implement sequence packing. Keeping packing disabled preserves explicit
example boundaries and prevents the configuration from claiming an optimization that
the runtime does not perform.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "model_tuning/config/qlora_8b.yaml"
TRAINER = ROOT / "scripts/train-grow-doc-qlora.py"


def training_section(text: str) -> str:
    match = re.search(r"(?ms)^training:\s*\n(.*?)(?=^[A-Za-z_][A-Za-z0-9_]*:\s*(?:#.*)?$|\Z)", text)
    return match.group(1) if match else ""


def scalar(block: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*([^#\n]+?)\s*$", block)
    return match.group(1).strip().strip('"\'') if match else None


def validate(config_text: str, trainer_text: str) -> list[str]:
    errors: list[str] = []
    packing = scalar(training_section(config_text), "packing")
    if packing != "false":
        errors.append("training.packing must be false until the trainer implements and tests explicit sequence packing")

    required_runtime_markers = (
        "encoded_train = [encode_record(tokenizer, row, max_length) for row in train_rows]",
        "train_dataset=EncodedDataset(encoded_train)",
        "data_collator=Collator(tokenizer.pad_token_id)",
    )
    for marker in required_runtime_markers:
        if marker not in trainer_text:
            errors.append(f"trainer packing contract marker missing: {marker}")

    forbidden_markers = ("packing=True", "packing = True", "packing=true")
    for marker in forbidden_markers:
        if marker in trainer_text:
            errors.append(f"trainer unexpectedly enables packing: {marker}")
    return errors


def self_test() -> None:
    config = CONFIG.read_text(encoding="utf-8")
    trainer = TRAINER.read_text(encoding="utf-8")
    assert not validate(config, trainer), validate(config, trainer)

    tampered = config.replace("packing: false", "packing: true", 1)
    assert any("packing must be false" in error for error in validate(tampered, trainer))

    tampered_trainer = trainer.replace("train_dataset=EncodedDataset(encoded_train)", "train_dataset=packed_train", 1)
    assert any("trainer packing contract marker missing" in error for error in validate(config, tampered_trainer))
    print("QLoRA packing contract self-test: PASS")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0

    errors = validate(CONFIG.read_text(encoding="utf-8"), TRAINER.read_text(encoding="utf-8"))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("QLoRA packing contract: PASS (packing disabled; per-example trainer semantics verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
