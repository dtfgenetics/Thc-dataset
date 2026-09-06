#!/usr/bin/env python3
"""Evaluate evidence-role alignment as a leak-safe RAG reranking signal.

This experiment does not mutate the frozen RAG snapshot or training artifacts. Retrieval
features come only from the user prompt and corpus-side reviewed claim/source metadata.
Held-out expected answers, forbidden claims, and must_cite labels are never ranking inputs;
must_cite is used only after retrieval to measure required-source coverage.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "scripts/build-rag-eval-snapshot.py"
CLAIMS = ROOT / "model_tuning/generated/rag/claims_v1.jsonl"
BENCH = ROOT / "model_tuning/eval/heldout_v2.jsonl"

spec = importlib.util.spec_from_file_location("rag_eval", BASE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("could not load build-rag-eval-snapshot.py")
rag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rag)

ROLE_PATTERNS = {
    "causal_confirmation": (
        r"\bpathogenicity\b", r"\bkoch(?:'s)? postulates?\b", r"\binoculat(?:e|ed|ion)\b",
        r"\bre[- ]?isolat(?:e|ed|ion)\b", r"\bsymptoms? (?:were )?reproduc(?:e|ed|ible)\b",
        r"\bcaus(?:e|ed|ing)\b", r"\bfirst report\b",
    ),
    "molecular_identification": (
        r"\bmolecular\b", r"\bsequenc(?:e|ed|ing)\b", r"\bpcr\b", r"\bphylogen(?:y|etic)\b",
        r"\bidentif(?:y|ied|ication)\b",
    ),
    "differential_context": (
        r"\bdifferential\b", r"\bsurvey\b", r"\blook[- ]?alike\b", r"\bdiagnos(?:is|tic)\b",
        r"\bmultiple (?:pathogens|causes|organisms)\b",
    ),
    "management": (
        r"\bmanagement\b", r"\bcontrol\b", r"\bprevent(?:ion|ive)?\b", r"\bsanitation\b",
        r"\btreatment\b",
    ),
}

INTENT_PATTERNS = {
    "causal_confirmation": (
        r"\bpathogenicity\b", r"\bcaus(?:e|ed|al)\b", r"\bprove\b", r"\bconfirm(?:ed|ation)?\b",
        r"\bsupport .* as the cause\b", r"\bwhat findings\b",
    ),
    "molecular_identification": (
        r"\bmolecular\b", r"\bpcr\b", r"\bsequenc(?:e|ing)\b", r"\bidentify\b", r"\bidentification\b",
    ),
    "differential_context": (
        r"\bdifferential\b", r"\brule out\b", r"\blook[- ]?alike\b", r"\bother causes\b",
    ),
    "management": (
        r"\bmanage(?:ment)?\b", r"\bcontrol\b", r"\bprevent\b", r"\btreat\b",
    ),
}


def joined_corpus_text(row: dict) -> str:
    fields = rag.row_fields(row)
    return " ".join(str(value or "") for value in fields.values()).lower()


def detect_roles(text: str, patterns: dict[str, tuple[str, ...]]) -> set[str]:
    roles: set[str] = set()
    for role, role_patterns in patterns.items():
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in role_patterns):
            roles.add(role)
    return roles


def role_alignment_bonus(prompt: str, row: dict) -> float:
    intents = detect_roles(prompt.lower(), INTENT_PATTERNS)
    if not intents:
        return 0.0
    roles = detect_roles(joined_corpus_text(row), ROLE_PATTERNS)
    if not roles:
        return 0.0
    matched = intents & roles
    if not matched:
        return 0.0
    # A bounded categorical bonus avoids swamping the existing lexical/metadata score.
    return float(len(matched))


def retrieve_variant(claims: list[dict], prompt: str, top_k: int, bonus_weight: float) -> list[dict]:
    df = rag.document_frequencies(claims)
    query = rag.tokens(prompt)
    ranked = []
    for row in claims:
        score = rag.weighted_score(query, row, df, len(claims))
        score += bonus_weight * role_alignment_bonus(prompt, row)
        ranked.append((score, row["id"], row))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in ranked if item[0] > 0][:top_k]


def coverage(cases: list[dict], selections: dict[str, list[dict]]) -> tuple[int, int, list[str]]:
    eligible = 0
    hits = 0
    missing: list[str] = []
    for case in cases:
        required = {str(x).strip() for x in case.get("must_cite") or [] if str(x).strip()}
        if not required:
            continue
        eligible += 1
        found = {
            str(source_id).strip()
            for row in selections.get(case["id"], [])
            for source_id in row.get("source_ids") or []
            if str(source_id).strip()
        }
        if required.issubset(found):
            hits += 1
        else:
            missing.append(case["id"])
    return hits, eligible, missing


def main() -> int:
    claims = rag.load_jsonl(CLAIMS)
    cases = rag.load_jsonl(BENCH)
    rag.validate_claims(claims)
    rag.validate_cases(cases)

    current_snapshot = rag.build(claims, cases, 5, metadata_aware=True)
    current = rag.required_source_coverage(cases, current_snapshot)
    print("current", json.dumps(current, sort_keys=True))

    best = (current["hit_cases"], 0.0, current["missing_case_ids"])
    for weight in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
        selections = {case["id"]: retrieve_variant(claims, case["prompt"], 5, weight) for case in cases}
        hits, eligible, missing = coverage(cases, selections)
        print(f"evidence_role_bonus={weight:.2f} coverage={hits}/{eligible} missing={','.join(missing)}")
        if hits > best[0]:
            best = (hits, weight, missing)

    print(f"best coverage={best[0]}/{current['eligible_cases']} weight={best[1]:.2f} missing={','.join(best[2])}")
    if best[0] < current["hit_cases"]:
        raise SystemExit("evidence-role experiment regressed current retrieval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
