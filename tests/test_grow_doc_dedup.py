#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit-grow-doc-dedup.py"
spec = importlib.util.spec_from_file_location("grow_doc_dedup", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class GrowDocDedupTests(unittest.TestCase):
    def write_jsonl(self, path: pathlib.Path, rows: list[dict]) -> None:
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    def test_prompt_leak_fails_even_when_answer_differs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            train = root / "train_sft.jsonl"
            heldout = root / "heldout_eval.jsonl"
            self.write_jsonl(train, [{"question": "What does VPD describe?", "answer": "A vapor-pressure difference.", "source_id": "train-src"}])
            self.write_jsonl(heldout, [{"question": " WHAT does VPD describe? ", "expected_points": ["Transpiration-driving vapor-pressure difference."], "must_cite": ["eval-src"]}])
            report = module.audit([train, heldout])
            self.assertFalse(report["pass"])
            self.assertEqual(report["totals"]["train_eval_prompt_leak_groups"], 1)
            self.assertEqual(report["totals"]["train_eval_pair_leak_groups"], 0)

    def test_message_prompt_wins_over_generic_task_metadata(self) -> None:
        a = {"task": "science_education", "messages": [{"role": "user", "content": "Explain photoperiod."}]}
        b = {"task": "science_education", "messages": [{"role": "user", "content": "Explain PPFD."}]}
        self.assertNotEqual(module.prompt_text(a), module.prompt_text(b))

    def test_missing_provenance_is_counted_without_rewriting_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            train = root / "train_sft.jsonl"
            self.write_jsonl(train, [{"question": "Explain photoperiod.", "answer": "Daily light and dark duration."}])
            report = module.audit([train])
            self.assertTrue(report["pass"])
            self.assertEqual(report["totals"]["missing_source_metadata"], 1)

    def test_citation_metadata_satisfies_provenance_detection(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            train = root / "train_sft.jsonl"
            self.write_jsonl(train, [{"question": "Explain PPFD.", "answer": "Photon flux density in PAR.", "citations": [{"source_id": "paper-1"}]}])
            report = module.audit([train])
            self.assertEqual(report["totals"]["missing_source_metadata"], 0)


if __name__ == "__main__":
    unittest.main()
