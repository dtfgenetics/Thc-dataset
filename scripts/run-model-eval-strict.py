#!/usr/bin/env python3
"""Strict single-GPU entrypoint for Grow Doc controlled model evaluation.

The generic evaluator keeps `device_map="auto"` for portability. This wrapper is
used by controlled benchmark launchers and intercepts model loading so a run fails
immediately if Transformers/Accelerate places any model module on CPU, disk, or a
second CUDA device.
"""
from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts/run-model-eval.py"


def normalize_device(value: Any) -> str:
    if isinstance(value, int):
        return f"cuda:{value}"
    text = str(value).strip().lower()
    if text == "cuda":
        return "cuda:0"
    if text.isdigit():
        return f"cuda:{text}"
    return text


def validate_device_map(device_map: Any) -> dict[str, Any]:
    if not isinstance(device_map, dict) or not device_map:
        raise RuntimeError("strict evaluation requires a non-empty model.hf_device_map")
    normalized = {str(module): normalize_device(device) for module, device in device_map.items()}
    devices = sorted(set(normalized.values()))
    forbidden = sorted(device for device in devices if device in {"cpu", "disk", "meta"})
    if forbidden:
        raise RuntimeError(f"strict evaluation refuses model offload devices: {', '.join(forbidden)}")
    unexpected = sorted(device for device in devices if device != "cuda:0")
    if unexpected:
        raise RuntimeError(
            "strict evaluation requires every model module on cuda:0; observed devices: " + ", ".join(devices)
        )
    return {
        "policy": "single-cuda-no-offload-v1",
        "devices": devices,
        "module_count": len(normalized),
        "offload_detected": False,
    }


def run_target(argv: list[str]) -> int:
    try:
        from transformers import AutoModelForCausalLM
    except ImportError as exc:
        raise RuntimeError("strict evaluator requires the pinned Transformers runtime") from exc

    original = AutoModelForCausalLM.from_pretrained
    observed: dict[str, Any] = {}

    def guarded_from_pretrained(*args: Any, **kwargs: Any) -> Any:
        model = original(*args, **kwargs)
        summary = validate_device_map(getattr(model, "hf_device_map", None))
        observed.update(summary)
        print("strict device-map contract: " + json.dumps(summary, sort_keys=True), file=sys.stderr)
        return model

    old_argv = sys.argv[:]
    sys.argv = [str(TARGET), *argv]
    try:
        with patch.object(AutoModelForCausalLM, "from_pretrained", side_effect=guarded_from_pretrained):
            try:
                runpy.run_path(str(TARGET), run_name="__main__")
            except SystemExit as exc:
                code = exc.code
                if code is None:
                    return 0
                if isinstance(code, int):
                    return code
                raise
    finally:
        sys.argv = old_argv
    if not observed:
        raise RuntimeError("strict evaluation did not observe a model load")
    return 0


def self_test() -> None:
    assert normalize_device(0) == "cuda:0"
    assert normalize_device("0") == "cuda:0"
    assert normalize_device("cuda") == "cuda:0"
    assert validate_device_map({"": 0, "model.layers.0": "cuda:0"})["offload_detected"] is False
    for device_map, expected in [
        ({"": "cpu"}, "offload"),
        ({"": "disk"}, "offload"),
        ({"": 0, "model.layers.1": 1}, "cuda:0"),
        ({}, "non-empty"),
        (None, "non-empty"),
    ]:
        try:
            validate_device_map(device_map)
        except RuntimeError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"strict device-map contract should reject {device_map!r}")
    print("strict model evaluation entrypoint self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--strict-self-test", action="store_true")
    known, remainder = parser.parse_known_args()
    if known.strict_self_test:
        self_test()
        return 0
    return run_target(remainder)


if __name__ == "__main__":
    raise SystemExit(main())
