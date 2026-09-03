#!/usr/bin/env python3
"""Generate evidence-rich review packets for Grow Doc SFT candidates.

This tool does not approve training data. It turns immutable generated candidates into a
review-oriented JSONL view with stable hashes, provenance summaries, risk flags, and a
blank decision template. Reviewers still make explicit approve/reject decisions through
promote-reviewed-sft.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

NUMERIC_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|ppm|ppfd|µmol|umol|mol|dli|ec|ms/cm|ph|°[cf]|degrees?)\b", re.I)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{lineno}: row must be an object")
        rows.append(row)
    return rows


def canonical_hash(row: dict[str, Any]) -> str:
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_identity(item: dict[str, Any]) -> str:
    doi = str(item.get("doi") or "").strip().lower()
    if doi:
        doi = doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/").removeprefix("doi:")
        return f"doi:{doi}"
    url = str(item.get("url") or "").strip().lower().rstrip("/")
    if url:
        return f"url:{url}"
    title = str(item.get("sourceTitle") or "").strip().lower()
    return f"title:{title}"


def validate_candidate(row: dict[str, Any]) -> None:
    rid = row.get("id")
    if not isinstance(rid, str) or not rid.strip():
        raise ValueError("candidate missing id")
    if row.get("reviewStatus") != "generated_unreviewed":
        raise ValueError(f"candidate {rid} is not generated_unreviewed")
    if row.get("evidenceTier") not in {"A", "B", "C"}:
        raise ValueError(f"candidate {rid} has invalid evidenceTier")
    if not isinstance(row.get("splitGroup"), str) or not row["splitGroup"].strip():
        raise ValueError(f"candidate {rid} missing splitGroup")
    messages = row.get("messages")
    if not isinstance(messages, list) or not messages or messages[-1].get("role") != "assistant":
        raise ValueError(f"candidate {rid} has invalid messages")
    provenance = row.get("provenance")
    if not isinstance(provenance, list) or not provenance:
        raise ValueError(f"candidate {rid} missing provenance")
    for idx, item in enumerate(provenance):
        if not isinstance(item, dict) or not str(item.get("sourceTitle") or "").strip():
            raise ValueError(f"candidate {rid} provenance[{idx}] missing sourceTitle")


def build_packet(row: dict[str, Any]) -> dict[str, Any]:
    validate_candidate(row)
    assistant_text = "\n".join(
        str(m.get("content") or "") for m in row["messages"] if m.get("role") == "assistant"
    )
    provenance = row["provenance"]
    source_ids = sorted({source_identity(p) for p in provenance})
    risks: list[str] = []
    if row["evidenceTier"] == "C":
        risks.append("tier_c_evidence")
    if any(not (p.get("doi") or p.get("url")) for p in provenance):
        risks.append("source_without_doi_or_url")
    if NUMERIC_RE.search(assistant_text):
        risks.append("numerical_claim_review_required")

    return {
        "recordId": row["id"],
        "candidateSha256": canonical_hash(row),
        "lane": row.get("lane"),
        "evidenceTier": row["evidenceTier"],
        "splitGroup": row["splitGroup"],
        "messages": row["messages"],
        "provenance": provenance,
        "sourceIdentities": source_ids,
        "riskFlags": risks,
        "reviewChecklist": {
            "claimsSupportedBySources": None,
            "citationsMatchClaims": None,
            "diagnosticDifferentialsPreserved": None,
            "uncertaintyCalibrated": None,
            "numericalContextQualified": None,
            "noUnsupportedUniversalThresholds": None,
            "clearAndInstructionCompliant": None,
        },
        "decisionTemplate": {
            "recordId": row["id"],
            "decision": None,
            "reviewer": None,
            "reviewedAt": None,
            "notes": "",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    rows = load_jsonl(Path(args.candidates))
    if not rows:
        raise ValueError("candidate corpus is empty")

    seen: set[str] = set()
    packets: list[dict[str, Any]] = []
    for row in rows:
        rid = row.get("id")
        if rid in seen:
            raise ValueError(f"duplicate candidate id: {rid}")
        seen.add(rid)
        packets.append(build_packet(row))

    packets.sort(key=lambda p: (p["splitGroup"], str(p["lane"]), p["recordId"]))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in packets), encoding="utf-8")

    risk_counts = Counter(flag for packet in packets for flag in packet["riskFlags"])
    report = {
        "candidateRecords": len(rows),
        "reviewPackets": len(packets),
        "splitGroups": len({p["splitGroup"] for p in packets}),
        "lanes": dict(Counter(str(p["lane"]) for p in packets)),
        "evidenceTiers": dict(Counter(p["evidenceTier"] for p in packets)),
        "riskFlags": dict(risk_counts),
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
