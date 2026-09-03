import importlib.util
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


def checks(**overrides):
    values = {key: True for key in mod.REQUIRED_CHECKS}
    values.update(overrides)
    return values


def decision(row, outcome="approved", **extra):
    value = {
        "recordId": row["id"],
        "candidateSha256": mod.canonical_hash(row),
        "decision": outcome,
        "reviewer": "reviewer-a",
        "reviewedAt": "2026-09-03T01:00:00-05:00",
        "checks": checks(),
    }
    value.update(extra)
    return value


class PromotionTests(unittest.TestCase):
    def test_approved_record_preserves_provenance_and_adds_audit_hash(self):
        row = candidate()
        reviewed = mod.index_decisions([decision(row)], {"r1": row})["r1"]
        promoted = mod.promote(row, reviewed)
        self.assertEqual(promoted["reviewStatus"], "reviewed")
        self.assertEqual(promoted["splitGroup"], row["splitGroup"])
        self.assertEqual(promoted["provenance"], row["provenance"])
        self.assertEqual(promoted["review"]["candidateSha256"], mod.canonical_hash(row))
        self.assertEqual(promoted["review"]["checks"], checks())
        self.assertFalse(promoted["review"]["messagesEdited"])

    def test_message_edit_is_allowed_only_inside_messages(self):
        row = candidate()
        edited_messages = [
            {"role": "user", "content": "What does the evidence support?"},
            {"role": "assistant", "content": "The cited source supports only the scoped claim; broader inference is uncertain."},
        ]
        reviewed = mod.index_decisions([decision(
            row,
            notes="Tightened uncertainty language",
            editedMessages=edited_messages,
        )], {"r1": row})["r1"]
        promoted = mod.promote(row, reviewed)
        self.assertNotEqual(promoted["messages"], row["messages"])
        self.assertEqual(promoted["provenance"], row["provenance"])
        self.assertEqual(promoted["splitGroup"], row["splitGroup"])
        self.assertTrue(promoted["review"]["messagesEdited"])

    def test_rejection_requires_notes(self):
        row = candidate()
        with self.assertRaisesRegex(ValueError, "requires notes"):
            mod.index_decisions([decision(row, outcome="rejected")], {"r1": row})

    def test_unknown_and_duplicate_decisions_are_rejected(self):
        row = candidate()
        unknown = decision(row)
        unknown["recordId"] = "missing"
        with self.assertRaisesRegex(ValueError, "unknown candidate"):
            mod.index_decisions([unknown], {"r1": row})
        duplicate = decision(row)
        with self.assertRaisesRegex(ValueError, "duplicate review decision"):
            mod.index_decisions([duplicate, duplicate], {"r1": row})

    def test_rejected_record_cannot_carry_edited_messages(self):
        row = candidate()
        rejected = decision(
            row,
            outcome="rejected",
            notes="Unsupported claim",
            editedMessages=[{"role": "assistant", "content": "No"}],
        )
        with self.assertRaisesRegex(ValueError, "cannot include editedMessages"):
            mod.index_decisions([rejected], {"r1": row})

    def test_candidate_gate_rejects_already_reviewed_input(self):
        row = candidate()
        row["reviewStatus"] = "reviewed"
        with self.assertRaisesRegex(ValueError, "not generated_unreviewed"):
            mod.index_candidates([row])

    def test_stale_or_tampered_candidate_hash_is_rejected(self):
        row = candidate()
        bad = decision(row)
        bad["candidateSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "review hash does not match"):
            mod.index_decisions([bad], {"r1": row})

    def test_approval_requires_all_scientific_checks_to_pass(self):
        row = candidate()
        bad = decision(row)
        bad["checks"]["numericalContext"] = False
        with self.assertRaisesRegex(ValueError, "failed review checks"):
            mod.index_decisions([bad], {"r1": row})

    def test_missing_or_non_boolean_review_checks_are_rejected(self):
        row = candidate()
        missing = decision(row)
        missing["checks"].pop("citationIntegrity")
        with self.assertRaisesRegex(ValueError, "missing review checks"):
            mod.index_decisions([missing], {"r1": row})

        invalid = decision(row)
        invalid["checks"]["sourceSupport"] = "yes"
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            mod.index_decisions([invalid], {"r1": row})

    def test_rejection_may_record_failed_checks_but_still_requires_notes(self):
        row = candidate()
        rejected = decision(row, outcome="rejected", notes="Source does not support answer")
        rejected["checks"]["sourceSupport"] = False
        indexed = mod.index_decisions([rejected], {"r1": row})
        self.assertFalse(indexed["r1"]["checks"]["sourceSupport"])


if __name__ == "__main__":
    unittest.main()
