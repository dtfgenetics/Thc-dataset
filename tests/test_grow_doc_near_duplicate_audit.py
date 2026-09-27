#!/usr/bin/env python3
"""Deterministic regression tests for the Grow Doc near-duplicate auditor."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit-grow-doc-near-duplicates.py"
spec = importlib.util.spec_from_file_location("grow_doc_near_duplicates", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class NearDuplicateAuditTests(unittest.TestCase):
    def write_jsonl(self, path: pathlib.Path, rows: list[dict]) -> None:
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    def test_train_eval_paraphrase_fails_closed_and_preserves_sources(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            train = root / "sft.jsonl"
            heldout = root / "heldout_eval.jsonl"
            self.write_jsonl(train, [{"id": "t1", "question": "What does vapor pressure deficit describe in a grow room?", "answer": "VPD describes the vapor-pressure difference driving transpiration.", "source_id": "src-train"}])
            self.write_jsonl(heldout, [{"id": "e1", "question": "What does vapor pressure deficit describe inside a grow room?", "expected_points": ["VPD describes the vapor-pressure difference driving transpiration."], "must_cite": ["src-eval"]}])
            report = module.audit([train, heldout], prompt_threshold=0.70, pair_threshold=0.75)
            self.assertFalse(report["pass"])
            self.assertEqual(report["totals"]["train_eval_contamination"], 1)
            match = report["matches"][0]
            self.assertTrue(match["train_eval_contamination"])
            self.assertEqual(match["left"]["source_ids"], ["src-train"])
            self.assertEqual(match["right"]["source_ids"], ["src-eval"])

    def test_empty_records_do_not_false_positive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            train = root / "train.jsonl"
            heldout = root / "heldout_eval.jsonl"
            self.write_jsonl(train, [{"id": "t-empty", "metadata": {"kind": "placeholder"}}])
            self.write_jsonl(heldout, [{"id": "e-empty", "metadata": {"kind": "placeholder"}}])
            report = module.audit([train, heldout], prompt_threshold=0.70, pair_threshold=0.75)
            self.assertTrue(report["pass"])
            self.assertEqual(report["totals"]["matches"], 0)

    def test_within_training_match_is_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            train = root / "sft.jsonl"
            self.write_jsonl(train, [
                {"id": "a", "question": "Explain photosynthetic photon flux density for growers.", "answer": "PPFD measures photon flux density in PAR."},
                {"id": "b", "question": "Explain photosynthetic photon flux density for a grower.", "answer": "PPFD measures photon flux density across PAR."},
            ])
            report = module.audit([train], prompt_threshold=0.70, pair_threshold=0.75)
            self.assertTrue(report["pass"])
            self.assertGreaterEqual(report["totals"]["within_training_review"], 1)


if __name__ == "__main__":
    unittest.main()
