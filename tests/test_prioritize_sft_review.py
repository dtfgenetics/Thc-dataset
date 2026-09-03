import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "prioritize-sft-review.py"
spec = importlib.util.spec_from_file_location("prioritize_sft_review", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def packet(record_id, lane="science_explanation", tier="A", risks=None, sources=None, decision=None):
    return {
        "recordId": record_id,
        "candidateSha256": "a" * 64,
        "lane": lane,
        "evidenceTier": tier,
        "splitGroup": "source-component-001",
        "riskFlags": risks or [],
        "sourceIdentities": sources or ["doi:10.1/example"],
        "decisionTemplate": {"decision": decision},
    }


class PrioritizeReviewTests(unittest.TestCase):
    def test_numerical_claims_rank_first(self):
        rows = [
            packet("plain", lane="diagnostic_reasoning"),
            packet("numeric", risks=["numerical_claim_review_required"]),
        ]
        queue = mod.build_queue(rows)
        self.assertEqual(queue[0]["recordId"], "numeric")
        self.assertGreater(queue[0]["priorityScore"], queue[1]["priorityScore"])

    def test_diagnostic_reasoning_outranks_science_when_risk_equal(self):
        rows = [packet("science"), packet("diagnostic", lane="diagnostic_reasoning")]
        queue = mod.build_queue(rows)
        self.assertEqual(queue[0]["recordId"], "diagnostic")

    def test_duplicate_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate review packet"):
            mod.build_queue([packet("dup"), packet("dup")])

    def test_decided_packet_rejected(self):
        with self.assertRaisesRegex(ValueError, "must remain undecided"):
            mod.build_queue([packet("done", decision="approved")])

    def test_queue_never_approves_records(self):
        queue = mod.build_queue([packet("pending")])
        self.assertEqual(queue[0]["reviewStatus"], "pending_human_review")
        self.assertNotIn("decision", queue[0])
        self.assertEqual(queue[0]["reviewRank"], 1)


if __name__ == "__main__":
    unittest.main()
