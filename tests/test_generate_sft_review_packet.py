import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate-sft-review-packet.py"
spec = importlib.util.spec_from_file_location("generate_sft_review_packet", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


class ReviewPacketTests(unittest.TestCase):
    def candidate(self):
        return {
            "id": "growdoc:test:1",
            "reviewStatus": "generated_unreviewed",
            "lane": "grounded_qa",
            "evidenceTier": "B",
            "splitGroup": "source-component-abc",
            "messages": [
                {"role": "user", "content": "What should I check?"},
                {"role": "assistant", "content": "Check the environment before assigning a cause."},
            ],
            "provenance": [
                {"sourceTitle": "Example paper", "doi": "https://doi.org/10.1000/XYZ"}
            ],
        }

    def test_packet_preserves_candidate_hash_and_blank_decision(self):
        row = self.candidate()
        packet = mod.build_packet(row)
        self.assertEqual(packet["candidateSha256"], mod.canonical_hash(row))
        self.assertEqual(packet["sourceIdentities"], ["doi:10.1000/xyz"])
        self.assertIsNone(packet["decisionTemplate"]["decision"])
        self.assertTrue(all(v is None for v in packet["reviewChecklist"].values()))

    def test_flags_numeric_claims_for_manual_review(self):
        row = self.candidate()
        row["messages"][-1]["content"] = "A reading of 900 ppm may require context."
        packet = mod.build_packet(row)
        self.assertIn("numerical_claim_review_required", packet["riskFlags"])

    def test_flags_tier_c_and_weak_locator(self):
        row = self.candidate()
        row["evidenceTier"] = "C"
        row["provenance"] = [{"sourceTitle": "Extension note"}]
        packet = mod.build_packet(row)
        self.assertIn("tier_c_evidence", packet["riskFlags"])
        self.assertIn("source_without_doi_or_url", packet["riskFlags"])

    def test_rejects_non_generated_candidates(self):
        row = self.candidate()
        row["reviewStatus"] = "reviewed"
        with self.assertRaises(ValueError):
            mod.build_packet(row)

    def test_main_outputs_one_packet_per_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidates = root / "candidates.jsonl"
            output = root / "packet.jsonl"
            report = root / "report.json"
            row = self.candidate()
            candidates.write_text(json.dumps(row) + "\n", encoding="utf-8")

            old_argv = __import__("sys").argv
            try:
                __import__("sys").argv = [
                    "generate-sft-review-packet.py",
                    "--candidates", str(candidates),
                    "--output", str(output),
                    "--report", str(report),
                ]
                mod.main()
            finally:
                __import__("sys").argv = old_argv

            packets = [json.loads(line) for line in output.read_text().splitlines() if line.strip()]
            summary = json.loads(report.read_text())
            self.assertEqual(len(packets), 1)
            self.assertEqual(summary["reviewPackets"], 1)
            self.assertEqual(summary["splitGroups"], 1)


if __name__ == "__main__":
    unittest.main()
