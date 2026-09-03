#!/usr/bin/env python3
"""Promote generated Grow Doc SFT candidates only after explicit human review.

The candidate corpus remains immutable. Review decisions are a separate JSONL ledger.
Approved rows are copied into a reviewed corpus with review metadata attached. Rejected
rows are written to a rejection report and never enter the training corpus.

Decision JSONL fields:
  recordId: candidate id
  candidateSha256: canonical hash of the exact candidate reviewed
  decision: approved | rejected
  reviewer: non-empty reviewer identifier
  reviewedAt: ISO-8601 timestamp/date
  checks: scientific-review checklist booleans
  notes: required for rejected decisions; recommended for edits
  editedMessages: optional replacement messages for approved decisions only

Required checks:
  sourceSupport: cited evidence supports the answer
  citationIntegrity: provenance is traceable and not fabricated
  scopeAndUncertainty: scope, caveats, and uncertainty are appropriate
  diagnosticDifferential: diagnostic claims preserve plausible alternatives
  numericalContext: numerical claims retain system/stage/measurement context

Safety invariants:
- every candidate must have exactly one decision unless --allow-undecided is set
- decisions may reference only existing candidate IDs
- the decision hash must match the exact candidate version being reviewed
- reviewer and reviewedAt are mandatory
- approval requires every scientific-review check to be true
- rejected rows cannot be promoted
- editedMessages may change only the conversation, never provenance/split identity
- original candidate content is hashed into the promoted review record for auditability
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_CHECKS = (
    "sourceSupport",
    "citationIntegrity",
    "scopeAndUncertainty",
    "diagnosticDifferential",
    "numericalContext",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{lineno}: each row must be a JSON object")
        rows.append(value)
    return rows


def canonical_hash(row: dict[str, Any]) -> str:
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_iso8601(value: str) -> None:
    candidate = value.strip()
    if not candidate:
        raise ValueError("reviewedAt must not be empty")
    try:
        datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"reviewedAt is not ISO-8601: {value}") from exc


def validate_messages(messages: Any) -> None:
    if not isinstance(messages, list) or not messages:
        raise ValueError("editedMessages must be a non-empty list")
    for idx, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError(f"editedMessages[{idx}] must be an object")
        if message.get("role") not in {"system", "user", "assistant"}:
            raise ValueError(f"editedMessages[{idx}] has invalid role")
        if not isinstance(message.get("content"), str) or not message["content"].strip():
            raise ValueError(f"editedMessages[{idx}] requires non-empty content")
    if messages[-1].get("role") != "assistant":
        raise ValueError("editedMessages must end with an assistant response")


def validate_checks(checks: Any, rid: str, outcome: str) -> dict[str, bool]:
    if not isinstance(checks, dict):
        raise ValueError(f"candidate {rid} missing scientific review checks")
    unknown = set(checks) - set(REQUIRED_CHECKS)
    missing = set(REQUIRED_CHECKS) - set(checks)
    if unknown:
        raise ValueError(f"candidate {rid} has unknown review checks: {sorted(unknown)}")
    if missing:
        raise ValueError(f"candidate {rid} missing review checks: {sorted(missing)}")
    normalized: dict[str, bool] = {}
    for key in REQUIRED_CHECKS:
        value = checks[key]
        if not isinstance(value, bool):
            raise ValueError(f"candidate {rid} review check {key} must be boolean")
        normalized[key] = value
    if outcome == "approved" and not all(normalized.values()):
        failed = [key for key, value in normalized.items() if not value]
        raise ValueError(f"approved candidate {rid} has failed review checks: {failed}")
    return normalized


def index_candidates(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, str) or not rid.strip():
            raise ValueError("candidate missing id")
        if rid in indexed:
            raise ValueError(f"duplicate candidate id: {rid}")
        if row.get("reviewStatus") != "generated_unreviewed":
            raise ValueError(f"candidate {rid} is not generated_unreviewed")
        if not row.get("splitGroup"):
            raise ValueError(f"candidate {rid} missing splitGroup")
        if not row.get("provenance"):
            raise ValueError(f"candidate {rid} missing provenance")
        indexed[rid] = row
    return indexed


def index_decisions(rows: list[dict[str, Any]], candidates: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for decision in rows:
        rid = decision.get("recordId")
        if not isinstance(rid, str) or not rid.strip():
            raise ValueError("review decision missing recordId")
        if rid not in candidates:
            raise ValueError(f"review decision references unknown candidate: {rid}")
        if rid in indexed:
            raise ValueError(f"duplicate review decision for candidate: {rid}")
        expected_hash = canonical_hash(candidates[rid])
        supplied_hash = decision.get("candidateSha256")
        if not isinstance(supplied_hash, str) or supplied_hash != expected_hash:
            raise ValueError(f"candidate {rid} review hash does not match current candidate")
        outcome = decision.get("decision")
        if outcome not in {"approved", "rejected"}:
            raise ValueError(f"candidate {rid} has invalid decision: {outcome}")
        reviewer = decision.get("reviewer")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError(f"candidate {rid} missing reviewer")
        reviewed_at = decision.get("reviewedAt")
        if not isinstance(reviewed_at, str):
            raise ValueError(f"candidate {rid} missing reviewedAt")
        validate_iso8601(reviewed_at)
        checks = validate_checks(decision.get("checks"), rid, outcome)
        notes = decision.get("notes", "")
        if outcome == "rejected" and (not isinstance(notes, str) or not notes.strip()):
            raise ValueError(f"rejected candidate {rid} requires notes")
        if outcome == "rejected" and "editedMessages" in decision:
            raise ValueError(f"rejected candidate {rid} cannot include editedMessages")
        if "editedMessages" in decision:
            validate_messages(decision["editedMessages"])
        normalized = copy.deepcopy(decision)
        normalized["checks"] = checks
        indexed[rid] = normalized
    return indexed


def promote(candidate: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    row = copy.deepcopy(candidate)
    original_hash = canonical_hash(candidate)
    if decision.get("candidateSha256") not in {None, original_hash}:
        raise ValueError(f"candidate {candidate.get('id')} review hash does not match current candidate")
    if "editedMessages" in decision:
        row["messages"] = copy.deepcopy(decision["editedMessages"])
    row["reviewStatus"] = "reviewed"
    row["review"] = {
        "decision": "approved",
        "reviewer": decision["reviewer"].strip(),
        "reviewedAt": decision["reviewedAt"].strip(),
        "notes": decision.get("notes", "").strip() if isinstance(decision.get("notes", ""), str) else "",
        "candidateSha256": original_hash,
        "messagesEdited": "editedMessages" in decision,
        "checks": copy.deepcopy(decision.get("checks", {})),
    }
    return row


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--decisions", required=True)
    ap.add_argument("--reviewed-output", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--allow-undecided", action="store_true")
    args = ap.parse_args()

    candidates = index_candidates(load_jsonl(Path(args.candidates)))
    if not candidates:
        raise ValueError("candidate corpus is empty")
    decisions = index_decisions(load_jsonl(Path(args.decisions)), candidates)

    undecided = sorted(set(candidates) - set(decisions))
    if undecided and not args.allow_undecided:
        sample = ", ".join(undecided[:5])
        raise ValueError(f"{len(undecided)} candidates lack review decisions; sample: {sample}")

    reviewed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    edited = 0
    for rid in sorted(decisions):
        decision = decisions[rid]
        candidate = candidates[rid]
        if decision["decision"] == "approved":
            reviewed.append(promote(candidate, decision))
            edited += int("editedMessages" in decision)
        else:
            rejected.append({
                "recordId": rid,
                "reviewer": decision["reviewer"].strip(),
                "reviewedAt": decision["reviewedAt"].strip(),
                "notes": decision["notes"].strip(),
                "candidateSha256": canonical_hash(candidate),
                "checks": decision["checks"],
            })

    write_jsonl(Path(args.reviewed_output), reviewed)
    report = {
        "candidateRecords": len(candidates),
        "decisions": len(decisions),
        "approved": len(reviewed),
        "rejected": len(rejected),
        "undecided": len(undecided),
        "approvedWithMessageEdits": edited,
        "rejections": rejected,
        "undecidedRecordIds": undecided,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"rejections", "undecidedRecordIds"}}))


if __name__ == "__main__":
    main()
