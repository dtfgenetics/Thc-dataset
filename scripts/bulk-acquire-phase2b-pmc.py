#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bulk_acquisition" / "phase2b"
OUT.mkdir(parents=True, exist_ok=True)
UA = "THC-Plant-Diagnostic-Dataset/1.0 (+https://github.com/dtfgenetics/Thc-dataset)"


def fetch(url: str, timeout: int = 180):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.geturl(), r.headers.get("Content-Type")


def kind(data: bytes):
    if data.startswith(b"\xff\xd8\xff"): return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP": return "webp"
    if data.startswith((b"II*\x00", b"MM\x00*")): return "tif"
    return None


def sha256(data: bytes):
    return hashlib.sha256(data).hexdigest()


def html_candidates(pmcid: str, basename: str):
    page_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
    raw, final, _ = fetch(page_url)
    text = html.unescape(raw.decode("utf-8", "replace")).replace("\\/", "/")
    out = []
    # Match absolute and relative asset URLs that contain the exact JATS graphic basename.
    patterns = [
        rf"https?://[^\s\"'<>]+{re.escape(basename)}[^\s\"'<>]*",
        rf"(?:src|href)=[\"']([^\"']*{re.escape(basename)}[^\"']*)[\"']",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            value = m.group(1) if m.lastindex else m.group(0)
            value = html.unescape(value)
            out.append(urllib.parse.urljoin(final, value))
    # Also accept modern PMC CDN paths where query strings or transforms follow the basename.
    idx = text.find(basename)
    if idx >= 0:
        start = max(0, text.rfind('"', 0, idx) + 1)
        end_candidates = [x for x in (text.find('"', idx), text.find("'", idx), text.find(' ', idx)) if x > idx]
        if end_candidates:
            value = text[start:min(end_candidates)]
            if basename in value:
                out.append(urllib.parse.urljoin(final, value))
    seen = set()
    result = []
    for url in out:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def acquire(target):
    candidates = []
    try:
        candidates.extend(html_candidates(target["pmcid"], target["basename"]))
    except Exception as exc:
        html_error = str(exc)
    else:
        html_error = None
    candidates.extend(target.get("fallbackUrls", []))

    errors = []
    best = None
    for url in candidates:
        try:
            data, final, ctype = fetch(url)
            k = kind(data)
            if not k:
                raise RuntimeError(f"not image type={ctype} bytes={len(data)}")
            if len(data) < 20_000:
                raise RuntimeError(f"image too small: {len(data)}")
            if best is None or len(data) > len(best[0]):
                best = (data, final, ctype, k)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    if best is None:
        if html_error:
            errors.insert(0, f"PMC HTML: {html_error}")
        return {"datasetId":target["datasetId"],"sourceFileId":target["sourceFileId"],"figure":target["figure"],"status":"blocked","error":" | ".join(errors) or "no candidate URLs resolved"}
    data, final, ctype, k = best
    dest = OUT / f"{target['fileStem']}.{k}"
    dest.write_bytes(data)
    return {
        "datasetId":target["datasetId"],"sourceFileId":target["sourceFileId"],"figure":target["figure"],
        "status":"acquired","file":dest.name,"sizeBytes":len(data),"sha256":sha256(data),
        "finalUrl":final,"contentType":ctype,"license":target["license"],"role":target["role"],
        "diagnosticCeiling":target["diagnosticCeiling"],
    }


TARGETS = [
    {
        "datasetId":"DS-112","sourceFileId":"SF-031","pmcid":"PMC10071647","figure":"Figure 13",
        "basename":"42238_2023_178_Fig13_HTML.jpg","fileStem":"DS112_Figure13_trichome_maturation",
        "fallbackUrls":[
            "https://media.springernature.com/full/springer-static/image/art%3A10.1186%2Fs42238-023-00178-9/MediaObjects/42238_2023_178_Fig13_HTML.png",
            "https://media.springernature.com/full/springer-static/image/art%3A10.1186%2Fs42238-023-00178-9/MediaObjects/42238_2023_178_Fig13_HTML.jpg"
        ],
        "license":"CC BY 4.0","role":"trichome maturation reference",
        "diagnosticCeiling":"Clear/translucent/red-brown appearance is genotype/age/context dependent; not a universal harvest-certainty rule."
    },
    {
        "datasetId":"DS-120","sourceFileId":"SF-041","pmcid":"PMC10878361","figure":"Figure 1",
        "basename":"nvad044_fig1.jpg","fileStem":"DS120_Figure1_TSSM_injury_webbing",
        "license":"CC BY 4.0","role":"twospotted-spider-mite feeding injury/webbing reference",
        "diagnosticCeiling":"Cannabis/hemp feeding-injury reference; direct pest evidence/magnification should support organism confirmation."
    },
    {
        "datasetId":"DS-073","sourceFileId":"SF-043","pmcid":"PMC11902214","figure":"Figure 3",
        "basename":"plants-14-00830-g003.jpg","fileStem":"DS073_Figure3_HLVd_cutting_differential",
        "fallbackUrls":[
            "https://mdpi-res.com/d_attachment/plants/plants-14-00830/article_deploy/html/images/plants-14-00830-g003.png",
            "https://mdpi-res.com/d_attachment/plants/plants-14-00830/article_deploy/html/images/plants-14-00830-g003.jpg"
        ],
        "license":"CC BY 4.0","role":"molecularly characterized HLVd cutting/root differential reference",
        "diagnosticCeiling":"HLVd remains suspected from appearance alone; molecular testing is required for confirmation."
    },
    {
        "datasetId":"DS-102","sourceFileId":"SF-044","pmcid":"PMC10779078","figure":"Figure 7",
        "basename":"ijms-25-00014-g007.jpg","fileStem":"DS102_Figure7_HLVd_inflorescence_differential",
        "fallbackUrls":[
            "https://mdpi-res.com/d_attachment/ijms/ijms-25-00014/article_deploy/html/images/ijms-25-00014-g007.png",
            "https://mdpi-res.com/d_attachment/ijms/ijms-25-00014/article_deploy/html/images/ijms-25-00014-g007.jpg"
        ],
        "license":"CC BY 4.0","role":"HTS-confirmed HLVd inflorescence differential reference",
        "diagnosticCeiling":"Genotype-specific expression; photo alone cannot confirm HLVd and asymptomatic infection is possible."
    }
]


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    results = [acquire(t) for t in TARGETS]
    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schemaVersion":"1.0","phase":"bulk-acquisition-phase2b-pmc-reconciliation","createdAt":now,
        "repository":"dtfgenetics/Thc-dataset","results":results,
        "truthRule":"Only status=acquired means verified image bytes are in this bundle; image acquisition does not change molecular/lab confirmation ceilings."
    }
    (OUT / "phase2b-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines=[]
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name != "phase2b-checksums.sha256":
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    (OUT / "phase2b-checksums.sha256").write_text("\n".join(lines)+"\n", encoding="utf-8")
    acquired=[r for r in results if r["status"]=="acquired"]
    summary=["# Phase 2B — PMC figure reconciliation","",f"Acquired: **{len(acquired)}/{len(results)}**","" ]
    for r in results:
        summary.append(f"- **{r['sourceFileId']} / {r['figure']}** — `{r['status']}`" + (f" — `{r.get('sha256')}`" if r['status']=="acquired" else f" — {r.get('error')}") )
    summary += ["","HLVd figures remain molecularly bounded: visual similarity alone cannot confirm infection.",""]
    (OUT / "phase2b-summary.md").write_text("\n".join(summary), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0 if acquired else 1

if __name__ == "__main__":
    raise SystemExit(main())
