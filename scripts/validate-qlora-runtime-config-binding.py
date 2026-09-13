#!/usr/bin/env python3
"""Fail closed unless the real QLoRA trainer consumes the reviewed runtime contract.

The trainer no longer owns a second copy of the QLoRA/LoRA/TrainingArguments values.
This validator protects that architecture: the YAML is parsed by the typed contract,
runtime kwargs are derived by the tested mapping, and the real trainer must consume
those objects instead of reintroducing independent hyperparameter literals.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from qlora_runtime_contract import load_runtime_contract
from qlora_runtime_kwargs import runtime_kwargs

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "model_tuning/config/qlora_8b.yaml"
TRAINER = ROOT / "scripts/train-grow-doc-qlora.py"


def require(text: str, marker: str, label: str) -> None:
    if marker not in text:
        raise RuntimeError(
            f"QLoRA runtime/config binding failure: {label}; expected trainer marker {marker!r}"
        )


def reject(text: str, marker: str, label: str) -> None:
    if marker in text:
        raise RuntimeError(
            f"QLoRA runtime/config binding failure: {label}; legacy trainer literal {marker!r} returned"
        )


def validate(config_text: str, trainer_text: str) -> None:
    contract = load_runtime_contract(config_text)
    mapped = runtime_kwargs(contract)

    require(trainer_text, "from qlora_runtime_contract import load_runtime_contract", "typed contract import")
    require(trainer_text, "from qlora_runtime_kwargs import runtime_kwargs", "runtime mapping import")
    require(trainer_text, "contract = load_runtime_contract(config_text)", "typed contract load")
    require(trainer_text, "runtime_config = runtime_kwargs(contract)", "runtime kwargs derivation")

    for marker, label in [
        ("model_repo = contract.base_model", "base model binding"),
        ("model_revision = contract.base_model_revision", "base model revision binding"),
        ("tokenizer_revision = contract.tokenizer_revision", "tokenizer revision binding"),
        ("expected_template_sha = contract.tokenizer_chat_template_sha256", "chat-template digest binding"),
        ("max_length = contract.max_seq_length", "sequence-length binding"),
        ("seed = contract.seed", "seed binding"),
        ("enable_thinking = contract.tokenizer_chat_template_kwargs_enable_thinking", "thinking-mode binding"),
        ('BitsAndBytesConfig(**quantization_kwargs)', "quantization mapping consumption"),
        ('LoraConfig(**runtime_config["lora"])', "LoRA mapping consumption"),
        ('TrainingArguments(output_dir=str(output_dir), **runtime_config["training"])', "training mapping consumption"),
        ('use_gradient_checkpointing=runtime_config["training"]["gradient_checkpointing"]', "gradient-checkpointing binding"),
    ]:
        require(trainer_text, marker, label)

    require(
        trainer_text,
        'quantization_kwargs["bnb_4bit_compute_dtype"] = torch.bfloat16',
        "bfloat16 torch translation",
    )
    if mapped["quantization"]["bnb_4bit_compute_dtype"] != "bfloat16":
        raise RuntimeError("runtime mapping must preserve the reviewed bfloat16 sentinel")

    legacy_literals = [
        ("learning_rate=1e-4", "learning rate"),
        ('lr_scheduler_type="cosine"', "scheduler"),
        ("warmup_ratio=0.05", "warmup"),
        ("num_train_epochs=2", "epochs"),
        ("per_device_train_batch_size=1", "train batch size"),
        ("per_device_eval_batch_size=1", "eval batch size"),
        ("gradient_accumulation_steps=16", "gradient accumulation"),
        ("max_grad_norm=1.0", "max grad norm"),
        ("weight_decay=0.01", "weight decay"),
        ('optim="paged_adamw_8bit"', "optimizer"),
        ("save_total_limit=3", "checkpoint retention"),
        ("LoraConfig(r=32", "LoRA rank"),
        ('lora_alpha=64', "LoRA alpha"),
        ('lora_dropout=0.05', "LoRA dropout"),
        ('BitsAndBytesConfig(load_in_4bit=True', "4-bit quantization"),
    ]
    for marker, label in legacy_literals:
        reject(trainer_text, marker, label)


def self_test(config_text: str, trainer_text: str) -> None:
    validate(config_text, trainer_text)

    missing_mapping = trainer_text.replace(
        "runtime_config = runtime_kwargs(contract)",
        "runtime_config = {}",
    )
    if missing_mapping == trainer_text:
        raise AssertionError("self-test could not remove runtime kwargs derivation")
    try:
        validate(config_text, missing_mapping)
    except RuntimeError as exc:
        assert "runtime kwargs derivation" in str(exc)
    else:
        raise AssertionError("trainer without runtime kwargs derivation was accepted")

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
