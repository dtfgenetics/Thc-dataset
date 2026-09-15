#!/usr/bin/env python3
"""Regression vectors for Grow Doc's shared comparison-only source identity contract."""
from source_identity import canonical_source_identity


def self_test() -> None:
    positive = [
        ("doi:10.1234/ABC", "doi:10.1234/abc"),
        ("10.1234/ABC", "doi:10.1234/abc"),
        ("https://doi.org/10.1234/AbC", "doi:10.1234/abc"),
        ("https://dx.doi.org/10.1234/AbC", "doi:10.1234/abc"),
        ("http://example.com/path?utm_source=x", "https://example.com/path"),
        ("https://example.com/path/", "https://example.com/path"),
        ("http://example.com:80/path", "https://example.com/path"),
        ("https://example.com:443/path", "https://example.com/path"),
        ("https://example.com/path#section", "https://example.com/path"),
        ("https://example.com/path?fbclid=x&gclid=y", "https://example.com/path"),
    ]
    for raw, expected in positive:
        actual = canonical_source_identity(raw)
        assert actual == expected, (raw, actual, expected)

    negative = [
        ("https://example.com/reference?id=1", "https://example.com/reference?id=2"),
        ("https://example.com:8443/path", "https://example.com/path"),
        ("https://a.example/path", "https://b.example/path"),
    ]
    for left, right in negative:
        assert canonical_source_identity(left) != canonical_source_identity(right), (left, right)


if __name__ == "__main__":
    self_test()
    print("source identity contract: PASS")
