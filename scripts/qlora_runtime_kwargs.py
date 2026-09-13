#!/usr/bin/env python3
"""Derive QLoRA runtime kwargs from the reviewed typed contract.

This module is dependency-free and intentionally does not import torch, transformers,
or peft. The real trainer can translate the compute-dtype sentinel to torch.bfloat16
at runtime. Keeping this mapping pure makes config-to-runtime semantics testable before
GPU training is attempted.
"""
from __future__ import annotations

from typing import Any

from qlora_runtime_contract import QLoRARuntimeContract


def runtime_kwargs(contract: QLoRARuntimeContract) -> dict[str, dict[str, Any]]:
    if contract.packing:
        raise ValueError("Grow Doc trainer does not support packed examples; packing must remain false")
    if contract.precision["compute_dtype"] != "bfloat16":
        raise ValueError("Grow Doc QLoRA runtime currently requires bfloat16 compute")
    if contract.training["checkpoint_selection"] != "dev_eval_loss_then_external_heldout_promotion_gate":
        raise ValueError("unsupported checkpoint-selection contract")

    quantization = {
        "load_in_4bit": contract.precision["load_in_4bit"],
        "bnb_4bit_quant_type": contract.precision["bnb_4bit_quant_type"],
        "bnb_4bit_use_double_quant": contract.precision["bnb_4bit_use_double_quant"],
        "bnb_4bit_compute_dtype": contract.precision["compute_dtype"],
    }
    lora = {
        "r": contract.lora["r"],
        "lora_alpha": contract.lora["alpha"],
        "lora_dropout": contract.lora["dropout"],
        "bias": contract.lora["bias"],
        "task_type": "CAUSAL_LM",
        "target_modules": list(contract.lora["target_modules"]),
    }
    t = contract.training
    training = {
        "learning_rate": t["learning_rate"],
        "lr_scheduler_type": t["lr_scheduler_type"],
        "warmup_ratio": t["warmup_ratio"],
        "num_train_epochs": t["num_train_epochs"],
        "per_device_train_batch_size": t["per_device_train_batch_size"],
        "per_device_eval_batch_size": t["per_device_eval_batch_size"],
        "gradient_accumulation_steps": t["gradient_accumulation_steps"],
        "gradient_checkpointing": t["gradient_checkpointing"],
        "max_grad_norm": t["max_grad_norm"],
        "weight_decay": t["weight_decay"],
        "optim": t["optimizer"],
        "logging_steps": t["logging_steps"],
        "eval_strategy": "steps",
        "eval_steps": t["eval_steps"],
        "save_strategy": "steps",
        "save_steps": t["save_steps"],
        "save_total_limit": t["save_total_limit"],
        "bf16": t["bf16"],
        "tf32": t["tf32"],
        "seed": contract.seed,
        "data_seed": contract.seed,
        "report_to": [],
        "load_best_model_at_end": t["load_best_model_at_end"],
        "metric_for_best_model": t["metric_for_best_model"],
        "greater_is_better": t["greater_is_better"],
        "remove_unused_columns": False,
    }
    return {"quantization": quantization, "lora": lora, "training": training}


def self_test() -> None:
    from pathlib import Path
    from qlora_runtime_contract import load_runtime_contract

    root = Path(__file__).resolve().parents[1]
    contract = load_runtime_contract((root / "model_tuning/config/qlora_8b.yaml").read_text(encoding="utf-8"))
    kwargs = runtime_kwargs(contract)
    assert kwargs["quantization"] == {
        "load_in_4bit": True,
        "bnb_4bit_quant_type": "nf4",
        "bnb_4bit_use_double_quant": True,
        "bnb_4bit_compute_dtype": "bfloat16",
    }
    assert kwargs["lora"]["r"] == 32
    assert kwargs["lora"]["lora_alpha"] == 64
    assert kwargs["lora"]["lora_dropout"] == 0.05
    assert kwargs["training"]["learning_rate"] == 0.0001
    assert kwargs["training"]["per_device_train_batch_size"] == 1
    assert kwargs["training"]["per_device_eval_batch_size"] == 1
    assert kwargs["training"]["gradient_accumulation_steps"] == 16
    assert kwargs["training"]["seed"] == kwargs["training"]["data_seed"] == 420
    assert kwargs["training"]["metric_for_best_model"] == "eval_loss"
    assert kwargs["training"]["greater_is_better"] is False
    assert kwargs["training"]["report_to"] == []
    print("Grow Doc QLoRA runtime kwargs self-test: PASS")


if __name__ == "__main__":
    self_test()
