#!/usr/bin/env python3
"""Regression guard for source-identity semantics used by model-tuning audits.

This intentionally checks the shared contract directly.  It protects the
comparison semantics required by corpus deduplication and held-out isolation
without rewriting the original citation/source metadata.
"""
from source_identity import canonical_source_identity, canonical_sources


def assert_same(*values: str) -> None:
    identities = {canonical_source_identity(value) for value in values}
    assert len(identities) == 1, (values, identities)


def assert_different(left: str, right: str) -> None:
    assert canonical_source_identity(left) != canonical_source_identity(right), (left, right)


def main() -> None:
    # DOI aliases must identify the same scientific source.
    assert_same(
        "doi:10.1000/XYZ.123",
        "https://doi.org/10.1000/xyz.123",
        "http://dx.doi.org/10.1000/xyz.123",
    )

    # Transport aliases, default ports, fragments, and tracking parameters are
    # comparison noise and must not manufacture independent evidence.
    assert_same(
        "http://example.org/paper",
        "https://example.org/paper",
        "https://example.org:443/paper#results",
        "https://example.org/paper?utm_source=newsletter",
        "https://example.org/paper?gclid=abc123",
    )

    # Meaningful query parameters and non-default ports remain distinct.
    assert_different(
        "https://example.org/paper?section=methods",
        "https://example.org/paper?section=results",
    )
    assert_different(
        "https://example.org:8443/paper",
        "https://example.org/paper",
    )

    # Set-level canonicalization must deduplicate aliases while preserving
    # genuinely different sources.
    result = canonical_sources([
        "http://example.org/paper?utm_medium=email",
        "https://example.org:443/paper",
        "https://example.org/paper?section=methods",
        "doi:10.1000/xyz.123",
        "https://doi.org/10.1000/XYZ.123",
    ])
    assert len(result) == 3, result

    print("source identity parity guard: ok")


if __name__ == "__main__":
    main()
