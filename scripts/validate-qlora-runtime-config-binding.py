#!/usr/bin/env python3
"""Fail closed if the real QLoRA trainer drifts from qlora_8b.yaml.

The trainer currently spells out Transformers/PEFT arguments explicitly. Until it is
refactored to construct those objects directly from the YAML contract, this validator
makes that duplication machine-checked so a config-only or trainer-only edit cannot
silently change a real run.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "model_tuning/config/qlora_8b.yaml"
TRAINER = ROOT / "scripts/train-grow-doc-qlora.py"


def section_values(text: str, section: str) -> dict[str, str]:
    values: dict[str, str] = {}
    active = False
    for raw in text.splitlines():
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:\s*$", raw):
            active = raw.strip() == f"{section}:"
            continue
        if not active:
            continue
        if raw and not raw.startswith(" "):
            break
        match = re.match(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*):\s*([^#]+?)\s*$", raw)
        if match:
            values[match.group(1)] = match.group(2).strip().strip('"\'')
    return values


def list_values(text: str, section: str, key: str) -> list[str]:
    lines = text.splitlines()
    in_section = False
    in_list = False
    out: list[str] = []
    for raw in lines:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:\s*$", raw):
            in_section = raw.strip() == f"{section}:"
            in_list = False
            continue
        if not in_section:
            continue
        if re.match(rf"^\s{{2}}{re.escape(key)}:\s*$", raw):
            in_list = True
            continue
        if in_list:
            match = re.match(r"^\s{4}-\s+(.+?)\s*$", raw)
            if match:
                out.append(match.group(1).strip().strip('"\''))
                continue
            if raw.strip():
                break
    return out


def py_bool(value: str) -> str:
    lowered = value.lower()
    if lowered == "true":
        return "True"
    if lowered == "false":
        return "False"
    raise ValueError(f"expected YAML boolean, got {value!r}")


def require(text: str, marker: str, label: str) -> None:
    if marker not in text:
        raise RuntimeError(f"QLoRA runtime/config drift: {label}; expected trainer marker {marker!r}")


def validate(config_text: str, trainer_text: str) -> None:
    training = section_values(config_text, "training")
    precision = section_values(config_text, "precision")
    lora = section_values(config_text, "lora")
    targets = list_values(config_text, "lora", "target_modules")

    required_training = {
        "learning_rate", "lr_scheduler_type", "warmup_ratio", "num_train_epochs",
        "per_device_train_batch_size", "gradient_accumulation_steps",
        "gradient_checkpointing", "max_grad_norm", "weight_decay", "optimizer",
        "logging_steps", "eval_steps", "save_steps", "save_total_limit", "bf16",
        "tf32", "load_best_model_at_end",
    }
    missing = sorted(required_training - training.keys())
    if missing:
        raise RuntimeError(f"missing training contract keys: {missing}")

    require(trainer_text, f"learning_rate={training['learning_rate']}", "learning_rate")
    require(trainer_text, f"lr_scheduler_type=\"{training['lr_scheduler_type']}\"", "lr_scheduler_type")
    require(trainer_text, f"warmup_ratio={training['warmup_ratio']}", "warmup_ratio")
    require(trainer_text, f"num_train_epochs={training['num_train_epochs']}", "num_train_epochs")
    require(trainer_text, f"per_device_train_batch_size={training['per_device_train_batch_size']}", "per_device_train_batch_size")
    require(trainer_text, f"gradient_accumulation_steps={training['gradient_accumulation_steps']}", "gradient_accumulation_steps")
    require(trainer_text, f"gradient_checkpointing={py_bool(training['gradient_checkpointing'])}", "gradient_checkpointing")
    require(trainer_text, f"max_grad_norm={training['max_grad_norm']}", "max_grad_norm")
    require(trainer_text, f"weight_decay={training['weight_decay']}", "weight_decay")
    require(trainer_text, f"optim=\"{training['optimizer']}\"", "optimizer")
    require(trainer_text, f"logging_steps={training['logging_steps']}", "logging_steps")
    require(trainer_text, f"eval_steps={training['eval_steps']}", "eval_steps")
    require(trainer_text, f"save_steps={training['save_steps']}", "save_steps")
    require(trainer_text, f"save_total_limit={training['save_total_limit']}", "save_total_limit")
    require(trainer_text, f"bf16={py_bool(training['bf16'])}", "bf16")
    require(trainer_text, f"tf32={py_bool(training['tf32'])}", "tf32")
    require(trainer_text, f"load_best_model_at_end={py_bool(training['load_best_model_at_end'])}", "load_best_model_at_end")

    require(trainer_text, f"load_in_4bit={py_bool(precision['load_in_4bit'])}", "load_in_4bit")
    require(trainer_text, f"bnb_4bit_quant_type=\"{precision['bnb_4bit_quant_type']}\"", "bnb_4bit_quant_type")
    require(trainer_text, f"bnb_4bit_use_double_quant={py_bool(precision['bnb_4bit_use_double_quant'])}", "bnb_4bit_use_double_quant")
    if precision.get("compute_dtype") != "bfloat16":
        raise RuntimeError("validator currently supports only compute_dtype=bfloat16")
    require(trainer_text, "bnb_4bit_compute_dtype=torch.bfloat16", "compute_dtype")

    require(trainer_text, f"LoraConfig(r={lora['r']}", "LoRA rank")
    require(trainer_text, f"lora_alpha={lora['alpha']}", "LoRA alpha")
    require(trainer_text, f"lora_dropout={lora['dropout']}", "LoRA dropout")
    require(trainer_text, f"bias=\"{lora['bias']}\"", "LoRA bias")
    if not targets:
        raise RuntimeError("LoRA target_modules must not be empty")
    expected_targets = "target_modules=[" + ", ".join(f'\"{item}\"' for item in targets) + "]"
    require(trainer_text, expected_targets, "LoRA target_modules")


def self_test(config_text: str, trainer_text: str) -> None:
    validate(config_text, trainer_text)
    bad_trainer = trainer_text.replace("learning_rate=1e-4", "learning_rate=2e-4", 1)
    try:
        validate(config_text, bad_trainer)
    except RuntimeError as exc:
        assert "learning_rate" in str(exc)
    else:
        raise AssertionError("learning-rate drift was not rejected")

    bad_config = config_text.replace("r: 32", "r: 16", 1)
    try:
        validate(bad_config, trainer_text)
    except RuntimeError as exc:
        assert "LoRA rank" in str(exc)
    else:
        raise AssertionError("LoRA-rank drift was not rejected")
    print("Grow Doc QLoRA runtime/config binding self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    config_text = CONFIG.read_text(encoding="utf-8")
    trainer_text = TRAINER.read_text(encoding="utf-8")
    if args.self_test:
        self_test(config_text, trainer_text)
    else:
        validate(config_text, trainer_text)
        print("Grow Doc QLoRA runtime/config binding: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
