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


def validate_text(text: str, *, allow_placeholder_revision: bool = True) -> list[str]:
    errors: list[str] = []

    base_model = scalar(text, "base_model")
    base_revision = scalar(text, "base_model_revision")
    if not base_model:
        errors.append("base_model is required")
    if not base_revision:
        errors.append("base_model_revision is required")
    elif base_revision == "PIN_BEFORE_TRAINING" and not allow_placeholder_revision:
        errors.append("base_model_revision must be pinned before a real training run")

    precision = section(text, "precision")
    training_data = section(text, "training_data")
    training = section(text, "training")
    evaluation = section(text, "evaluation")
    merge_policy = section(text, "merge_policy")
    rag = section(text, "rag")
    lora = section(text, "lora")

    if bool_value(scalar(precision, "load_in_4bit")) is not True:
        errors.append("QLoRA contract requires precision.load_in_4bit: true")
    if scalar(precision, "bnb_4bit_quant_type") != "nf4":
        errors.append("QLoRA contract requires NF4 quantization")
    if scalar(precision, "compute_dtype") != "bfloat16":
        errors.append("starter 8B contract requires bfloat16 compute dtype")
    if bool_value(scalar(training, "bf16")) is not True:
        errors.append("training.bf16 must match bfloat16 compute dtype")

    sft_path = scalar(training_data, "sft_path")
    grounded_qa_path = scalar(training_data, "grounded_qa_path")
    grounded_qa_max_fraction = float_value(scalar(training_data, "grounded_qa_max_fraction"))
    retrieval_path = scalar(training_data, "retrieval_path")
    quarantine_path = scalar(training_data, "quarantine_path")
    heldout_path = scalar(evaluation, "heldout_path")

    if not grounded_qa_path:
        errors.append("training_data.grounded_qa_path is required")
    elif "model_tuning/generated/grounded_qa/" not in grounded_qa_path:
        errors.append("grounded QA data must come from the dedicated grounded_qa output lane")

    if grounded_qa_max_fraction is None:
        errors.append("training_data.grounded_qa_max_fraction must be numeric")
    elif not (0.0 < grounded_qa_max_fraction <= 0.20):
        errors.append("grounded QA fraction must be greater than 0 and capped at 0.20")

    paths = [p for p in (sft_path, grounded_qa_path, retrieval_path, quarantine_path, heldout_path) if p]
    if len(paths) != len(set(paths)):
        errors.append("SFT, grounded-QA, retrieval, quarantine, and held-out paths must be distinct")
    if heldout_path and heldout_path in {sft_path, grounded_qa_path}:
        errors.append("held-out evaluation data cannot be used as training data")

    for key in ("train_only_grounded_examples", "require_context_required", "preserve_source_ids", "forbid_quarantine_training", "forbid_eval_training_leakage"):
        if bool_value(scalar(training_data, key)) is not True:
            errors.append(f"training_data.{key} must be true")

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

    # The repository currently performs checkpoint promotion externally against the
    # frozen held-out suite. Until a Trainer eval_dataset/metric callback exists,
    # load_best_model_at_end would be misleading and can be invalid at runtime.
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


def validate_file(path: Path, *, allow_placeholder_revision: bool = True) -> list[str]:
    if not path.exists():
        return [f"config not found: {path}"]
    return validate_text(path.read_text(encoding="utf-8"), allow_placeholder_revision=allow_placeholder_revision)


def self_test() -> None:
    base = DEFAULT_CONFIG.read_text(encoding="utf-8")
    assert not validate_text(base), validate_text(base)

    tampered = base.replace("allow_adapter_merge: false", "allow_adapter_merge: true")
    assert any("adapter merge" in error for error in validate_text(tampered))

    tampered = base.replace("load_best_model_at_end: false", "load_best_model_at_end: true")
    assert any("load_best_model_at_end" in error for error in validate_text(tampered))

    tampered = base.replace("grounded_qa_max_fraction: 0.20", "grounded_qa_max_fraction: 0.50")
    assert any("grounded QA fraction" in error for error in validate_text(tampered))

    tampered = base.replace(
        "grounded_qa_path: model_tuning/generated/grounded_qa/qa_v1.jsonl",
        "grounded_qa_path: model_tuning/generated/sft/grounded_v1.jsonl",
    )
    assert any("dedicated grounded_qa" in error or "must be distinct" in error for error in validate_text(tampered))

    tampered = base.replace("base_model_revision: PIN_BEFORE_TRAINING", "base_model_revision: PIN_BEFORE_TRAINING")
    assert any("must be pinned" in error for error in validate_text(tampered, allow_placeholder_revision=False))

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "qlora.yaml"
        p.write_text(base, encoding="utf-8")
        assert not validate_file(p)

    print("QLoRA config validator self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--real-run", action="store_true", help="Require an immutable base-model revision instead of the starter placeholder")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    errors = validate_file(args.config, allow_placeholder_revision=not args.real_run)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"QLoRA config valid: {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
