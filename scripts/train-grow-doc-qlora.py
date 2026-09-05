#!/usr/bin/env python3
"""Fail-closed QLoRA trainer for the Grow Doc model workstream.

This entrypoint is intentionally conservative:
- it regenerates and verifies the frozen supplied-claim-grounded dataset bytes;
- it verifies the real-run QLoRA contract and dependency-lock hash before loading weights;
- it pins the exact Qwen3 model/tokenizer revision and chat-template SHA;
- it trains only the adapter; no merge, model soup, promotion, or deployment occurs;
- checkpoint promotion remains external to this script.

Use --self-test for dependency-free CI validation. A real run requires CUDA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "model_tuning/config/qlora_8b.yaml"
LOCK = ROOT / "model_tuning/requirements.lock"
TRAIN_SFT = ROOT / "model_tuning/generated/splits/train_sft_v1.jsonl"
TRAIN_GQA = ROOT / "model_tuning/generated/splits/train_grounded_qa_mixture_v1.jsonl"
DEV_SFT = ROOT / "model_tuning/generated/splits/dev_sft_v1.jsonl"
DEV_GQA = ROOT / "model_tuning/generated/splits/dev_grounded_qa_v1.jsonl"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scalar(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*([^#\n]+?)\s*$", text)
    return match.group(1).strip().strip('"\'') if match else None


def list_items(text: str, key: str) -> list[str]:
    match = re.search(rf"(?ms)^\s{{2}}{re.escape(key)}:\s*\n((?:\s{{4}}-.*\n?)*)", text)
    if not match:
        return []
    return [line.split("-", 1)[1].strip() for line in match.group(1).splitlines() if "-" in line]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: expected JSON object")
        rows.append(row)
    return rows


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def ensure_clean_checkout() -> str:
    head = git_head()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    if dirty.strip():
        raise RuntimeError("real training requires a clean git checkout")
    if len(head) != 40 or any(c not in "0123456789abcdef" for c in head):
        raise RuntimeError("real training requires a full 40-character git revision")
    return head


def run_preflight() -> str:
    repo_revision = ensure_clean_checkout()
    subprocess.run([sys.executable, "scripts/freeze-model-training-artifacts.py"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "scripts/verify-qlora-artifacts.py"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "scripts/validate-qlora-config.py", "--real-run"], cwd=ROOT, check=True)
    text = CONFIG.read_text(encoding="utf-8")
    expected_lock_sha = scalar(text, "dependency_lock_sha256")
    lock_path = scalar(text, "dependency_lock_path")
    if not lock_path or not expected_lock_sha or not HEX64.fullmatch(expected_lock_sha):
        raise RuntimeError("dependency lock path/SHA must be pinned before real training")
    resolved = ROOT / lock_path
    if not resolved.exists():
        raise RuntimeError(f"dependency lock missing: {lock_path}")
    actual = sha256_file(resolved)
    if actual != expected_lock_sha:
        raise RuntimeError(f"dependency lock SHA mismatch: expected {expected_lock_sha}, got {actual}")
    return repo_revision


def load_runtime():
    try:
        import torch
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise RuntimeError("install the exact model_tuning/requirements.lock before a real run") from exc
    return torch, LoraConfig, get_peft_model, prepare_model_for_kbit_training, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer, TrainingArguments


@dataclass
class EncodedRecord:
    input_ids: list[int]
    attention_mask: list[int]
    labels: list[int]
    record_id: str


def encode_record(tokenizer, row: dict[str, Any], max_length: int) -> EncodedRecord:
    messages = row.get("messages") or []
    if not messages or messages[-1].get("role") != "assistant":
        raise ValueError(f"{row.get('id')}: final assistant message is required")
    if row.get("grounding_mode") != "supplied_claims_only_v1":
        raise ValueError(f"{row.get('id')}: unsanitized record refused")
    prompt_messages = messages[:-1]
    prompt = tokenizer.apply_chat_template(
        prompt_messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    full = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
        enable_thinking=False,
    )
    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    full_ids = tokenizer(full, add_special_tokens=False)["input_ids"]
    if len(full_ids) > max_length:
        raise ValueError(f"{row.get('id')}: {len(full_ids)} tokens exceeds max_seq_length={max_length}; do not silently truncate evidence/target")
    if len(prompt_ids) >= len(full_ids):
        raise ValueError(f"{row.get('id')}: no assistant target tokens after chat formatting")
    # Qwen chat templates should render the generation prompt as a byte/token prefix
    # of the full supervised conversation. Fail closed if a library change breaks it.
    if full_ids[: len(prompt_ids)] != prompt_ids:
        raise ValueError(f"{row.get('id')}: generation prompt tokens are not a prefix of supervised conversation")
    labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids) :]
    return EncodedRecord(full_ids, [1] * len(full_ids), labels, str(row.get("id")))


class EncodedDataset:
    def __init__(self, rows: list[EncodedRecord]):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        return {"input_ids": row.input_ids, "attention_mask": row.attention_mask, "labels": row.labels}


class Collator:
    def __init__(self, pad_token_id: int):
        self.pad_token_id = pad_token_id

    def __call__(self, features: list[dict[str, list[int]]]):
        import torch
        width = max(len(x["input_ids"]) for x in features)
        input_ids, attention_mask, labels = [], [], []
        for row in features:
            pad = width - len(row["input_ids"])
            input_ids.append(row["input_ids"] + [self.pad_token_id] * pad)
            attention_mask.append(row["attention_mask"] + [0] * pad)
            labels.append(row["labels"] + [-100] * pad)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "labels": torch.tensor(labels, dtype=torch.long),
        }


def train(output_dir: Path) -> None:
    repo_revision = run_preflight()
    runtime = load_runtime()
    torch, LoraConfig, get_peft_model, prepare_model_for_kbit_training, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer, TrainingArguments = runtime
    if not torch.cuda.is_available():
        raise RuntimeError("QLoRA real run requires CUDA; CPU fallback is intentionally disabled")

    config_text = CONFIG.read_text(encoding="utf-8")
    model_repo = scalar(config_text, "base_model")
    model_revision = scalar(config_text, "base_model_revision")
    tokenizer_revision = scalar(config_text, "tokenizer_revision")
    expected_template_sha = scalar(config_text, "tokenizer_chat_template_sha256")
    max_length = int(scalar(config_text, "max_seq_length") or "4096")
    seed = int(scalar(config_text, "seed") or "420")
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    tokenizer = AutoTokenizer.from_pretrained(model_repo, revision=tokenizer_revision)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    template_sha = hashlib.sha256(tokenizer.chat_template.encode("utf-8")).hexdigest()
    if template_sha != expected_template_sha:
        raise RuntimeError(f"runtime chat-template SHA mismatch: expected {expected_template_sha}, got {template_sha}")

    train_rows = load_jsonl(TRAIN_SFT) + load_jsonl(TRAIN_GQA)
    dev_rows = load_jsonl(DEV_SFT) + load_jsonl(DEV_GQA)
    if len(train_rows) != 180:
        raise RuntimeError(f"expected frozen 180-row training mixture, got {len(train_rows)}")
    qa_rows = sum(1 for row in train_rows if row.get("task") == "grounded_qa")
    if qa_rows != 36:
        raise RuntimeError(f"expected 36 grounded-QA training rows, got {qa_rows}")

    encoded_train = [encode_record(tokenizer, row, max_length) for row in train_rows]
    encoded_dev = [encode_record(tokenizer, row, max_length) for row in dev_rows]

    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_repo,
        revision=model_revision,
        quantization_config=quant,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora = LoraConfig(
        r=32,
        lora_alpha=64,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora)

    output_dir.mkdir(parents=True, exist_ok=True)
    args = TrainingArguments(
        output_dir=str(output_dir),
        learning_rate=1e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        num_train_epochs=2,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=16,
        gradient_checkpointing=True,
        max_grad_norm=1.0,
        weight_decay=0.01,
        optim="paged_adamw_8bit",
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=3,
        bf16=True,
        tf32=True,
        seed=seed,
        data_seed=seed,
        report_to=[],
        load_best_model_at_end=False,
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=EncodedDataset(encoded_train),
        eval_dataset=EncodedDataset(encoded_dev),
        data_collator=Collator(tokenizer.pad_token_id),
    )
    result = trainer.train()
    adapter_dir = output_dir / "adapter-final"
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    packages = {}
    for name in ("torch", "transformers", "peft", "bitsandbytes", "accelerate"):
        try:
            from importlib.metadata import version
            packages[name] = version(name)
        except Exception:
            packages[name] = "unknown"
    manifest = {
        "schema_version": "grow-doc-qlora-run-v1",
        "status": "trained_not_promoted",
        "promotion_eligible": False,
        "repo_revision": repo_revision,
        "base_model": model_repo,
        "base_model_revision": model_revision,
        "tokenizer_revision": tokenizer_revision,
        "tokenizer_chat_template_sha256": template_sha,
        "enable_thinking": False,
        "dependency_lock_sha256": sha256_file(LOCK),
        "training_split_manifest_sha256": scalar(config_text, "split_manifest_sha256"),
        "training_dataset_manifest_sha256": scalar(config_text, "dataset_manifest_sha256"),
        "train_rows": len(train_rows),
        "grounded_qa_train_rows": qa_rows,
        "dev_rows": len(dev_rows),
        "seed": seed,
        "packages": packages,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch_cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "train_metrics": result.metrics,
        "adapter_path": str(adapter_dir),
        "adapter_merge_performed": False,
        "deployment_performed": False,
        "next_gate": "external heldout_v2 evaluation and promotion scorer",
    }
    (output_dir / "training-run-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("QLoRA training completed; adapter is NOT promoted, merged, or deployed.")


def self_test() -> None:
    assert sha256_file(Path(__file__)).__len__() == 64
    assert scalar("x: abc\n", "x") == "abc"
    fake = {
        "id": "x",
        "grounding_mode": "supplied_claims_only_v1",
        "messages": [{"role": "user", "content": "u"}, {"role": "assistant", "content": "a"}],
    }
    assert fake["messages"][-1]["role"] == "assistant"
    assert TRAIN_SFT.name == "train_sft_v1.jsonl"
    assert TRAIN_GQA.name == "train_grounded_qa_mixture_v1.jsonl"
    print("Grow Doc QLoRA trainer self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("model_tuning/runs/qlora_qwen3_8b_v1"))
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.preflight_only:
        revision = run_preflight()
        print(f"QLoRA preflight passed at repo revision {revision}; no training was run.")
        return 0
    train(args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
