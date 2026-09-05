#!/usr/bin/env python3
"""Small, dependency-free contract for model-eval chat-template kwargs.

Keep model-specific template behavior explicit and serializable so evaluation
runs cannot silently inherit tokenizer defaults.
"""
from __future__ import annotations

from typing import Any

CHAT_TEMPLATE_METHOD = "apply_chat_template:add_generation_prompt"


def validate_enable_thinking(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError("enable_thinking must be an explicit boolean")
    return value


def chat_template_kwargs(enable_thinking: Any) -> dict[str, bool]:
    return {"enable_thinking": validate_enable_thinking(enable_thinking)}


def render_chat_prompt(tokenizer: Any, prompt: str, *, enable_thinking: Any) -> str:
    kwargs = chat_template_kwargs(enable_thinking)
    rendered = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=False,
        add_generation_prompt=True,
        **kwargs,
    )
    if not isinstance(rendered, str) or not rendered:
        raise ValueError("tokenizer.apply_chat_template returned an empty/non-string prompt")
    return rendered


def self_test() -> None:
    assert chat_template_kwargs(False) == {"enable_thinking": False}
    assert chat_template_kwargs(True) == {"enable_thinking": True}
    for invalid in (None, 0, 1, "false", "true"):
        try:
            chat_template_kwargs(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"non-boolean enable_thinking must be rejected: {invalid!r}")

    class DummyTokenizer:
        def apply_chat_template(
            self,
            messages: list[dict[str, str]],
            *,
            tokenize: bool,
            add_generation_prompt: bool,
            enable_thinking: bool,
        ) -> str:
            assert messages == [{"role": "user", "content": "Test"}]
            assert tokenize is False
            assert add_generation_prompt is True
            assert enable_thinking is False
            return "rendered-with-thinking-disabled"

    assert render_chat_prompt(DummyTokenizer(), "Test", enable_thinking=False) == "rendered-with-thinking-disabled"
    print("model eval template contract self-test: PASS")


if __name__ == "__main__":
    self_test()
