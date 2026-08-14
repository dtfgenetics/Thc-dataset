#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import tarfile
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bulk_acquisition" / "phase2"
WORK = ROOT / "bulk_acquisition" / "work_phase2"
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)
USER_AGENT = "THC-Plant-Diagnostic-Dataset/1.0 (+https://github.com/dtfgenetics/Thc-dataset)"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_bytes(url: str, timeout: int = 180) -> tuple[bytes, str, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.geturl(), resp.headers.get("Content-Type")


def image_kind(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "tif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    return None


def save_image(data: bytes, dest_stem: Path) -> Path:
    kind = image_kind(data)
    if not kind:
        raise RuntimeError(f"Downloaded payload is not a recognized image ({len(data)} bytes)")
    dest = dest_stem.with_suffix("." + kind)
    dest.write_bytes(data)
    return dest


def acquire_direct(target: dict) -> dict:
    errors = []
    best: tuple[bytes, str, str | None] | None = None
    for url in target["urls"]:
        try:
            data, final_url, ctype = fetch_bytes(url)
            if not image_kind(data):
                raise RuntimeError(f"not an image; type={ctype}, bytes={len(data)}")
            if len(data) < 20_000:
                raise RuntimeError(f"image unexpectedly small: {len(data)} bytes")
            if best is None or len(data) > len(best[0]):
                best = (data, final_url, ctype)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    if best is None:
        raise RuntimeError(" | ".join(errors))
    data, final_url, ctype = best
    dest = save_image(data, OUT / target["fileStem"])
    return {
        "datasetId": target["datasetId"],
        "sourceFileId": target["sourceFileId"],
        "figure": target["figure"],
        "status": "acquired",
        "file": dest.name,
        "sizeBytes": dest.stat().st_size,
        "sha256": sha256(dest),
        "finalUrl": final_url,
        "contentType": ctype,
        "license": target["license"],
        "role": target["role"],
        "diagnosticCeiling": target["diagnosticCeiling"],
    }


def europepmc_graphic_href(pmcid: str, figure_number: int) -> str:
    xml_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    data, _, _ = fetch_bytes(xml_url)
    root = ET.fromstring(data)
    xlink = "{http://www.w3.org/1999/xlink}href"
    for fig in root.iter():
        if fig.tag.split("}")[-1] != "fig":
            continue
        label = ""
        for child in fig:
            if child.tag.split("}")[-1] == "label":
                label = "".join(child.itertext()).strip()
                break
        nums = re.findall(r"\d+", label)
        if not nums or int(nums[0]) != figure_number:
            continue
        for node in fig.iter():
            if node.tag.split("}")[-1] == "graphic":
                href = node.attrib.get(xlink) or node.attrib.get("href")
                if href:
                    return href
    raise RuntimeError(f"Could not resolve Figure {figure_number} graphic href from Europe PMC XML for {pmcid}")


def oa_tar_url(pmcid: str) -> str:
    data, _, _ = fetch_bytes(f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}")
    root = ET.fromstring(data)
    for link in root.iter("link"):
        if link.attrib.get("format") == "tgz" and link.attrib.get("href"):
            url = link.attrib["href"]
            if url.startswith("ftp://ftp.ncbi.nlm.nih.gov"):
                url = "https://ftp.ncbi.nlm.nih.gov" + url[len("ftp://ftp.ncbi.nlm.nih.gov"):]
            return url
    raise RuntimeError(f"No OA tgz link found for {pmcid}")


def acquire_pmc(target: dict) -> dict:
    pmcid = target["pmcid"]
    fig_num = target["figureNumber"]
    href = europepmc_graphic_href(pmcid, fig_num)
    base = os.path.basename(href)
    candidates = []
    if href.startswith("http"):
        candidates.append(href)
    quoted = urllib.parse.quote(base)
    candidates += [
        f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/bin/{quoted}",
        f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/bin/{quoted}",
    ]
    errors = []
    for url in candidates:
        try:
            data, final_url, ctype = fetch_bytes(url)
            if image_kind(data) and len(data) > 20_000:
                dest = save_image(data, OUT / target["fileStem"])
                return {
                    "datasetId": target["datasetId"], "sourceFileId": target["sourceFileId"],
                    "figure": target["figure"], "status": "acquired", "file": dest.name,
                    "sizeBytes": dest.stat().st_size, "sha256": sha256(dest), "finalUrl": final_url,
                    "contentType": ctype, "pmcGraphicHref": href, "license": target["license"],
                    "role": target["role"], "diagnosticCeiling": target["diagnosticCeiling"],
                }
            raise RuntimeError(f"not usable image; type={ctype}, bytes={len(data)}")
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    # Fallback: download the official PMC OA package and extract the exact graphic.
    try:
        tgz_url = oa_tar_url(pmcid)
        tgz = WORK / f"{pmcid}.tar.gz"
        if not tgz.exists():
            data, _, _ = fetch_bytes(tgz_url, timeout=300)
            tgz.write_bytes(data)
        with tarfile.open(tgz, "r:gz") as tf:
            matches = [m for m in tf.getmembers() if m.isfile() and os.path.basename(m.name) == base]
            if not matches:
                stem = os.path.splitext(base)[0]
                matches = [m for m in tf.getmembers() if m.isfile() and stem in os.path.basename(m.name)]
            if not matches:
                raise RuntimeError(f"Graphic {base} not found in OA package")
            member = max(matches, key=lambda m: m.size)
            f = tf.extractfile(member)
            if f is None:
                raise RuntimeError("Could not extract figure member")
            data = f.read()
        dest = save_image(data, OUT / target["fileStem"])
        return {
            "datasetId": target["datasetId"], "sourceFileId": target["sourceFileId"],
            "figure": target["figure"], "status": "acquired", "file": dest.name,
            "sizeBytes": dest.stat().st_size, "sha256": sha256(dest), "finalUrl": tgz_url,
            "contentType": "PMC OA package extraction", "pmcGraphicHref": href,
            "license": target["license"], "role": target["role"],
            "diagnosticCeiling": target["diagnosticCeiling"],
        }
    except Exception as exc:
        errors.append(f"OA package fallback: {exc}")
        raise RuntimeError(" | ".join(errors))


def mdpi_ds117() -> dict:
    target = {
        "datasetId":"DS-117", "sourceFileId":"SF-024", "figure":"Figure 1",
        "fileStem":"DS117_Figure1_leaf_morphogenesis",
        "license":"CC BY 4.0", "role":"healthy/developmental hard-negative reference",
        "diagnosticCeiling":"Normal developmental morphology for White Widow under the study conditions; not a universal cultivar-stage template.",
        "urls":[
            "https://mdpi-res.com/d_attachment/plants/plants-12-03646/article_deploy/html/images/plants-12-03646-g001.png",
            "https://mdpi-res.com/d_attachment/plants/plants-12-03646/article_deploy/plants-12-03646-g001.png",
            "https://www.mdpi.com/plants/plants-12-03646/article_deploy/html/images/plants-12-03646-g001.png",
            "https://www.mdpi.com/2223-7747/12/20/3646/xml-images/plants-12-03646-g001.png",
        ],
    }
    return acquire_direct(target)


DIRECT_TARGETS = [
    # Sex / intersex / male morphology — Frontiers CC BY.
    {"datasetId":"DS-074","sourceFileId":"SF-025","figure":"Figure 1","fileStem":"DS074_Figure1_female_inflorescence_development","urls":["https://www.frontiersin.org/files/Articles/533993/xml-images/fpls-11-00718-g001.webp"],"license":"CC BY 4.0","role":"female inflorescence morphology reference","diagnosticCeiling":"Stage/morphology reference; not a strict preflower-only classifier target."},
    {"datasetId":"DS-074","sourceFileId":"SF-026","figure":"Figure 2","fileStem":"DS074_Figure2_intersex_anthers","urls":["https://www.frontiersin.org/files/Articles/533993/xml-images/fpls-11-00718-g002.webp"],"license":"CC BY 4.0","role":"intersex anther morphology reference","diagnosticCeiling":"High-confidence intersex only when anthers are visibly present; timing/quality abstention still required."},
    {"datasetId":"DS-074","sourceFileId":"SF-027","figure":"Figure 6","fileStem":"DS074_Figure6_male_flower_development","urls":["https://www.frontiersin.org/files/Articles/533993/xml-images/fpls-11-00718-g006.webp"],"license":"CC BY 4.0","role":"male flower/anther morphology reference","diagnosticCeiling":"Male reproductive morphology reference; not evidence that an immature vegetative plant is male."},

    # Cannabis pathogens — only figures without known third-party reproduced panels.
    {"datasetId":"DS-097","sourceFileId":"SF-028","figure":"Figure 4","fileStem":"DS097_Figure4_botrytis_bud_rot","urls":["https://www.frontiersin.org/files/Articles/439316/xml-images/fpls-10-01120-g004.webp"],"license":"CC BY 4.0 article figure; no separate third-party credit identified for Figure 4","role":"Botrytis bud-rot progression reference","diagnosticCeiling":"Visual bud rot supports a differential; species confirmation remains tied to source culture/molecular evidence and user cases may require lab confirmation."},
    {"datasetId":"DS-097","sourceFileId":"SF-029","figure":"Figure 7","fileStem":"DS097_Figure7_powdery_mildew","urls":["https://www.frontiersin.org/files/Articles/439316/xml-images/fpls-10-01120-g007.webp"],"license":"CC BY 4.0","role":"Cannabis powdery-mildew progression reference","diagnosticCeiling":"Syndrome-level visual reference; taxon/species certainty must follow the source molecular limits."},

    # Polyploid/genetic normal-variation hard negatives — exact direct assets already pinned.
    {"datasetId":"DS-135","sourceFileId":"SF-DS135-F02","figure":"Figure 2","fileStem":"DS135_Figure2_ploidy_confirmation","urls":["https://www.frontiersin.org/files/Articles/449166/xml-images/fpls-10-00476-g002.webp"],"license":"CC BY 4.0","role":"ploidy confirmation evidence anchor","diagnosticCeiling":"Evidence anchor, not an image-only user diagnosis."},
    {"datasetId":"DS-135","sourceFileId":"SF-DS135-F03","figure":"Figure 3","fileStem":"DS135_Figure3_leaf_stomata_morphology","urls":["https://www.frontiersin.org/files/Articles/449166/xml-images/fpls-10-00476-g003.webp"],"license":"CC BY 4.0","role":"diploid/tetraploid morphology hard negative","diagnosticCeiling":"Genetic/ploidy-grounded normal variation; do not infer polyploidy from leaf shape alone."},
    {"datasetId":"DS-135","sourceFileId":"SF-DS135-F05","figure":"Figure 5","fileStem":"DS135_Figure5_trichome_density_morphology","urls":["https://www.frontiersin.org/files/Articles/449166/xml-images/fpls-10-00476-g005.webp"],"license":"CC BY 4.0","role":"trichome-density genetic morphology reference","diagnosticCeiling":"Morphology reference only; not a universal maturity or harvest rule."},
    {"datasetId":"DS-135","sourceFileId":"SF-DS135-F06","figure":"Figure 6","fileStem":"DS135_Figure6_inflorescence_architecture","urls":["https://www.frontiersin.org/files/Articles/449166/xml-images/fpls-10-00476-g006.webp"],"license":"CC BY 4.0","role":"inflorescence-architecture genetic hard negative","diagnosticCeiling":"Genetic/ploidy variation reference; not disease evidence by itself."},
]

PMC_TARGETS = [
    {"datasetId":"DS-112","sourceFileId":"SF-031","pmcid":"PMC10071647","figureNumber":13,"figure":"Figure 13","fileStem":"DS112_Figure13_trichome_maturation","license":"CC BY 4.0","role":"trichome maturation reference","diagnosticCeiling":"Clear/translucent/red-brown appearance is genotype/age/context dependent; not a universal harvest-certainty rule."},
    {"datasetId":"DS-120","sourceFileId":"SF-041","pmcid":"PMC10878361","figureNumber":1,"figure":"Figure 1","fileStem":"DS120_Figure1_TSSM_injury_webbing","license":"CC BY 4.0","role":"twospotted-spider-mite feeding injury/webbing reference","diagnosticCeiling":"Cannabis/hemp feeding-injury reference; organism confirmation should use magnification and direct pest evidence when available."},
    {"datasetId":"DS-073","sourceFileId":"SF-043","pmcid":"PMC11902214","figureNumber":3,"figure":"Figure 3","fileStem":"DS073_Figure3_HLVd_cutting_differential","license":"CC BY 4.0","role":"molecularly characterized HLVd cutting/root differential reference","diagnosticCeiling":"HLVd remains suspected from appearance alone; molecular testing is required for confirmation."},
    {"datasetId":"DS-102","sourceFileId":"SF-044","pmcid":"PMC10779078","figureNumber":7,"figure":"Figure 7","fileStem":"DS102_Figure7_HLVd_inflorescence_differential","license":"CC BY 4.0","role":"HTS-confirmed HLVd inflorescence differential reference","diagnosticCeiling":"Genotype-specific expression; photo alone cannot confirm HLVd and asymptomatic infection is possible."},
]


def main() -> int:
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.rmtree(WORK, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    results = []
    targets = [("direct", t) for t in DIRECT_TARGETS] + [("pmc", t) for t in PMC_TARGETS]
    # DS-117 MDPI target is attempted separately because MDPI rate-limits some clients.
    try:
        results.append(mdpi_ds117())
    except Exception as exc:
        results.append({"datasetId":"DS-117","sourceFileId":"SF-024","figure":"Figure 1","status":"blocked","error":str(exc)})

    for kind, target in targets:
        try:
            result = acquire_direct(target) if kind == "direct" else acquire_pmc(target)
            results.append(result)
        except Exception as exc:
            results.append({
                "datasetId": target["datasetId"], "sourceFileId": target["sourceFileId"],
                "figure": target["figure"], "status": "blocked", "error": str(exc),
            })

    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schemaVersion":"1.0",
        "phase":"bulk-acquisition-phase2-reference-figures",
        "createdAt":now,
        "repository":"dtfgenetics/Thc-dataset",
        "rightsExclusions":[{
            "datasetId":"DS-097","sourceFileId":"SF-030","figure":"Figure 2",
            "status":"not-acquired-publicly",
            "reason":"Composite includes panels explicitly reproduced from Canadian Journal of Plant Pathology by permission; article-level CC BY is not treated as automatic redistribution authority for those panels."
        }],
        "results":results,
        "truthRule":"Only status=acquired means verified image bytes are included. Figure acquisition never raises the scientific diagnostic ceiling recorded for the source.",
    }
    (OUT / "phase2-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    checks = []
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name != "phase2-checksums.sha256":
            checks.append(f"{sha256(p)}  {p.name}")
    (OUT / "phase2-checksums.sha256").write_text("\n".join(checks) + "\n", encoding="utf-8")

    acquired = [r for r in results if r.get("status") == "acquired"]
    blocked = [r for r in results if r.get("status") != "acquired"]
    lines = ["# THC Plant Diagnostic — Bulk Acquisition Phase 2", "", f"Generated: {now}", "", f"Acquired: **{len(acquired)}/{len(results)}** figure targets", ""]
    for r in results:
        extra = f" — {r.get('error')}" if r.get("status") != "acquired" else f" — {r.get('file')} — SHA256 `{r.get('sha256')}`"
        lines.append(f"- **{r['sourceFileId']} / {r['figure']}** — `{r['status']}`{extra}")
    lines += ["", "## Rights/safety", "", "- DS-097 Figure 2 is excluded from the public bundle because of explicitly permission-reproduced panels.", "- HLVd images remain molecular-reference differentials; photo-only diagnosis cannot confirm HLVd.", "- Trichome/color and polyploid morphology images do not establish universal maturity or genetic diagnoses.", "- All acquired figures retain source-file identity so related panels can be grouped before any training/evaluation split.", ""]
    (OUT / "phase2-summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    print(f"Acquired {len(acquired)}/{len(results)} Phase-2 figures")
    return 0 if acquired else 1


if __name__ == "__main__":
    raise SystemExit(main())
