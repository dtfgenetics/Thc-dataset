#!/usr/bin/env python3
"""Dependency-free loader for the reviewed Grow Doc QLoRA runtime contract.

This module is intentionally narrow: it parses only the top-level scalar values and
flat sections/lists used by model_tuning/config/qlora_8b.yaml. It exists so the real
trainer can consume the reviewed YAML contract directly without adding a second YAML
runtime dependency or duplicating hyperparameters in Python literals.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "model_tuning/config/qlora_8b.yaml"


class ContractError(RuntimeError):
    pass


def _strip_scalar(value: str) -> str:
    return value.strip().strip('"\'')


def top_level_values(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw or raw.startswith(" ") or raw.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*([^#]+?)\s*$", raw)
        if not match:
            continue
        key, value = match.group(1), _strip_scalar(match.group(2))
        if key in out:
            raise ContractError(f"duplicate top-level key: {key}")
        out[key] = value
    return out


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
        if not match:
            continue
        key, value = match.group(1), _strip_scalar(match.group(2))
        if key in values:
            raise ContractError(f"duplicate {section}.{key}")
        values[key] = value
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
            if in_list:
                raise ContractError(f"duplicate list declaration: {section}.{key}")
            in_list = True
            continue
        if in_list:
            match = re.match(r"^\s{4}-\s+(.+?)\s*$", raw)
            if match:
                value = _strip_scalar(match.group(1))
                if not value:
                    raise ContractError(f"empty list value in {section}.{key}")
                out.append(value)
                continue
            if raw.strip():
                break
    if len(out) != len(set(out)):
        raise ContractError(f"duplicate values in {section}.{key}")
    return out


def parse_bool(value: str, label: str) -> bool:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ContractError(f"{label} must be true or false")


def parse_int(value: str, label: str) -> int:
    if not re.fullmatch(r"[+-]?[0-9]+", value):
        raise ContractError(f"{label} must be an integer")
    return int(value)


def parse_float(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ContractError(f"{label} must be numeric") from exc
    if not math.isfinite(parsed):
        raise ContractError(f"{label} must be finite")
    return parsed


def require(mapping: dict[str, str], key: str, label: str) -> str:
    value = mapping.get(key)
    if value is None or value == "":
        raise ContractError(f"missing {label}")
    return value


@dataclass(frozen=True)
class QLoRARuntimeContract:
    base_model: str
    base_model_revision: str
    tokenizer_revision: str
    tokenizer_chat_template_sha256: str
    max_seq_length: int
    seed: int
    precision: dict[str, Any]
    lora: dict[str, Any]
    training: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "base_model": self.base_model,
            "base_model_revision": self.base_model_revision,
            "tokenizer_revision": self.tokenizer_revision,
            "tokenizer_chat_template_sha256": self.tokenizer_chat_template_sha256,
            "max_seq_length": self.max_seq_length,
            "seed": self.seed,
            "precision": dict(self.precision),
            "lora": dict(self.lora),
            "training": dict(self.training),
        }


def load_runtime_contract(text: str) -> QLoRARuntimeContract:
    top = top_level_values(text)
    precision_raw = section_values(text, "precision")
    lora_raw = section_values(text, "lora")
    training_raw = section_values(text, "training")
    targets = list_values(text, "lora", "target_modules")

    required_training = {
        "max_seq_length", "learning_rate", "lr_scheduler_type", "warmup_ratio",
        "num_train_epochs", "per_device_train_batch_size", "gradient_accumulation_steps",
        "gradient_checkpointing", "max_grad_norm", "weight_decay", "optimizer",
        "logging_steps", "eval_steps", "save_steps", "save_total_limit", "seed", "bf16",
        "tf32", "load_best_model_at_end", "metric_for_best_model", "greater_is_better",
        "checkpoint_selection",
    }
    missing = sorted(required_training - training_raw.keys())
    if missing:
        raise ContractError(f"missing training contract keys: {missing}")

    required_precision = {"load_in_4bit", "bnb_4bit_quant_type", "bnb_4bit_use_double_quant", "compute_dtype"}
    missing = sorted(required_precision - precision_raw.keys())
    if missing:
        raise ContractError(f"missing precision contract keys: {missing}")

    required_lora = {"r", "alpha", "dropout", "bias"}
    missing = sorted(required_lora - lora_raw.keys())
    if missing:
        raise ContractError(f"missing LoRA contract keys: {missing}")
    if not targets:
        raise ContractError("lora.target_modules must not be empty")

    training_seed = parse_int(training_raw["seed"], "training.seed")
    reproducibility = section_values(text, "reproducibility")
    reproducibility_seed = parse_int(require(reproducibility, "seed", "reproducibility.seed"), "reproducibility.seed")
    if training_seed != reproducibility_seed:
        raise ContractError("training.seed must match reproducibility.seed")

    precision = {
        "load_in_4bit": parse_bool(precision_raw["load_in_4bit"], "precision.load_in_4bit"),
        "bnb_4bit_quant_type": precision_raw["bnb_4bit_quant_type"],
        "bnb_4bit_use_double_quant": parse_bool(precision_raw["bnb_4bit_use_double_quant"], "precision.bnb_4bit_use_double_quant"),
        "compute_dtype": precision_raw["compute_dtype"],
    }
    lora = {
        "r": parse_int(lora_raw["r"], "lora.r"),
        "alpha": parse_int(lora_raw["alpha"], "lora.alpha"),
        "dropout": parse_float(lora_raw["dropout"], "lora.dropout"),
        "bias": lora_raw["bias"],
        "target_modules": targets,
    }
    training = {
        "learning_rate": parse_float(training_raw["learning_rate"], "training.learning_rate"),
        "lr_scheduler_type": training_raw["lr_scheduler_type"],
        "warmup_ratio": parse_float(training_raw["warmup_ratio"], "training.warmup_ratio"),
        "num_train_epochs": parse_float(training_raw["num_train_epochs"], "training.num_train_epochs"),
        "per_device_train_batch_size": parse_int(training_raw["per_device_train_batch_size"], "training.per_device_train_batch_size"),
        "gradient_accumulation_steps": parse_int(training_raw["gradient_accumulation_steps"], "training.gradient_accumulation_steps"),
        "gradient_checkpointing": parse_bool(training_raw["gradient_checkpointing"], "training.gradient_checkpointing"),
        "max_grad_norm": parse_float(training_raw["max_grad_norm"], "training.max_grad_norm"),
        "weight_decay": parse_float(training_raw["weight_decay"], "training.weight_decay"),
        "optimizer": training_raw["optimizer"],
        "logging_steps": parse_int(training_raw["logging_steps"], "training.logging_steps"),
        "eval_steps": parse_int(training_raw["eval_steps"], "training.eval_steps"),
        "save_steps": parse_int(training_raw["save_steps"], "training.save_steps"),
        "save_total_limit": parse_int(training_raw["save_total_limit"], "training.save_total_limit"),
        "bf16": parse_bool(training_raw["bf16"], "training.bf16"),
        "tf32": parse_bool(training_raw["tf32"], "training.tf32"),
        "load_best_model_at_end": parse_bool(training_raw["load_best_model_at_end"], "training.load_best_model_at_end"),
        "metric_for_best_model": training_raw["metric_for_best_model"],
        "greater_is_better": parse_bool(training_raw["greater_is_better"], "training.greater_is_better"),
        "checkpoint_selection": training_raw["checkpoint_selection"],
    }

    max_seq_length = parse_int(training_raw["max_seq_length"], "training.max_seq_length")
    if max_seq_length <= 0 or training_seed < 0:
        raise ContractError("max_seq_length must be positive and seed must be non-negative")
    if lora["r"] <= 0 or lora["alpha"] <= 0 or not 0 <= lora["dropout"] < 1:
        raise ContractError("LoRA rank/alpha must be positive and dropout must be in [0,1)")

    return QLoRARuntimeContract(
        base_model=require(top, "base_model", "base_model"),
        base_model_revision=require(top, "base_model_revision", "base_model_revision"),
        tokenizer_revision=require(top, "tokenizer_revision", "tokenizer_revision"),
        tokenizer_chat_template_sha256=require(top, "tokenizer_chat_template_sha256", "tokenizer_chat_template_sha256"),
        max_seq_length=max_seq_length,
        seed=training_seed,
        precision=precision,
        lora=lora,
        training=training,
    )


def self_test() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    contract = load_runtime_contract(text)
    assert contract.base_model == "Qwen/Qwen3-8B"
    assert contract.max_seq_length == 4096
    assert contract.seed == 420
    assert contract.precision == {
        "load_in_4bit": True,
        "bnb_4bit_quant_type": "nf4",
        "bnb_4bit_use_double_quant": True,
        "compute_dtype": "bfloat16",
    }
    assert contract.lora["r"] == 32
    assert contract.lora["alpha"] == 64
    assert contract.lora["target_modules"] == [
        "q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"
    ]
    assert contract.training["learning_rate"] == 0.0001
    assert contract.training["gradient_accumulation_steps"] == 16
    assert contract.training["metric_for_best_model"] == "eval_loss"

    changed = load_runtime_contract(text.replace("learning_rate: 0.0001", "learning_rate: 0.0002", 1))
    assert changed.training["learning_rate"] == 0.0002

    for bad_text, expected in [
        (text.replace("bf16: true", "bf16: maybe", 1), "training.bf16"),
        (text.replace("  seed: 420\n\nprecision:", "  seed: 421\n\nprecision:", 1), "training.seed must match"),
        (text.replace("    - down_proj", "    - q_proj\n    - down_proj", 1), "duplicate values"),
    ]:
        try:
            load_runtime_contract(bad_text)
        except ContractError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid runtime contract was accepted: {expected}")
    print("Grow Doc QLoRA runtime contract loader self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    contract = load_runtime_contract(CONFIG.read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps(contract.as_dict(), indent=2, sort_keys=True))
    else:
        print("Grow Doc QLoRA runtime contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
