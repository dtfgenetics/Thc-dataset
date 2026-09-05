#!/usr/bin/env python3
"""Materialize and verify a pinned tokenizer chat-template contract.

The default loader reads only tokenizer_config.json at an immutable Hugging Face
revision, then hashes its exact chat_template string. This avoids downloading
model weights or requiring Transformers just to establish template identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
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
    expected = expected_sha256.lower()
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError("expected chat-template SHA-256 must be 64 hexadecimal characters")
    actual = chat_template_sha256(template)
    if actual != expected:
        raise ValueError(f"tokenizer chat-template SHA-256 mismatch: expected {expected}, got {actual}")
    return actual


def validate_revision(revision: str) -> str:
    if not revision or revision in {"UNPINNED", "PIN_BEFORE_TRAINING"}:
        raise ValueError("tokenizer revision must be pinned before materializing its chat template")
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision.lower()):
        raise ValueError("tokenizer revision must be a full 40-character git commit SHA")
    return revision.lower()


def tokenizer_config_url(repo: str, revision: str) -> str:
    pinned = validate_revision(revision)
    if not repo or "/" not in repo:
        raise ValueError("tokenizer repo must be an owner/name Hugging Face repository id")
    safe_repo = "/".join(urllib.parse.quote(part, safe="") for part in repo.split("/"))
    return f"https://huggingface.co/{safe_repo}/resolve/{pinned}/tokenizer_config.json"


def template_from_tokenizer_config(value: Any) -> str:
    if not isinstance(value, dict):
        raise ValueError("tokenizer_config.json must contain a JSON object")
    template = value.get("chat_template")
    if isinstance(template, list):
        # Transformers supports named templates, but Grow Doc requires one
        # deterministic default template for reproducible prompt formatting.
        defaults = [item.get("template") for item in template if isinstance(item, dict) and item.get("name") == "default"]
        if len(defaults) != 1:
            raise ValueError("tokenizer config must expose exactly one default chat template")
        template = defaults[0]
    return normalize_template(template)


def load_pinned_template_from_config(repo: str, revision: str, *, timeout: float = 30.0) -> str:
    url = tokenizer_config_url(repo, revision)
    req = urllib.request.Request(url, headers={"User-Agent": "grow-doc-chat-template-materializer/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"failed to fetch pinned tokenizer config: {exc}") from exc
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("pinned tokenizer_config.json was not valid UTF-8 JSON") from exc
    return template_from_tokenizer_config(value)


def load_pinned_template_transformers(repo: str, revision: str) -> str:
    validate_revision(revision)
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("Transformers loader requires the transformers package") from exc
    tok = AutoTokenizer.from_pretrained(repo, revision=revision)
    return normalize_template(tok.chat_template)


def self_test() -> None:
    template = "{% for message in messages %}{{ message['role'] }}: {{ message['content'] }}{% endfor %}"
    digest = chat_template_sha256(template)
    assert len(digest) == 64
    assert verify_chat_template(template, digest.upper()) == digest
    assert template_from_tokenizer_config({"chat_template": template}) == template
    assert template_from_tokenizer_config({"chat_template": [{"name": "default", "template": template}]}) == template
    url = tokenizer_config_url("Qwen/Qwen3-8B", "b968826d9c46dd6066d109eabc6255188de91218")
    assert url.endswith("/b968826d9c46dd6066d109eabc6255188de91218/tokenizer_config.json")

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

    for bad_revision in ("UNPINNED", "main", "b968826"):
        try:
            validate_revision(bad_revision)
        except ValueError:
            pass
        else:
            raise AssertionError("non-immutable tokenizer revisions must be rejected")

    print("chat-template materializer self-test: PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--tokenizer-repo", default="Qwen/Qwen3-8B")
    p.add_argument("--tokenizer-revision", default="UNPINNED")
    p.add_argument("--expected-sha256")
    p.add_argument("--print-template", action="store_true")
    p.add_argument("--loader", choices=("config", "transformers"), default="config")
    args = p.parse_args()

    if args.self_test:
        self_test()
        return 0

    if args.loader == "transformers":
        template = load_pinned_template_transformers(args.tokenizer_repo, args.tokenizer_revision)
    else:
        template = load_pinned_template_from_config(args.tokenizer_repo, args.tokenizer_revision)
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
