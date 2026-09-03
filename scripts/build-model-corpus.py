#!/usr/bin/env python3
"""Build deterministic Grow Doc RAG/SFT/quarantine corpora from reviewed diagnostic profiles.

Uses only stdlib. The builder teaches evidence-grounded behavior; factual claims remain attached
to supplied retrieval context and provenance instead of being converted into context-free SFT.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/diagnostic-profiles.jsonl"
DEFAULT_EVAL = ROOT / "model_tuning/eval/heldout_v1.jsonl"
DEFAULT_OUT = ROOT / "model_tuning/generated"


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())).strip()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_id(source: dict) -> str:
    if source.get("doi"):
        return f"doi:{source['doi'].strip().lower()}"
    if source.get("url"):
        return f"url:{source['url'].strip()}"
    return f"source:{sha((source.get('title') or '') + '|' + (source.get('organization') or ''))[:16]}"


def load_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def source_metadata(source: dict) -> dict:
    return {
        "title": source.get("title"),
        "organization": source.get("organization"),
        "publisher": source.get("publisher"),
        "authors": source.get("authors") or [],
        "publicationDate": source.get("publicationDate"),
        "year": source.get("year"),
        "accessedDate": source.get("accessedDate"),
        "doi": source.get("doi"),
        "url": source.get("url"),
    }


def make_rag(profile: dict) -> tuple[list[dict], list[dict]]:
    good = []
    quarantine = []
    seen = set()
    for source in profile.get("sources") or []:
        sid = source_id(source)
        claims = source.get("supportedClaims") or []
        if not (source.get("doi") or source.get("url")) or not claims:
            quarantine.append(
                {
                    "profile_id": profile.get("id"),
                    "reason": "source_missing_provenance_or_supported_claims",
                    "source": source,
                }
            )
            continue
        for claim in claims:
            key = norm(claim)
            if not key or key in seen:
                continue
            seen.add(key)
            metadata = source_metadata(source)
            good.append(
                {
                    "id": f"rag-{profile['id']}-{sha(sid+'|'+key)[:12]}",
                    "profile_id": profile["id"],
                    "profile_ids": [profile["id"]],
                    "profile_name": profile.get("name"),
                    "category": profile.get("category"),
                    "claim": claim.strip(),
                    "claim_sha256": sha(key),
                    "source_id": sid,
                    "source_ids": [sid],
                    "source": metadata,
                    "sources": [{"source_id": sid, **metadata}],
                    "review_status": profile.get("reviewStatus"),
                    "retrieval_only": True,
                }
            )
    return good, quarantine


def evidence_block(rows: list[dict], limit: int = 5) -> str:
    return "\n".join(f"[{row['source_id']}] {row['claim']}" for row in rows[:limit])


def make_sft(profile: dict, rag_rows: list[dict]) -> list[dict]:
    if not rag_rows:
        return []
    context = evidence_block(rag_rows)
    cites = []
    for row in rag_rows[:5]:
        if row["source_id"] not in cites:
            cites.append(row["source_id"])
    summary = (profile.get("summary") or "").strip()
    indicators = profile.get("indicators") or []
    exclusions = profile.get("exclusions") or []
    lookalikes = profile.get("lookAlikes") or []
    confirmation = profile.get("confirmation") or []
    warnings = profile.get("warnings") or []
    response = (
        f"Evidence-supported interpretation: {summary}\n\n"
        f"Key supporting observations: {'; '.join(indicators[:4]) if indicators else 'Use the supplied evidence and observed pattern.'}\n"
        f"Important alternatives: {', '.join(lookalikes[:5]) if lookalikes else 'Other biotic and abiotic causes remain possible.'}\n"
        f"Confirmation: {'; '.join(confirmation[:3]) if confirmation else 'Use qualified diagnostic confirmation before a species-level claim.'}\n"
        f"Limitations: {'; '.join(warnings[:2]) if warnings else 'Do not generalize beyond the supplied evidence.'}\n"
        f"Citations: {' '.join(cites)}"
    )
    diagnostic = {
        "id": f"sft-{profile['id']}-diagnostic",
        "task": "grounded_diagnostic_reasoning",
        "messages": [
            {
                "role": "system",
                "content": "Answer only from the supplied evidence. Separate observation, differential diagnosis, and confirmation. Cite source identifiers and state uncertainty.",
            },
            {
                "role": "user",
                "content": f"Evidence:\n{context}\n\nUsing this evidence, explain the diagnostic pattern for {profile.get('name')} without claiming that an image alone confirms the cause.",
            },
            {"role": "assistant", "content": response},
        ],
        "source_ids": cites,
        "profile_id": profile["id"],
        "grounded": True,
        "context_required": True,
    }
    differential = {
        "id": f"sft-{profile['id']}-differential",
        "task": "differential_and_next_test",
        "messages": [
            {
                "role": "system",
                "content": "Use retrieved evidence, avoid universal thresholds, and prefer discriminating tests over confident guessing.",
            },
            {
                "role": "user",
                "content": f"Evidence:\n{context}\n\nWhat should be distinguished from {profile.get('name')}, and what evidence would reduce uncertainty?",
            },
            {
                "role": "assistant",
                "content": f"Primary differentials: {', '.join(lookalikes[:7]) if lookalikes else 'Competing biotic and abiotic causes.'}\n\nEvidence that reduces uncertainty: {'; '.join(confirmation[:4]) if confirmation else 'Collect representative samples and use qualified diagnostics.'}\n\nDo not overcall the diagnosis when: {'; '.join(exclusions[:3]) if exclusions else 'the supplied evidence does not distinguish the alternatives.'}\n\nCitations: {' '.join(cites)}",
            },
        ],
        "source_ids": cites,
        "profile_id": profile["id"],
        "grounded": True,
        "context_required": True,
    }
    education = {
        "id": f"sft-{profile['id']}-education",
        "task": "science_education",
        "messages": [
            {
                "role": "system",
                "content": "Teach clearly from supplied evidence. Distinguish established facts from limitations and avoid adding uncited facts.",
            },
            {
                "role": "user",
                "content": f"Evidence:\n{context}\n\nTeach a grower what is scientifically established here about {profile.get('name')}, what is not established, and why confirmation matters.",
            },
            {
                "role": "assistant",
                "content": f"What is established: {summary}\n\nWhat is not established: {'; '.join(warnings[:3]) if warnings else 'The evidence does not justify claims beyond its studied context.'}\n\nWhy confirmation matters: {'; '.join(confirmation[:3]) if confirmation else 'Similar symptoms can have different causes, so confirmation prevents false certainty.'}\n\nCitations: {' '.join(cites)}",
            },
        ],
        "source_ids": cites,
        "profile_id": profile["id"],
        "grounded": True,
        "context_required": True,
    }
    return [diagnostic, differential, education]


def eval_fingerprints(path: pathlib.Path) -> set[str]:
    fps = set()
    if not path.exists():
        return fps
    for row in load_jsonl(path):
        prompt = norm(row.get("prompt") or "")
        if prompt:
            fps.add(sha(prompt))
    return fps


def merge_unique_dicts(existing: list[dict], incoming: list[dict], key: str) -> list[dict]:
    seen = {item.get(key) for item in existing}
    out = list(existing)
    for item in incoming:
        value = item.get(key)
        if value not in seen:
            out.append(item)
            seen.add(value)
    return out


def dedupe_rag(rows: list[dict]) -> tuple[list[dict], int, int]:
    """Deduplicate exact normalized claims while retaining all corroborating provenance."""
    by_claim: dict[str, dict] = {}
    duplicate_claims = 0
    merged_provenance_links = 0
    for row in rows:
        fp = row["claim_sha256"]
        if fp not in by_claim:
            by_claim[fp] = row
            continue
        duplicate_claims += 1
        keep = by_claim[fp]
        before_sources = len(keep["source_ids"])
        keep["source_ids"] = list(dict.fromkeys(keep["source_ids"] + row.get("source_ids", [row["source_id"]])))
        keep["profile_ids"] = list(dict.fromkeys(keep["profile_ids"] + row.get("profile_ids", [row["profile_id"]])))
        keep["sources"] = merge_unique_dicts(keep["sources"], row.get("sources", []), "source_id")
        merged_provenance_links += max(0, len(keep["source_ids"]) - before_sources)
    return list(by_claim.values()), duplicate_claims, merged_provenance_links


def build(input_path: pathlib.Path, eval_path: pathlib.Path) -> tuple[list[dict], list[dict], list[dict], dict]:
    rag = []
    sft = []
    quarantine = []
    seen_profiles = set()
    duplicate_profiles = []
    eval_fps = eval_fingerprints(eval_path)
    for profile in load_jsonl(input_path):
        pid = profile.get("id")
        if not pid or pid in seen_profiles:
            duplicate_profiles.append(pid)
            quarantine.append({"profile_id": pid, "reason": "duplicate_or_missing_profile_id"})
            continue
        seen_profiles.add(pid)
        if profile.get("reviewStatus") != "reviewed":
            quarantine.append(
                {
                    "profile_id": pid,
                    "reason": "profile_not_reviewed",
                    "reviewStatus": profile.get("reviewStatus"),
                }
            )
            continue
        profile_rag, source_quarantine = make_rag(profile)
        quarantine.extend(source_quarantine)
        rag.extend(profile_rag)
        for item in make_sft(profile, profile_rag):
            user_text = next((m["content"] for m in item["messages"] if m["role"] == "user"), "")
            if sha(norm(user_text)) in eval_fps:
                quarantine.append({"profile_id": pid, "reason": "eval_prompt_collision", "sft_id": item["id"]})
            else:
                sft.append(item)

    rag, duplicate_claims, merged_provenance_links = dedupe_rag(rag)
    multi_source_claims = sum(1 for row in rag if len(row.get("source_ids", [])) > 1)
    stats = {
        "input_profiles": len(seen_profiles),
        "duplicate_profile_ids": len(duplicate_profiles),
        "rag_claims": len(rag),
        "sft_examples": len(sft),
        "quarantine_records": len(quarantine),
        "duplicate_claims_removed": duplicate_claims,
        "merged_provenance_links": merged_provenance_links,
        "multi_source_claims": multi_source_claims,
        "sft_tasks": dict(Counter(x["task"] for x in sft)),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "eval_sha256": hashlib.sha256(eval_path.read_bytes()).hexdigest() if eval_path.exists() else None,
        "policy": "reviewed profiles only; source-level claim provenance required; context-required SFT; exact claim dedup with provenance consolidation; eval prompt collision rejection",
    }
    return rag, sft, quarantine, stats


def write_jsonl(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in rows),
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    ap.add_argument("--eval", type=pathlib.Path, default=DEFAULT_EVAL)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()
    try:
        rag, sft, quarantine, stats = build(args.input, args.eval)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if stats["rag_claims"] == 0 or stats["sft_examples"] == 0:
        print("corpus build produced no usable RAG/SFT records", file=sys.stderr)
        return 1
    if stats["duplicate_claims_removed"] > 0 and stats["merged_provenance_links"] == 0:
        print("duplicate claims were removed without retaining any distinct corroborating provenance", file=sys.stderr)
        return 1
    if not args.check_only:
        write_jsonl(args.out / "rag" / "claims_v1.jsonl", rag)
        write_jsonl(args.out / "sft" / "grounded_v1.jsonl", sft)
        write_jsonl(args.out / "quarantine" / "quarantine_v1.jsonl", quarantine)
        (args.out / "manifest_v1.json").write_text(
            json.dumps(stats, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(stats, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
