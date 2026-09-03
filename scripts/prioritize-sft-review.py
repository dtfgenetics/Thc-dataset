#!/usr/bin/env python3
"""Build a deterministic, non-approving review queue for Grow Doc SFT packets.

The queue ranks higher-risk and higher-value candidates first while preserving the
human-review boundary. It never writes approval decisions or changes candidate data.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

RISK_WEIGHTS = {
    "numerical_claim_review_required": 50,
    "tier_c_evidence": 40,
    "source_without_doi_or_url": 25,
}

LANE_WEIGHTS = {
    "diagnostic_reasoning": 20,
    "grounded_qa": 15,
    "science_explanation": 10,
}

EVIDENCE_WEIGHTS = {"A": 6, "B": 3, "C": 0}


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


def validate_packet(packet: dict[str, Any]) -> None:
    rid = packet.get("recordId")
    if not isinstance(rid, str) or not rid.strip():
        raise ValueError("review packet missing recordId")
    if packet.get("evidenceTier") not in {"A", "B", "C"}:
        raise ValueError(f"review packet {rid} has invalid evidenceTier")
    if not isinstance(packet.get("splitGroup"), str) or not packet["splitGroup"].strip():
        raise ValueError(f"review packet {rid} missing splitGroup")
    if not isinstance(packet.get("riskFlags"), list):
        raise ValueError(f"review packet {rid} riskFlags must be a list")
    if not packet.get("candidateSha256"):
        raise ValueError(f"review packet {rid} missing candidateSha256")
    decision = packet.get("decisionTemplate")
    if not isinstance(decision, dict) or decision.get("decision") is not None:
        raise ValueError(f"review packet {rid} must remain undecided")


def priority_score(packet: dict[str, Any]) -> int:
    score = LANE_WEIGHTS.get(str(packet.get("lane")), 0)
    score += EVIDENCE_WEIGHTS.get(str(packet.get("evidenceTier")), 0)
    for flag in sorted(set(str(flag) for flag in packet.get("riskFlags", []))):
        score += RISK_WEIGHTS.get(flag, 10)
    # Multiple independent sources make a record especially useful once reviewed.
    score += min(len(set(packet.get("sourceIdentities") or [])), 5)
    return score


def priority_reasons(packet: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    flags = sorted(set(str(flag) for flag in packet.get("riskFlags", [])))
    reasons.extend(flags)
    lane = str(packet.get("lane") or "")
    if lane in LANE_WEIGHTS:
        reasons.append(f"lane:{lane}")
    reasons.append(f"evidence_tier:{packet['evidenceTier']}")
    return reasons


def build_queue(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    queue: list[dict[str, Any]] = []
    for packet in packets:
        validate_packet(packet)
        rid = packet["recordId"]
        if rid in seen:
            raise ValueError(f"duplicate review packet recordId: {rid}")
        seen.add(rid)
        queue.append({
            "recordId": rid,
            "candidateSha256": packet["candidateSha256"],
            "priorityScore": priority_score(packet),
            "priorityReasons": priority_reasons(packet),
            "lane": packet.get("lane"),
            "evidenceTier": packet["evidenceTier"],
            "splitGroup": packet["splitGroup"],
            "riskFlags": packet.get("riskFlags", []),
            "sourceIdentities": packet.get("sourceIdentities", []),
            "reviewStatus": "pending_human_review",
        })

    queue.sort(key=lambda row: (-row["priorityScore"], str(row["lane"]), row["recordId"]))
    for rank, row in enumerate(queue, 1):
        row["reviewRank"] = rank
    return queue


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--packets", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    packets = load_jsonl(Path(args.packets))
    if not packets:
        raise ValueError("review packet corpus is empty")
    queue = build_queue(packets)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in queue), encoding="utf-8")

    report = {
        "queuedRecords": len(queue),
        "riskFlagCounts": dict(Counter(flag for row in queue for flag in row["riskFlags"])),
        "laneCounts": dict(Counter(str(row["lane"]) for row in queue)),
        "evidenceTierCounts": dict(Counter(row["evidenceTier"] for row in queue)),
        "highRiskRecords": sum(1 for row in queue if row["riskFlags"]),
        "topPriorityScore": queue[0]["priorityScore"],
        "topPriorityRecordIds": [row["recordId"] for row in queue[:10]],
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
