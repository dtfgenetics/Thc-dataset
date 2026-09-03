import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "split-reviewed-sft.py"
spec = importlib.util.spec_from_file_location("split_reviewed_sft", MODULE_PATH)
m = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(m)


def row(rid, group, doi, status="reviewed", text=None):
    return {
        "id": rid,
        "lane": "grounded_qa",
        "reviewStatus": status,
        "splitGroup": group,
        "messages": [
            {"role": "system", "content": "Grow Doc"},
            {"role": "user", "content": text or f"question {rid}"},
            {"role": "assistant", "content": f"answer {rid}"},
        ],
        "provenance": [{"sourceTitle": f"Source {rid}", "doi": doi, "url": None}],
    }


class SplitReviewedSftTests(unittest.TestCase):
    def test_rejects_unreviewed(self):
        with self.assertRaisesRegex(ValueError, "not human reviewed"):
            m.validate_rows([row("a", "g1", "10.1/a", status="generated_unreviewed")], set(), set())

    def test_rejects_locked_overlap(self):
        with self.assertRaisesRegex(ValueError, "locked evaluation"):
            m.validate_rows([row("a", "g1", "10.1/a")], {"a"}, set())

    def test_partition_keeps_groups_atomic(self):
        rows = [
            row("a1", "g1", "10.1/a"),
            row("a2", "g1", "10.1/a"),
            row("b1", "g2", "10.1/b"),
            row("c1", "g3", "10.1/c"),
        ]
        groups = {}
        for r in rows:
            groups.setdefault(r["splitGroup"], []).append(r)
        dev_groups = m.choose_dev_groups(groups, 0.25, "test")
        train = [r for r in rows if r["splitGroup"] not in dev_groups]
        dev = [r for r in rows if r["splitGroup"] in dev_groups]
        m.assert_no_cross_split_leakage(train, dev)
        self.assertFalse({r["splitGroup"] for r in train} & {r["splitGroup"] for r in dev})

    def test_detects_provenance_leak_even_with_different_groups(self):
        train = [row("a", "g1", "https://doi.org/10.5555/shared")]
        dev = [row("b", "g2", "10.5555/shared")]
        with self.assertRaisesRegex(ValueError, "provenance source identity leakage"):
            m.assert_no_cross_split_leakage(train, dev)

    def test_detects_normalized_message_duplicate(self):
        a = row("a", "g1", "10.1/a", text="Same   question")
        b = row("b", "g2", "10.1/b", text="same question")
        b["messages"][2]["content"] = a["messages"][2]["content"]
        with self.assertRaisesRegex(ValueError, "normalized conversation duplicate"):
            m.assert_no_cross_split_leakage([a], [b])


if __name__ == "__main__":
    unittest.main()
