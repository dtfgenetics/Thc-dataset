#!/usr/bin/env python3
"""Shared comparison-only source identity normalization for Grow Doc model tuning.

This module never rewrites stored citation/source metadata. It only creates stable
identities for deduplication, provenance joins, and train/evaluation isolation.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "dclid", "msclkid"}


def canonical_source_identity(value: str) -> str:
    """Return a conservative DOI/URL identity without mutating source metadata."""
    raw = (value or "").strip()
    if not raw:
        return ""

    lowered = raw.lower()
    if lowered.startswith("url:"):
        return canonical_source_identity(raw[4:].strip())
    if lowered.startswith("doi:"):
        payload = raw[4:].strip()
        if not payload:
            return ""
        if payload.lower().startswith(("http://", "https://")):
            canonical = canonical_source_identity(payload)
            return canonical if canonical.startswith("doi:") else f"doi:{payload.lower()}"
        return f"doi:{payload.lower()}"
    if DOI_RE.fullmatch(raw):
        return f"doi:{raw.lower()}"

    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return raw

    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    if host in {"doi.org", "www.doi.org", "dx.doi.org"}:
        payload = path.lstrip("/")
        return f"doi:{payload.lower()}" if payload else ""

    port = parsed.port
    netloc = host
    if port and not ((parsed.scheme.lower() == "http" and port == 80) or (parsed.scheme.lower() == "https" and port == 443)):
        netloc = f"{host}:{port}"

    normalized_path = path.rstrip("/") or "/"
    query_pairs = []
    for key, query_value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered_key = key.lower()
        if lowered_key.startswith("utm_") or lowered_key in TRACKING_QUERY_KEYS:
            continue
        query_pairs.append((key, query_value))
    normalized_query = urlencode(query_pairs, doseq=True)
    return urlunsplit(("https", netloc, normalized_path, normalized_query, ""))


def canonical_sources(values) -> set[str]:
    """Canonicalize an iterable of source identifiers, dropping empty values."""
    return {
        identity
        for value in values
        for identity in [canonical_source_identity(str(value))]
        if identity
    }
