import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "promote-reviewed-sft.py"
spec = importlib.util.spec_from_file_location("promote_reviewed_sft", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def candidate(rid="r1"):
    return {
        "id": rid,
        "lane": "grounded_qa",
        "messages": [
            {"role": "user", "content": "What does this evidence support?"},
            {"role": "assistant", "content": "It supports the scoped claim."},
        ],
        "reviewStatus": "generated_unreviewed",
        "splitGroup": "source-component-1",
        "evidenceTier": "A",
        "provenance": [{"sourceTitle": "Example", "doi": "10.1000/example"}],
    }


class PromotionTests(unittest.TestCase):
    def test_approved_record_preserves_provenance_and_adds_audit_hash(self):
        row = candidate()
        decision = {
            "recordId": "r1",
            "decision": "approved",
            "reviewer": "reviewer-a",
            "reviewedAt": "2026-09-03T01:00:00-05:00",
        }
        promoted = mod.promote(row, decision)
        self.assertEqual(promoted["reviewStatus"], "reviewed")
        self.assertEqual(promoted["splitGroup"], row["splitGroup"])
        self.assertEqual(promoted["provenance"], row["provenance"])
        self.assertEqual(promoted["review"]["candidateSha256"], mod.canonical_hash(row))
        self.assertFalse(promoted["review"]["messagesEdited"])

    def test_message_edit_is_allowed_only_inside_messages(self):
        row = candidate()
        decision = {
            "recordId": "r1",
            "decision": "approved",
            "reviewer": "reviewer-a",
            "reviewedAt": "2026-09-03",
            "notes": "Tightened uncertainty language",
            "editedMessages": [
                {"role": "user", "content": "What does the evidence support?"},
                {"role": "assistant", "content": "The cited source supports only the scoped claim; broader inference is uncertain."},
            ],
        }
        promoted = mod.promote(row, decision)
        self.assertNotEqual(promoted["messages"], row["messages"])
        self.assertEqual(promoted["provenance"], row["provenance"])
        self.assertEqual(promoted["splitGroup"], row["splitGroup"])
        self.assertTrue(promoted["review"]["messagesEdited"])

    def test_rejection_requires_notes(self):
        rows = [{
            "recordId": "r1",
            "decision": "rejected",
            "reviewer": "reviewer-a",
            "reviewedAt": "2026-09-03",
        }]
        with self.assertRaisesRegex(ValueError, "requires notes"):
            mod.index_decisions(rows, {"r1"})

    def test_unknown_and_duplicate_decisions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown candidate"):
            mod.index_decisions([{
                "recordId": "missing",
                "decision": "approved",
                "reviewer": "reviewer-a",
                "reviewedAt": "2026-09-03",
            }], {"r1"})
        duplicate = {
            "recordId": "r1",
            "decision": "approved",
            "reviewer": "reviewer-a",
            "reviewedAt": "2026-09-03",
        }
        with self.assertRaisesRegex(ValueError, "duplicate review decision"):
            mod.index_decisions([duplicate, duplicate], {"r1"})

    def test_rejected_record_cannot_carry_edited_messages(self):
        with self.assertRaisesRegex(ValueError, "cannot include editedMessages"):
            mod.index_decisions([{
                "recordId": "r1",
                "decision": "rejected",
                "reviewer": "reviewer-a",
                "reviewedAt": "2026-09-03",
                "notes": "Unsupported claim",
                "editedMessages": [{"role": "assistant", "content": "No"}],
            }], {"r1"})

    def test_candidate_gate_rejects_already_reviewed_input(self):
        row = candidate()
        row["reviewStatus"] = "reviewed"
        with self.assertRaisesRegex(ValueError, "not generated_unreviewed"):
            mod.index_candidates([row])


if __name__ == "__main__":
    unittest.main()
