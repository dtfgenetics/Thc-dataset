#!/usr/bin/env python3
"""Regression tests for Grow Doc text SFT leakage controls."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build-text-sft.py"
SPEC = importlib.util.spec_from_file_location("build_text_sft", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class SplitGroupTests(unittest.TestCase):
    def test_shared_sources_form_transitive_component(self) -> None:
        profiles = [
            {
                "id": "a",
                "reviewStatus": "reviewed",
                "sources": [{"title": "S1", "doi": "10.1000/example"}],
            },
            {
                "id": "b",
                "reviewStatus": "reviewed",
                "sources": [
                    {"title": "S1", "url": "https://doi.org/10.1000/example"},
                    {"title": "S2", "url": "https://example.org/paper"},
                ],
            },
            {
                "id": "c",
                "reviewStatus": "reviewed",
                "sources": [{"title": "S2", "url": "https://example.org/paper/"}],
            },
            {
                "id": "d",
                "reviewStatus": "reviewed",
                "sources": [{"title": "S3", "url": "https://example.org/independent"}],
            },
        ]

        groups = mod.build_split_groups(profiles)

        self.assertEqual(groups["a"], groups["b"])
        self.assertEqual(groups["b"], groups["c"])
        self.assertNotEqual(groups["a"], groups["d"])

    def test_doi_normalization_matches_common_forms(self) -> None:
        self.assertEqual(
            mod.normalize_doi("10.3389/fpls.2019.01120"),
            mod.normalize_doi("https://doi.org/10.3389/fpls.2019.01120"),
        )
        self.assertEqual(
            mod.normalize_doi("DOI: 10.3389/FPLS.2019.01120"),
            "doi:10.3389/fpls.2019.01120",
        )

    def test_unreviewed_profile_does_not_generate_records(self) -> None:
        profile = {
            "id": "draft-profile",
            "name": "Draft profile",
            "reviewStatus": "draft",
            "sources": [{"title": "Source", "url": "https://example.org/source"}],
        }
        self.assertEqual(mod.build(profile, "source-component-test"), [])


if __name__ == "__main__":
    unittest.main()
