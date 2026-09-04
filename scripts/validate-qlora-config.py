#!/usr/bin/env python3
"""Validate the Grow Doc QLoRA training contract before any real training run.

Dependency-free by design so CI can catch configuration drift without installing
Transformers/PEFT/bitsandbytes. This validates repository policy and internal
consistency; it does not claim that a GPU training environment is available.
"""
from __future__ import annotations

import argparse
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "model_tuning/config/qlora_8b.yaml"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def scalar(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*([^#\n]+?)\s*$", text)
    return match.group(1).strip().strip('"\'') if match else None


def section(text: str, name: str) -> str:
    match = re.search(rf"(?ms)^{re.escape(name)}:\s*\n(.*?)(?=^[A-Za-z_][A-Za-z0-9_]*:\s*(?:#.*)?$|\Z)", text)
    return match.group(1) if match else ""


def list_items(block: str, key: str) -> list[str]:
    match = re.search(rf"(?ms)^\s{{2}}{re.escape(key)}:\s*\n((?:\s{{4}}-.*\n?)*)", block)
    if not match:
        return []
    return [line.split("-", 1)[1].strip() for line in match.group(1).splitlines() if "-" in line]


def bool_value(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def float_value(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def validate_text(text: str, *, allow_placeholders: bool = True) -> list[str]:
    errors: list[str] = []

    base_model = scalar(text, "base_model")
    base_revision = scalar(text, "base_model_revision")
    tokenizer_revision = scalar(text, "tokenizer_revision")
    if not base_model:
        errors.append("base_model is required")
    if not base_revision:
        errors.append("base_model_revision is required")
    elif base_revision == "PIN_BEFORE_TRAINING" and not allow_placeholders:
        errors.append("base_model_revision must be pinned before a real training run")
    if not tokenizer_revision:
        errors.append("tokenizer_revision is required")
    elif tokenizer_revision == "PIN_BEFORE_TRAINING" and not allow_placeholders:
        errors.append("tokenizer_revision must be pinned before a real training run")

    reproducibility = section(text, "reproducibility")
    precision = section(text, "precision")
    training_data = section(text, "training_data")
    training = section(text, "training")
    evaluation = section(text, "evaluation")
    merge_policy = section(text, "merge_policy")
    rag = section(text, "rag")
    lora = section(text, "lora")

    for key in (
        "require_pinned_base_revision",
        "require_pinned_dependency_lock",
        "require_dataset_manifest_hash",
        "require_split_manifest_hash",
        "require_tokenizer_revision_pin",
        "record_cuda_and_gpu",
    ):
        if bool_value(scalar(reproducibility, key)) is not True:
            errors.append(f"reproducibility.{key} must be true")

    if bool_value(scalar(precision, "load_in_4bit")) is not True:
        errors.append("QLoRA contract requires precision.load_in_4bit: true")
    if scalar(precision, "bnb_4bit_quant_type") != "nf4":
        errors.append("QLoRA contract requires NF4 quantization")
    if scalar(precision, "compute_dtype") != "bfloat16":
        errors.append("starter 8B contract requires bfloat16 compute dtype")
    if bool_value(scalar(training, "bf16")) is not True:
        errors.append("training.bf16 must match bfloat16 compute dtype")

    path_keys = (
        "sft_path",
        "dev_sft_path",
        "grounded_qa_path",
        "grounded_qa_dev_path",
        "split_manifest_path",
        "dataset_manifest_path",
        "retrieval_path",
        "quarantine_path",
    )
    path_values = {key: scalar(training_data, key) for key in path_keys}
    heldout_path = scalar(evaluation, "heldout_path")
    for key, value in path_values.items():
        if not value:
            errors.append(f"training_data.{key} is required")

    populated = [value for value in path_values.values() if value] + ([heldout_path] if heldout_path else [])
    if len(populated) != len(set(populated)):
        errors.append("train/dev/retrieval/quarantine/manifest/held-out paths must be distinct")

    expected_path_fragments = {
        "sft_path": "/splits/train_sft_",
        "dev_sft_path": "/splits/dev_sft_",
        "grounded_qa_path": "/splits/train_grounded_qa_",
        "grounded_qa_dev_path": "/splits/dev_grounded_qa_",
    }
    for key, fragment in expected_path_fragments.items():
        value = path_values[key]
        if value and fragment not in value:
            errors.append(f"training_data.{key} must use the source-component {fragment.split('/')[-1]} lane")

    grounded_qa_max_fraction = float_value(scalar(training_data, "grounded_qa_max_fraction"))
    if grounded_qa_max_fraction is None:
        errors.append("training_data.grounded_qa_max_fraction must be numeric")
    elif not (0.0 < grounded_qa_max_fraction <= 0.20):
        errors.append("grounded QA fraction must be greater than 0 and capped at 0.20")

    for key in (
        "train_only_grounded_examples",
        "require_context_required",
        "preserve_source_ids",
        "require_source_component_split",
        "forbid_quarantine_training",
        "forbid_eval_training_leakage",
    ):
        if bool_value(scalar(training_data, key)) is not True:
            errors.append(f"training_data.{key} must be true")

    for hash_key in ("split_manifest_sha256", "dataset_manifest_sha256"):
        value = scalar(training_data, hash_key)
        if not value:
            errors.append(f"training_data.{hash_key} is required")
        elif value == "MATERIALIZE_BEFORE_TRAINING":
            if not allow_placeholders:
                errors.append(f"training_data.{hash_key} must be an immutable SHA-256 before a real training run")
        elif not HEX64.fullmatch(value):
            errors.append(f"training_data.{hash_key} must be a lowercase 64-character SHA-256")

    if bool_value(scalar(rag, "preferred_for_factual_knowledge")) is not True:
        errors.append("rag.preferred_for_factual_knowledge must be true")
    if bool_value(scalar(rag, "require_source_metadata")) is not True:
        errors.append("rag.require_source_metadata must be true")
    if bool_value(scalar(rag, "require_claim_limitations")) is not True:
        errors.append("rag.require_claim_limitations must be true")

    if bool_value(scalar(merge_policy, "allow_adapter_merge")) is not False:
        errors.append("adapter merge must remain locked before measured promotion")
    if scalar(merge_policy, "unlock_condition") != "measured_multi_slice_improvement":
        errors.append("adapter merge unlock condition must require measured multi-slice improvement")
    if bool_value(scalar(merge_policy, "reject_if_any_critical_slice_regresses")) is not True:
        errors.append("critical-slice regression rejection must remain enabled")

    if bool_value(scalar(training, "load_best_model_at_end")) is not False:
        errors.append("load_best_model_at_end must stay false until in-training eval integration exists")
    if scalar(training, "checkpoint_selection") != "external_heldout_promotion_gate":
        errors.append("training.checkpoint_selection must use the external held-out promotion gate")

    targets = set(list_items(lora, "target_modules"))
    required_targets = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}
    missing_targets = sorted(required_targets - targets)
    if missing_targets:
        errors.append("missing LoRA target modules: " + ", ".join(missing_targets))

    required_slices = set(list_items(evaluation, "required_slices"))
    for critical in ("factuality", "diagnostic", "hallucination", "citation_accuracy", "regression", "grounded_qa"):
        if critical not in required_slices:
            errors.append(f"evaluation.required_slices missing {critical}")

    return errors


def validate_file(path: Path, *, allow_placeholders: bool = True) -> list[str]:
    if not path.exists():
        return [f"config not found: {path}"]
    return validate_text(path.read_text(encoding="utf-8"), allow_placeholders=allow_placeholders)


def self_test() -> None:
    base = DEFAULT_CONFIG.read_text(encoding="utf-8")
    assert not validate_text(base), validate_text(base)

    tampered = base.replace("allow_adapter_merge: false", "allow_adapter_merge: true")
    assert any("adapter merge" in error for error in validate_text(tampered))

    tampered = base.replace("grounded_qa_max_fraction: 0.20", "grounded_qa_max_fraction: 0.50")
    assert any("grounded QA fraction" in error for error in validate_text(tampered))

    tampered = base.replace("require_source_component_split: true", "require_source_component_split: false")
    assert any("source_component_split" in error for error in validate_text(tampered))

    tampered = base.replace("load_best_model_at_end: false", "load_best_model_at_end: true")
    assert any("load_best_model_at_end" in error for error in validate_text(tampered))

    tampered = base.replace(
        "grounded_qa_path: model_tuning/generated/splits/train_grounded_qa_v1.jsonl",
        "grounded_qa_path: model_tuning/generated/splits/train_sft_v1.jsonl",
    )
    assert any("grounded_qa_path" in error or "must be distinct" in error for error in validate_text(tampered))

    real_run_errors = validate_text(base, allow_placeholders=False)
    assert any("base_model_revision" in error for error in real_run_errors)
    assert any("tokenizer_revision" in error for error in real_run_errors)
    assert any("split_manifest_sha256" in error for error in real_run_errors)
    assert any("dataset_manifest_sha256" in error for error in real_run_errors)

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "qlora.yaml"
        p.write_text(base, encoding="utf-8")
        assert not validate_file(p)

    print("QLoRA config validator self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--real-run", action="store_true", help="Require pinned model/tokenizer revisions and immutable corpus/split hashes")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    errors = validate_file(args.config, allow_placeholders=not args.real_run)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"QLoRA config valid: {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
