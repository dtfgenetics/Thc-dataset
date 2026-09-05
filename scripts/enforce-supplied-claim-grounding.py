#!/usr/bin/env python3
"""Rewrite model-training records so targets contain only supplied evidence claims.

Upstream diagnostic profiles can contain broader reviewed summaries, differentials,
and confirmation notes. Those are useful for the product, but they must not leak into
an SFT target when the corresponding evidence is absent from that record's prompt.

This module makes the training boundary mechanical: factual bullets in the assistant
answer are copied verbatim from evidence physically present in the user message. All
other text is fixed uncertainty/behavior scaffolding. No model or semantic classifier
is used, so the transformation is deterministic and auditable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

BRACKET_CLAIM = re.compile(r"^\s*\[([^\]]+)\]\s+(.+?)\s*$")
BULLET_CLAIM = re.compile(r"^\s*-\s+(.+?)\s*$")
EVIDENCE_FROM = re.compile(r"Evidence from \[([^\]]+)\]:", re.IGNORECASE)


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def messages_by_role(row: dict) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for message in row.get("messages") or []:
        role = message.get("role")
        if role in {"system", "user", "assistant"} and role not in found:
            found[role] = message
    return found


def extract_supplied_claims(user_text: str, source_ids: list[str]) -> list[tuple[str, str]]:
    claims: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    fallback_source = None
    match = EVIDENCE_FROM.search(user_text or "")
    if match:
        fallback_source = match.group(1).strip()
    elif len(source_ids) == 1:
        fallback_source = source_ids[0]

    for line in (user_text or "").splitlines():
        bracketed = BRACKET_CLAIM.match(line)
        if bracketed:
            pair = (bracketed.group(1).strip(), bracketed.group(2).strip())
        else:
            bullet = BULLET_CLAIM.match(line)
            if not bullet or not fallback_source:
                continue
            pair = (fallback_source, bullet.group(1).strip())
        if pair[0] and pair[1] and pair not in seen:
            seen.add(pair)
            claims.append(pair)
    return claims


def canonical_evidence(claims: list[tuple[str, str]]) -> str:
    return "\n".join(f"[{sid}] {claim}" for sid, claim in claims)


def task_prompt(task: str, evidence: str) -> str:
    if task == "grounded_diagnostic_reasoning":
        request = (
            "Using only the supplied claims, explain what the evidence supports and what remains unconfirmed. "
            "Treat any diagnostic/profile label as a hypothesis, not as a conclusion, unless a supplied claim explicitly establishes it."
        )
    elif task == "differential_and_next_test":
        request = (
            "Using only the supplied claims, state any distinctions or confirmation evidence they actually establish. "
            "If the claims do not establish a named differential or diagnostic test, say so rather than inventing one."
        )
    elif task == "science_education":
        request = (
            "Teach only what these supplied claims establish. Separate the evidence from uncertainty and do not add profile-wide facts, "
            "thresholds, diagnoses, or recommendations that are absent from the claims."
        )
    else:
        request = (
            "Based only on these supplied claims, summarize what is scientifically supported. Do not infer that the evidence establishes "
            "the profile label unless a supplied claim explicitly does so."
        )
    return f"Evidence:\n{evidence}\n\n{request}"


def task_boundary(task: str) -> str:
    if task == "grounded_diagnostic_reasoning":
        return (
            "Diagnostic boundary: The supplied evidence does not justify a broader diagnostic conclusion unless one of the quoted claims "
            "explicitly establishes it. Keep the profile label as a hypothesis and separate observation from confirmation."
        )
    if task == "differential_and_next_test":
        return (
            "Differential boundary: Name a differential, test, threshold, or discriminating feature only when it appears in the quoted claims. "
            "Otherwise state that the supplied evidence is insufficient to specify it."
        )
    if task == "science_education":
        return (
            "Teaching boundary: Explain the quoted claims clearly, but do not extend them into unstated diagnoses, universal rules, thresholds, "
            "or recommendations. Distinguish evidence from what remains unknown."
        )
    return (
        "Grounding boundary: These claims support only the statements above. They do not by themselves establish any broader profile label, "
        "diagnosis, causal claim, universal threshold, differential, or recommendation unless that statement is explicitly contained in the supplied evidence."
    )


def assistant_target(task: str, claims: list[tuple[str, str]]) -> str:
    bullets = "\n".join(f"- {claim} Citation: {sid}" for sid, claim in claims)
    return f"Supported by the supplied evidence:\n{bullets}\n\n{task_boundary(task)}"


def sanitize_row(row: dict) -> dict:
    roles = messages_by_role(row)
    if "user" not in roles or "assistant" not in roles:
        raise ValueError(f"{row.get('id')}: user and assistant messages are required")
    source_ids = [str(value) for value in (row.get("source_ids") or []) if str(value).strip()]
    if not source_ids:
        raise ValueError(f"{row.get('id')}: source_ids are required")
    claims = extract_supplied_claims(roles["user"].get("content") or "", source_ids)
    if not claims:
        raise ValueError(f"{row.get('id')}: no supplied evidence claims could be parsed from user prompt")
    claim_sources = {sid for sid, _ in claims}
    if not claim_sources.issubset(set(source_ids)):
        raise ValueError(f"{row.get('id')}: parsed evidence references a source outside source_ids")

    clean = json.loads(json.dumps(row, ensure_ascii=False))
    clean_roles = messages_by_role(clean)
    task = str(clean.get("task") or "")
    evidence = canonical_evidence(claims)
    clean_roles["user"]["content"] = task_prompt(task, evidence)
    clean_roles["assistant"]["content"] = assistant_target(task, claims)
    clean["grounding_mode"] = "supplied_claims_only_v1"
    clean["evidence_claims"] = [
        {"source_id": sid, "claim": claim, "claim_sha256": text_sha256(claim)} for sid, claim in claims
    ]
    clean["evidence_claim_sha256s"] = [item["claim_sha256"] for item in clean["evidence_claims"]]
    return clean


def validate_row(row: dict) -> list[str]:
    errors: list[str] = []
    rid = row.get("id") or "<missing-id>"
    if row.get("grounding_mode") != "supplied_claims_only_v1":
        errors.append(f"{rid}: grounding_mode must be supplied_claims_only_v1")
        return errors
    roles = messages_by_role(row)
    evidence_claims = row.get("evidence_claims") or []
    if not evidence_claims:
        errors.append(f"{rid}: evidence_claims are required")
        return errors
    user = (roles.get("user") or {}).get("content") or ""
    assistant = (roles.get("assistant") or {}).get("content") or ""
    for item in evidence_claims:
        sid = item.get("source_id")
        claim = item.get("claim")
        digest = item.get("claim_sha256")
        if not sid or not claim or text_sha256(claim) != digest:
            errors.append(f"{rid}: invalid evidence claim metadata")
            continue
        if f"[{sid}] {claim}" not in user:
            errors.append(f"{rid}: evidence claim missing from user prompt")
        if f"- {claim} Citation: {sid}" not in assistant:
            errors.append(f"{rid}: assistant factual bullet is not an exact supplied claim")
    expected = assistant_target(
        str(row.get("task") or ""),
        [(item["source_id"], item["claim"]) for item in evidence_claims],
    )
    if assistant != expected:
        errors.append(f"{rid}: assistant target contains content outside deterministic supplied-claim template")
    return errors


def sanitize_records(rows: list[dict]) -> list[dict]:
    sanitized = [sanitize_row(row) for row in rows]
    errors = [error for row in sanitized for error in validate_row(row)]
    if errors:
        raise ValueError("; ".join(errors[:5]))
    return sanitized


def self_test() -> None:
    unsafe = {
        "id": "gqa-target-1",
        "task": "grounded_qa",
        "profile_id": "target-disorder",
        "source_ids": ["url:https://example.test/different"],
        "grounded": True,
        "context_required": True,
        "messages": [
            {"role": "system", "content": "Answer only from evidence."},
            {"role": "user", "content": "Evidence from [url:https://example.test/different]:\n- Different disorder causes circular lesions.\n\nWhat is supported about Target disorder?"},
            {"role": "assistant", "content": "Target disorder is confirmed and has red ooze."},
        ],
    }
    clean = sanitize_row(unsafe)
    user = messages_by_role(clean)["user"]["content"]
    assistant = messages_by_role(clean)["assistant"]["content"]
    assert "What is supported about Target disorder?" not in user
    assert "Target disorder is confirmed" not in assistant
    assert "Different disorder causes circular lesions." in assistant
    assert not validate_row(clean)

    base_claim = [("doi:test", "Evidence claim.")]
    diagnostic = assistant_target("grounded_diagnostic_reasoning", base_claim)
    differential = assistant_target("differential_and_next_test", base_claim)
    education = assistant_target("science_education", base_claim)
    assert len({diagnostic, differential, education}) == 3
    assert "Diagnostic boundary" in diagnostic
    assert "Differential boundary" in differential
    assert "Teaching boundary" in education

    tampered = json.loads(json.dumps(clean))
    messages_by_role(tampered)["assistant"]["content"] += "\nTarget disorder is definitely confirmed."
    assert any("outside deterministic" in error for error in validate_row(tampered))

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "rows.jsonl"
        path.write_text(json.dumps(clean) + "\n", encoding="utf-8")
        loaded = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert not validate_row(loaded[0])
    print("supplied-claim grounding self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    parser.error("this module is used by the split builder; pass --self-test for standalone validation")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
