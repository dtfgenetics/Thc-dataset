#!/usr/bin/env python3
"""Materialize and verify a pinned tokenizer chat-template contract.

This helper intentionally separates chat-template identity from model weights.
It can hash a tokenizer's effective chat template at a pinned revision and
verify that hash against the immutable Grow Doc experiment contract.
"""
from __future__ import annotations

import argparse
import hashlib
from typing import Any


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_template(template: Any) -> str:
    if not isinstance(template, str) or not template.strip():
        raise ValueError("tokenizer chat_template must be a non-empty string")
    return template


def chat_template_sha256(template: Any) -> str:
    return text_sha256(normalize_template(template))


def verify_chat_template(template: Any, expected_sha256: str) -> str:
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256.lower()):
        raise ValueError("expected chat-template SHA-256 must be 64 hexadecimal characters")
    actual = chat_template_sha256(template)
    if actual != expected_sha256.lower():
        raise ValueError(
            f"tokenizer chat-template SHA-256 mismatch: expected {expected_sha256.lower()}, got {actual}"
        )
    return actual


def load_pinned_template(repo: str, revision: str) -> str:
    if not revision or revision in {"UNPINNED", "PIN_BEFORE_TRAINING"} or len(revision) < 7:
        raise ValueError("tokenizer revision must be pinned before materializing its chat template")
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("materializing a real tokenizer chat template requires transformers") from exc
    tok = AutoTokenizer.from_pretrained(repo, revision=revision)
    return normalize_template(tok.chat_template)


def self_test() -> None:
    template = "{% for message in messages %}{{ message['role'] }}: {{ message['content'] }}{% endfor %}"
    digest = chat_template_sha256(template)
    assert len(digest) == 64
    assert verify_chat_template(template, digest.upper()) == digest

    for bad in (None, "", "   "):
        try:
            chat_template_sha256(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("empty/non-string chat templates must be rejected")

    try:
        verify_chat_template(template, "0" * 64)
    except ValueError as exc:
        assert "mismatch" in str(exc)
    else:
        raise AssertionError("template hash mismatch must be rejected")

    try:
        verify_chat_template(template, "not-a-hash")
    except ValueError as exc:
        assert "64 hexadecimal" in str(exc)
    else:
        raise AssertionError("malformed expected hashes must be rejected")

    print("chat-template materializer self-test: PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--tokenizer-repo", default="Qwen/Qwen3-8B")
    p.add_argument("--tokenizer-revision", default="UNPINNED")
    p.add_argument("--expected-sha256")
    p.add_argument("--print-template", action="store_true")
    args = p.parse_args()

    if args.self_test:
        self_test()
        return 0

    template = load_pinned_template(args.tokenizer_repo, args.tokenizer_revision)
    digest = chat_template_sha256(template)
    if args.expected_sha256:
        verify_chat_template(template, args.expected_sha256)
    print(f"tokenizer_repo={args.tokenizer_repo}")
    print(f"tokenizer_revision={args.tokenizer_revision}")
    print(f"tokenizer_chat_template_sha256={digest}")
    if args.print_template:
        print(template)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
