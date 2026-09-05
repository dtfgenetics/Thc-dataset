#!/usr/bin/env python3
"""Validate Grow Doc model evaluation run manifests without external dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DTYPES = {"float32", "float16", "bfloat16", "int8", "nf4"}
CHAT_TEMPLATE_METHODS = {"apply_chat_template:add_generation_prompt"}


class ValidationError(ValueError):
    pass


def require_keys(obj: dict[str, Any], required: set[str], allowed: set[str], path: str) -> None:
    missing = required - obj.keys()
    extra = obj.keys() - allowed
    if missing:
        raise ValidationError(f"{path}: missing required keys: {sorted(missing)}")
    if extra:
        raise ValidationError(f"{path}: unexpected keys: {sorted(extra)}")


def require_string(value: Any, path: str, min_len: int = 1) -> str:
    if not isinstance(value, str) or len(value) < min_len:
        raise ValidationError(f"{path}: expected string with length >= {min_len}")
    return value


def require_sha256(value: Any, path: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValidationError(f"{path}: expected lowercase SHA-256 hex")


def validate_manifest(data: dict[str, Any]) -> None:
    require_keys(
        data,
        {"schema_version", "run_id", "created_at", "model", "tokenizer", "decoding", "evaluation", "runtime", "artifacts"},
        {"schema_version", "run_id", "created_at", "model", "tokenizer", "decoding", "retrieval", "evaluation", "runtime", "artifacts"},
        "$",
    )
    if data["schema_version"] != "grow-doc-eval-run-v1":
        raise ValidationError("$.schema_version: unsupported schema version")
    require_string(data["run_id"], "$.run_id", 8)
    created_at = require_string(data["created_at"], "$.created_at")
    try:
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("$.created_at: expected ISO-8601 date-time") from exc

    model = data["model"]
    if not isinstance(model, dict):
        raise ValidationError("$.model: expected object")
    require_keys(model, {"repository", "revision", "dtype", "adapter"}, {"repository", "revision", "dtype", "adapter"}, "$.model")
    require_string(model["repository"], "$.model.repository")
    require_string(model["revision"], "$.model.revision", 7)
    if model["dtype"] not in DTYPES:
        raise ValidationError(f"$.model.dtype: expected one of {sorted(DTYPES)}")
    adapter = model["adapter"]
    if adapter is not None:
        if not isinstance(adapter, dict):
            raise ValidationError("$.model.adapter: expected object or null")
        require_keys(adapter, {"repository", "revision"}, {"repository", "revision"}, "$.model.adapter")
        require_string(adapter["repository"], "$.model.adapter.repository")
        require_string(adapter["revision"], "$.model.adapter.revision", 7)

    tokenizer = data["tokenizer"]
    if not isinstance(tokenizer, dict):
        raise ValidationError("$.tokenizer: expected object")
    require_keys(
        tokenizer,
        {"repository", "revision", "chat_template_sha256", "chat_template_method", "chat_template_kwargs"},
        {"repository", "revision", "chat_template_sha256", "chat_template_method", "chat_template_kwargs"},
        "$.tokenizer",
    )
    require_string(tokenizer["repository"], "$.tokenizer.repository")
    require_string(tokenizer["revision"], "$.tokenizer.revision", 7)
    require_sha256(tokenizer["chat_template_sha256"], "$.tokenizer.chat_template_sha256")
    if tokenizer["chat_template_method"] not in CHAT_TEMPLATE_METHODS:
        raise ValidationError(
            "$.tokenizer.chat_template_method: expected apply_chat_template:add_generation_prompt"
        )
    chat_template_kwargs = tokenizer["chat_template_kwargs"]
    if not isinstance(chat_template_kwargs, dict):
        raise ValidationError("$.tokenizer.chat_template_kwargs: expected object")
    require_keys(
        chat_template_kwargs,
        {"enable_thinking"},
        {"enable_thinking"},
        "$.tokenizer.chat_template_kwargs",
    )
    if not isinstance(chat_template_kwargs["enable_thinking"], bool):
        raise ValidationError("$.tokenizer.chat_template_kwargs.enable_thinking: expected boolean")

    decoding = data["decoding"]
    if not isinstance(decoding, dict):
        raise ValidationError("$.decoding: expected object")
    require_keys(decoding, {"temperature", "top_p", "max_new_tokens", "do_sample"}, {"temperature", "top_p", "max_new_tokens", "do_sample", "seed"}, "$.decoding")
    if not isinstance(decoding["temperature"], (int, float)) or decoding["temperature"] < 0:
        raise ValidationError("$.decoding.temperature: expected number >= 0")
    if not isinstance(decoding["top_p"], (int, float)) or not (0 < decoding["top_p"] <= 1):
        raise ValidationError("$.decoding.top_p: expected 0 < value <= 1")
    if not isinstance(decoding["max_new_tokens"], int) or isinstance(decoding["max_new_tokens"], bool) or decoding["max_new_tokens"] < 1:
        raise ValidationError("$.decoding.max_new_tokens: expected integer >= 1")
    if not isinstance(decoding["do_sample"], bool):
        raise ValidationError("$.decoding.do_sample: expected boolean")
    if "seed" in decoding and decoding["seed"] is not None and (not isinstance(decoding["seed"], int) or isinstance(decoding["seed"], bool)):
        raise ValidationError("$.decoding.seed: expected integer or null")

    retrieval = data.get("retrieval")
    if retrieval is not None:
        if not isinstance(retrieval, dict):
            raise ValidationError("$.retrieval: expected object or null")
        require_keys(retrieval, {"snapshot_sha256", "top_k", "reranker"}, {"snapshot_sha256", "top_k", "reranker"}, "$.retrieval")
        require_sha256(retrieval["snapshot_sha256"], "$.retrieval.snapshot_sha256")
        if not isinstance(retrieval["top_k"], int) or isinstance(retrieval["top_k"], bool) or retrieval["top_k"] < 1:
            raise ValidationError("$.retrieval.top_k: expected integer >= 1")
        if retrieval["reranker"] is not None:
            require_string(retrieval["reranker"], "$.retrieval.reranker")

    evaluation = data["evaluation"]
    if not isinstance(evaluation, dict):
        raise ValidationError("$.evaluation: expected object")
    require_keys(evaluation, {"benchmark_path", "benchmark_sha256", "scorer_revision"}, {"benchmark_path", "benchmark_sha256", "scorer_revision"}, "$.evaluation")
    require_string(evaluation["benchmark_path"], "$.evaluation.benchmark_path")
    require_sha256(evaluation["benchmark_sha256"], "$.evaluation.benchmark_sha256")
    require_string(evaluation["scorer_revision"], "$.evaluation.scorer_revision", 7)

    runtime = data["runtime"]
    if not isinstance(runtime, dict):
        raise ValidationError("$.runtime: expected object")
    runtime_required = {"python", "transformers", "torch", "accelerate", "device"}
    runtime_allowed = runtime_required | {"peft", "bitsandbytes", "gpu_name", "gpu_memory_bytes"}
    require_keys(runtime, runtime_required, runtime_allowed, "$.runtime")
    for key in ("python", "transformers", "torch", "accelerate", "device"):
        require_string(runtime[key], f"$.runtime.{key}")
    for key in ("peft", "bitsandbytes", "gpu_name"):
        if key in runtime and runtime[key] is not None:
            require_string(runtime[key], f"$.runtime.{key}")
    if "gpu_memory_bytes" in runtime and runtime["gpu_memory_bytes"] is not None:
        value = runtime["gpu_memory_bytes"]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValidationError("$.runtime.gpu_memory_bytes: expected integer >= 1 or null")

    artifacts = data["artifacts"]
    if not isinstance(artifacts, dict):
        raise ValidationError("$.artifacts: expected object")
    require_keys(artifacts, {"responses_path", "responses_sha256", "scores_path"}, {"responses_path", "responses_sha256", "scores_path", "review_path"}, "$.artifacts")
    require_string(artifacts["responses_path"], "$.artifacts.responses_path")
    require_sha256(artifacts["responses_sha256"], "$.artifacts.responses_sha256")
    require_string(artifacts["scores_path"], "$.artifacts.scores_path")
    if "review_path" in artifacts and artifacts["review_path"] is not None:
        require_string(artifacts["review_path"], "$.artifacts.review_path")


def valid_fixture() -> dict[str, Any]:
    sha = "a" * 64
    return {
        "schema_version": "grow-doc-eval-run-v1",
        "run_id": "baseline-qwen3-8b-0001",
        "created_at": "2026-09-03T14:00:00Z",
        "model": {"repository": "Qwen/Qwen3-8B", "revision": "1234567", "dtype": "bfloat16", "adapter": None},
        "tokenizer": {
            "repository": "Qwen/Qwen3-8B",
            "revision": "1234567",
            "chat_template_sha256": sha,
            "chat_template_method": "apply_chat_template:add_generation_prompt",
            "chat_template_kwargs": {"enable_thinking": False},
        },
        "decoding": {"temperature": 0.0, "top_p": 1.0, "max_new_tokens": 512, "do_sample": False, "seed": 42},
        "retrieval": {"snapshot_sha256": sha, "top_k": 5, "reranker": None},
        "evaluation": {"benchmark_path": "model_tuning/eval/heldout_v2.jsonl", "benchmark_sha256": sha, "scorer_revision": "1234567"},
        "runtime": {"python": "3.11", "transformers": "x", "torch": "x", "accelerate": "x", "peft": None, "bitsandbytes": None, "device": "cuda", "gpu_name": "test", "gpu_memory_bytes": 1},
        "artifacts": {"responses_path": "out/responses.jsonl", "responses_sha256": sha, "scores_path": "out/scores.json", "review_path": None},
    }


def self_test() -> None:
    good = valid_fixture()
    validate_manifest(good)

    bad_sha = json.loads(json.dumps(good))
    bad_sha["artifacts"]["responses_sha256"] = "not-a-sha"
    try:
        validate_manifest(bad_sha)
    except ValidationError:
        pass
    else:
        raise AssertionError("invalid SHA-256 was accepted")

    leaked_field = json.loads(json.dumps(good))
    leaked_field["model"]["untracked_revision"] = "oops"
    try:
        validate_manifest(leaked_field)
    except ValidationError:
        pass
    else:
        raise AssertionError("unexpected field was accepted")

    missing_template_hash = json.loads(json.dumps(good))
    del missing_template_hash["tokenizer"]["chat_template_sha256"]
    try:
        validate_manifest(missing_template_hash)
    except ValidationError:
        pass
    else:
        raise AssertionError("missing tokenizer chat-template hash was accepted")

    wrong_template_method = json.loads(json.dumps(good))
    wrong_template_method["tokenizer"]["chat_template_method"] = "raw-tokenize"
    try:
        validate_manifest(wrong_template_method)
    except ValidationError:
        pass
    else:
        raise AssertionError("non-chat-template prompt formatting was accepted")

    missing_template_kwargs = json.loads(json.dumps(good))
    del missing_template_kwargs["tokenizer"]["chat_template_kwargs"]
    try:
        validate_manifest(missing_template_kwargs)
    except ValidationError:
        pass
    else:
        raise AssertionError("missing chat-template kwargs were accepted")

    wrong_thinking_type = json.loads(json.dumps(good))
    wrong_thinking_type["tokenizer"]["chat_template_kwargs"]["enable_thinking"] = "false"
    try:
        validate_manifest(wrong_thinking_type)
    except ValidationError:
        pass
    else:
        raise AssertionError("non-boolean enable_thinking was accepted")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", help="manifest JSON file to validate")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("model run manifest validator self-test: PASS")
        return 0
    if not args.manifest:
        parser.error("manifest path required unless --self-test is used")

    path = Path(args.manifest)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValidationError("$: expected object")
        validate_manifest(data)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"manifest validation failed: {exc}", file=sys.stderr)
        return 1

    print(f"manifest validation PASS: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())