#!/usr/bin/env python3
"""Validate that the frozen Grow Doc training mix yields useful QLoRA checkpoints.

This guard is dataset-size aware. It reads the reviewed QLoRA runtime contract and
counts the exact frozen train SFT + capped grounded-QA rows, then estimates the
single-GPU optimizer-step budget used by the trainer. It fails if the configured
save/eval cadence would produce too few scheduled dev-evaluation checkpoints.

It does not train, evaluate a model, merge adapters, or modify dataset content.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from qlora_runtime_contract import CONFIG, load_runtime_contract  # noqa: E402

DEFAULT_TRAIN_SFT = ROOT / "model_tuning/generated/splits/train_sft_v1.jsonl"
DEFAULT_TRAIN_GQA = ROOT / "model_tuning/generated/splits/train_grounded_qa_mixture_v1.jsonl"
MIN_SCHEDULED_EVALS = 2


class CadenceError(RuntimeError):
    pass


def count_jsonl_objects(path: Path) -> int:
    if not path.exists():
        raise CadenceError(f"missing frozen training file: {path}")
    count = 0
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CadenceError(f"{path}:{line_no}: invalid JSON") from exc
        if not isinstance(value, dict):
            raise CadenceError(f"{path}:{line_no}: expected JSON object")
        count += 1
    if count <= 0:
        raise CadenceError(f"frozen training file is empty: {path}")
    return count


def estimate_schedule(
    *,
    train_rows: int,
    batch_size: int,
    gradient_accumulation_steps: int,
    num_train_epochs: float,
    eval_steps: int,
    save_steps: int,
    minimum_scheduled_evals: int = MIN_SCHEDULED_EVALS,
) -> dict[str, int | float]:
    if train_rows <= 0:
        raise CadenceError("train_rows must be positive")
    if batch_size <= 0 or gradient_accumulation_steps <= 0:
        raise CadenceError("batch size and gradient accumulation must be positive")
    if not math.isfinite(num_train_epochs) or num_train_epochs <= 0:
        raise CadenceError("num_train_epochs must be finite and positive")
    if eval_steps <= 0 or save_steps <= 0:
        raise CadenceError("eval_steps and save_steps must be positive")
    if eval_steps != save_steps:
        raise CadenceError("eval_steps must equal save_steps for checkpoint selection")
    if minimum_scheduled_evals < 1:
        raise CadenceError("minimum_scheduled_evals must be positive")

    micro_batches_per_epoch = math.ceil(train_rows / batch_size)
    optimizer_steps_per_epoch = math.ceil(micro_batches_per_epoch / gradient_accumulation_steps)
    total_optimizer_steps = math.ceil(optimizer_steps_per_epoch * num_train_epochs)
    scheduled_evaluations = total_optimizer_steps // eval_steps

    if scheduled_evaluations < minimum_scheduled_evals:
        raise CadenceError(
            "checkpoint cadence is too sparse for the frozen training mix: "
            f"{scheduled_evaluations} scheduled eval(s) across {total_optimizer_steps} optimizer steps; "
            f"require at least {minimum_scheduled_evals}"
        )

    return {
        "train_rows": train_rows,
        "micro_batches_per_epoch": micro_batches_per_epoch,
        "optimizer_steps_per_epoch": optimizer_steps_per_epoch,
        "total_optimizer_steps": total_optimizer_steps,
        "eval_steps": eval_steps,
        "save_steps": save_steps,
        "scheduled_evaluations": scheduled_evaluations,
        "minimum_scheduled_evaluations": minimum_scheduled_evals,
        "num_train_epochs": num_train_epochs,
    }


def self_test() -> None:
    current = estimate_schedule(
        train_rows=161,
        batch_size=1,
        gradient_accumulation_steps=16,
        num_train_epochs=2,
        eval_steps=10,
        save_steps=10,
    )
    assert current["optimizer_steps_per_epoch"] == 11
    assert current["total_optimizer_steps"] == 22
    assert current["scheduled_evaluations"] == 2

    try:
        estimate_schedule(
            train_rows=161,
            batch_size=1,
            gradient_accumulation_steps=16,
            num_train_epochs=2,
            eval_steps=100,
            save_steps=100,
        )
    except CadenceError as exc:
        assert "too sparse" in str(exc)
    else:
        raise AssertionError("sparse checkpoint cadence was accepted")

    try:
        estimate_schedule(
            train_rows=161,
            batch_size=1,
            gradient_accumulation_steps=16,
            num_train_epochs=2,
            eval_steps=10,
            save_steps=20,
        )
    except CadenceError as exc:
        assert "must equal" in str(exc)
    else:
        raise AssertionError("mismatched eval/save cadence was accepted")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rows.jsonl"
        path.write_text('{"id":"a"}\n\n{"id":"b"}\n', encoding="utf-8")
        assert count_jsonl_objects(path) == 2
        path.write_text('{"id":"a"}\n[]\n', encoding="utf-8")
        try:
            count_jsonl_objects(path)
        except CadenceError as exc:
            assert "expected JSON object" in str(exc)
        else:
            raise AssertionError("non-object JSONL row was accepted")

    print("Grow Doc QLoRA checkpoint cadence self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--train-sft", type=Path, default=DEFAULT_TRAIN_SFT)
    parser.add_argument("--train-grounded-qa", type=Path, default=DEFAULT_TRAIN_GQA)
    parser.add_argument("--minimum-scheduled-evals", type=int, default=MIN_SCHEDULED_EVALS)
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    try:
        contract = load_runtime_contract(CONFIG.read_text(encoding="utf-8"))
        sft_rows = count_jsonl_objects(args.train_sft)
        gqa_rows = count_jsonl_objects(args.train_grounded_qa)
        training = contract.training
        report = estimate_schedule(
            train_rows=sft_rows + gqa_rows,
            batch_size=int(training["per_device_train_batch_size"]),
            gradient_accumulation_steps=int(training["gradient_accumulation_steps"]),
            num_train_epochs=float(training["num_train_epochs"]),
            eval_steps=int(training["eval_steps"]),
            save_steps=int(training["save_steps"]),
            minimum_scheduled_evals=args.minimum_scheduled_evals,
        )
        report["train_sft_rows"] = sft_rows
        report["train_grounded_qa_rows"] = gqa_rows
    except (OSError, CadenceError, ValueError) as exc:
        print(f"Grow Doc QLoRA checkpoint cadence: FAIL: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    print("Grow Doc QLoRA checkpoint cadence: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
