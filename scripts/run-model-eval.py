#!/usr/bin/env python3
"""Prepare reproducible held-out model evaluation artifacts.

CI uses --self-test with a deterministic mock backend. Real evaluation requires
--backend transformers with pinned revisions and local model access.

Optional retrieval is accepted only through a prebuilt frozen snapshot whose
hash and benchmark binding are verified before prompts are constructed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUPPORTED_DTYPES = ("float32", "float16", "bfloat16")
CHAT_TEMPLATE_METHOD = "apply_chat_template:add_generation_prompt"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{n}: expected object")
        rows.append(row)
    return rows


def validate_cases(rows: list[dict[str, Any]]) -> None:
    required = {"id", "category", "prompt", "expected_points", "must_cite", "forbidden_claims"}
    seen: set[str] = set()
    for n, row in enumerate(rows, 1):
        missing = required - row.keys()
        if missing:
            raise ValueError(f"row {n}: missing {sorted(missing)}")
        if row["id"] in seen:
            raise ValueError(f"row {n}: duplicate id {row['id']}")
        seen.add(row["id"])


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def mock_response(case: dict[str, Any]) -> str:
    return "MOCK ONLY — NOT MODEL PERFORMANCE. " + " ".join(case["expected_points"] + case["must_cite"])


def dtype_attribute(name: str) -> str:
    if name not in SUPPORTED_DTYPES:
        raise ValueError(
            f"unsupported evaluation dtype {name!r}; use one of {', '.join(SUPPORTED_DTYPES)}. "
            "Quantized evaluation requires a separately pinned quantization contract."
        )
    return name


def verify_chat_template(template: Any, expected_sha256: str) -> str:
    if not isinstance(template, str) or not template.strip():
        raise ValueError("tokenizer chat_template must be a non-empty string")
    expected = expected_sha256.lower()
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError("tokenizer chat-template SHA-256 must be 64 hexadecimal characters")
    actual = text_sha256(template)
    if actual != expected:
        raise ValueError(f"tokenizer chat-template SHA-256 mismatch: expected {expected}, got {actual}")
    return actual


def render_chat_prompt(tokenizer: Any, prompt: str) -> str:
    rendered = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=False,
        add_generation_prompt=True,
    )
    if not isinstance(rendered, str) or not rendered:
        raise ValueError("tokenizer.apply_chat_template returned an empty/non-string prompt")
    return rendered


def load_retrieval(snapshot_path: Path, manifest_path: Path, benchmark_path: Path, cases: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "grow-doc-rag-snapshot-v1":
        raise ValueError("unsupported retrieval snapshot manifest schema")
    if manifest.get("snapshot_sha256") != sha256(snapshot_path):
        raise ValueError("retrieval snapshot SHA-256 does not match manifest")
    if manifest.get("benchmark_sha256") != sha256(benchmark_path):
        raise ValueError("retrieval snapshot was built against a different benchmark")
    top_k = manifest.get("top_k")
    if not isinstance(top_k, int) or top_k < 1:
        raise ValueError("retrieval manifest top_k must be a positive integer")

    rows = load_jsonl(snapshot_path)
    expected = {c["id"]: c for c in cases}
    by_case: dict[str, dict[str, Any]] = {}
    for n, row in enumerate(rows, 1):
        case_id = row.get("case_id")
        if case_id not in expected:
            raise ValueError(f"retrieval row {n}: unknown case_id {case_id!r}")
        if case_id in by_case:
            raise ValueError(f"retrieval row {n}: duplicate case_id {case_id}")
        if row.get("prompt_sha256") != text_sha256(expected[case_id]["prompt"]):
            raise ValueError(f"retrieval row {n}: prompt hash mismatch for {case_id}")
        retrieved = row.get("retrieved")
        if not isinstance(retrieved, list):
            raise ValueError(f"retrieval row {n}: retrieved must be a list")
        if len(retrieved) > top_k:
            raise ValueError(f"retrieval row {n}: exceeds manifest top_k")
        seen_claims: set[str] = set()
        for item in retrieved:
            required = {"rank", "score", "claim_id", "claim_sha256", "claim", "source_ids", "profile_ids"}
            missing = required - item.keys()
            if missing:
                raise ValueError(f"retrieval row {n}: item missing {sorted(missing)}")
            if item["claim_id"] in seen_claims:
                raise ValueError(f"retrieval row {n}: duplicate claim {item['claim_id']}")
            seen_claims.add(item["claim_id"])
            if text_sha256(item["claim"]) != item["claim_sha256"]:
                raise ValueError(f"retrieval row {n}: claim hash mismatch for {item['claim_id']}")
            if not item["source_ids"] or not item["profile_ids"]:
                raise ValueError(f"retrieval row {n}: provenance missing for {item['claim_id']}")
        by_case[case_id] = row

    missing_cases = sorted(set(expected) - set(by_case))
    if missing_cases:
        raise ValueError(f"retrieval snapshot missing benchmark cases: {missing_cases}")
    return by_case, manifest


def retrieval_context(row: dict[str, Any] | None) -> str:
    if row is None:
        return ""
    items = row["retrieved"]
    if not items:
        return "\n\nRETRIEVED EVIDENCE\nNo approved evidence was retrieved. Do not invent citations or claims."
    lines = [
        "\n\nRETRIEVED EVIDENCE",
        "Use only these retrieved claims as factual grounding; preserve uncertainty and cite source IDs exactly.",
    ]
    for item in items:
        lines.append(f"[{item['rank']}] {item['claim']} Sources: {', '.join(item['source_ids'])}")
    return "\n".join(lines)


def transformers_generate(args: argparse.Namespace, prompts: list[str]) -> tuple[list[str], list[str], str]:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("transformers backend requires torch and transformers") from exc

    torch_dtype = getattr(torch, dtype_attribute(args.dtype))
    tok = AutoTokenizer.from_pretrained(args.tokenizer_repo, revision=args.tokenizer_revision)
    template_hash = verify_chat_template(tok.chat_template, args.tokenizer_chat_template_sha256)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_repo,
        revision=args.model_revision,
        torch_dtype=torch_dtype,
        device_map="auto",
    )
    if args.adapter_repo:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter_repo, revision=args.adapter_revision)
    model.eval()

    answers: list[str] = []
    rendered_hashes: list[str] = []
    for prompt in prompts:
        if args.seed is not None:
            torch.manual_seed(args.seed)
        rendered = render_chat_prompt(tok, prompt)
        rendered_hashes.append(text_sha256(rendered))
        inputs = tok(rendered, add_special_tokens=False, return_tensors="pt")
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        kwargs: dict[str, Any] = {"max_new_tokens": args.max_new_tokens, "do_sample": args.do_sample}
        if args.do_sample:
            kwargs.update(temperature=args.temperature, top_p=args.top_p)
        with torch.inference_mode():
            generated = model.generate(**inputs, **kwargs)
        answers.append(tok.decode(generated[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True).strip())
    return answers, rendered_hashes, template_hash


def runtime() -> dict[str, Any]:
    from importlib.metadata import PackageNotFoundError, version

    def v(name: str) -> str:
        try:
            return version(name)
        except PackageNotFoundError:
            return "not-installed"

    device = "cpu"
    gpu_name = None
    gpu_memory_bytes = None
    try:
        import torch
        if torch.cuda.is_available():
            device = "cuda"
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory_bytes = int(torch.cuda.get_device_properties(0).total_memory)
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
    except ImportError:
        device = "unknown"
    return {
        "python": platform.python_version(), "transformers": v("transformers"), "torch": v("torch"),
        "accelerate": v("accelerate"), "peft": None if v("peft") == "not-installed" else v("peft"),
        "bitsandbytes": None if v("bitsandbytes") == "not-installed" else v("bitsandbytes"),
        "device": device, "gpu_name": gpu_name, "gpu_memory_bytes": gpu_memory_bytes,
    }


def execute(args: argparse.Namespace, mock: bool = False) -> tuple[Path, Path]:
    bench = Path(args.benchmark)
    cases = load_jsonl(bench)
    validate_cases(cases)

    retrieval_rows: dict[str, dict[str, Any]] = {}
    retrieval_manifest: dict[str, Any] | None = None
    if args.retrieval_snapshot or args.retrieval_manifest:
        if not args.retrieval_snapshot or not args.retrieval_manifest:
            raise ValueError("retrieval snapshot and manifest must be provided together")
        retrieval_rows, retrieval_manifest = load_retrieval(Path(args.retrieval_snapshot), Path(args.retrieval_manifest), bench, cases)

    prompts = []
    for case in cases:
        base = "Answer cautiously from evidence; preserve limitations and exact citations when known.\n\n" + case["prompt"]
        prompts.append(base + retrieval_context(retrieval_rows.get(case["id"])))

    if mock:
        answers = [mock_response(c) for c in cases]
        rendered_hashes = [text_sha256(p) for p in prompts]
        template_hash = text_sha256("MOCK ONLY — no tokenizer loaded")
    else:
        answers, rendered_hashes, template_hash = transformers_generate(args, prompts)

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    responses = outdir / "responses.jsonl"
    response_rows: list[dict[str, Any]] = []
    for case, prompt, rendered_hash, answer in zip(cases, prompts, rendered_hashes, answers):
        retrieved = retrieval_rows.get(case["id"], {}).get("retrieved", [])
        response_rows.append({
            "id": case["id"], "category": case["category"],
            "prompt_sha256": text_sha256(prompt),
            "rendered_prompt_sha256": rendered_hash,
            "response": answer,
            "retrieval": None if retrieval_manifest is None else {
                "claim_ids": [item["claim_id"] for item in retrieved],
                "source_ids": sorted({sid for item in retrieved for sid in item["source_ids"]}),
                "profile_ids": sorted({pid for item in retrieved for pid in item["profile_ids"]}),
                "context_sha256": text_sha256(retrieval_context(retrieval_rows[case["id"]])),
            },
        })
    write_jsonl(responses, response_rows)

    scores = outdir / "scores.json"
    scores.write_text(json.dumps({"status": "mock-only" if mock else "pending-review", "promotion_eligible": False}, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "grow-doc-eval-run-v1",
        "run_id": args.run_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model": {
            "repository": args.model_repo, "revision": args.model_revision, "dtype": args.dtype,
            "adapter": None if not args.adapter_repo else {"repository": args.adapter_repo, "revision": args.adapter_revision},
        },
        "tokenizer": {
            "repository": args.tokenizer_repo,
            "revision": args.tokenizer_revision,
            "chat_template_sha256": template_hash,
            "chat_template_method": CHAT_TEMPLATE_METHOD,
        },
        "decoding": {
            "temperature": args.temperature, "top_p": args.top_p, "max_new_tokens": args.max_new_tokens,
            "do_sample": args.do_sample, "seed": args.seed,
        },
        "retrieval": None if retrieval_manifest is None else {
            "snapshot_sha256": retrieval_manifest["snapshot_sha256"], "top_k": retrieval_manifest["top_k"], "reranker": None,
        },
        "evaluation": {"benchmark_path": str(bench), "benchmark_sha256": sha256(bench), "scorer_revision": args.scorer_revision},
        "runtime": runtime(),
        "artifacts": {
            "responses_path": str(responses), "responses_sha256": sha256(responses),
            "scores_path": str(scores), "review_path": None,
        },
    }
    mpath = outdir / "run-manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return responses, mpath


def self_test() -> None:
    for dtype in SUPPORTED_DTYPES:
        assert dtype_attribute(dtype) == dtype
    try:
        dtype_attribute("nf4")
    except ValueError:
        pass
    else:
        raise AssertionError("quantized dtype must be rejected until its config is pinned")

    template = "{% for message in messages %}{{ message['role'] }}: {{ message['content'] }}{% endfor %} assistant:"
    digest = text_sha256(template)
    assert verify_chat_template(template, digest.upper()) == digest
    try:
        verify_chat_template(template, "0" * 64)
    except ValueError as exc:
        assert "mismatch" in str(exc)
    else:
        raise AssertionError("template mismatch must be rejected")

    class DummyTokenizer:
        chat_template = template
        def apply_chat_template(self, messages: list[dict[str, str]], tokenize: bool, add_generation_prompt: bool) -> str:
            assert tokenize is False
            assert add_generation_prompt is True
            return f"user: {messages[0]['content']} assistant:"

    rendered = render_chat_prompt(DummyTokenizer(), "Test")
    assert rendered == "user: Test assistant:"

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        bench = root / "heldout.jsonl"
        snapshot = root / "snapshot.jsonl"
        snapshot_manifest = root / "snapshot.manifest.json"
        write_jsonl(bench, [{"id": "case-001", "category": "factuality", "prompt": "What is supported?", "expected_points": ["A cautious point."], "must_cite": ["doi:10.0000/test"], "forbidden_claims": ["An overclaim."]}])
        claim = "A cautious point is supported by the reviewed evidence."
        write_jsonl(snapshot, [{"case_id": "case-001", "prompt_sha256": text_sha256("What is supported?"), "retrieved": [{"rank": 1, "score": 2.0, "claim_id": "rag-001", "claim_sha256": text_sha256(claim), "claim": claim, "source_ids": ["doi:10.0000/test"], "profile_ids": ["profile-001"]}]}])
        snapshot_manifest.write_text(json.dumps({"schema_version": "grow-doc-rag-snapshot-v1", "algorithm": "grow-doc-lexical-idf-v1", "top_k": 5, "benchmark_sha256": sha256(bench), "snapshot_sha256": sha256(snapshot)}), encoding="utf-8")
        a = argparse.Namespace(
            benchmark=str(bench), output_dir=str(root / "out"), run_id="self-test-0001",
            model_repo="Qwen/Qwen3-8B", model_revision="1234567", tokenizer_repo="Qwen/Qwen3-8B", tokenizer_revision="1234567",
            tokenizer_chat_template_sha256=digest, adapter_repo=None, adapter_revision=None, dtype="bfloat16", temperature=0.0,
            top_p=1.0, max_new_tokens=64, do_sample=False, seed=42, scorer_revision="1234567",
            retrieval_snapshot=str(snapshot), retrieval_manifest=str(snapshot_manifest),
        )
        responses, manifest = execute(a, mock=True)
        response = load_jsonl(responses)[0]
        assert response["response"].startswith("MOCK ONLY")
        assert response["rendered_prompt_sha256"]
        assert response["retrieval"]["claim_ids"] == ["rag-001"]
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        assert manifest_data["tokenizer"]["chat_template_method"] == CHAT_TEMPLATE_METHOD
        assert len(manifest_data["tokenizer"]["chat_template_sha256"]) == 64
        assert manifest_data["retrieval"]["snapshot_sha256"] == sha256(snapshot)
        assert manifest_data["artifacts"]["responses_sha256"] == sha256(responses)
        assert json.loads((root / "out" / "scores.json").read_text(encoding="utf-8"))["promotion_eligible"] is False

        snapshot_manifest.write_text(json.dumps({"schema_version": "grow-doc-rag-snapshot-v1", "top_k": 5, "benchmark_sha256": "0" * 64, "snapshot_sha256": sha256(snapshot)}), encoding="utf-8")
        try:
            execute(a, mock=True)
        except ValueError as exc:
            assert "different benchmark" in str(exc)
        else:
            raise AssertionError("benchmark-mismatched retrieval snapshot must be rejected")
    print("model evaluation runner self-test: PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--backend", choices=("transformers",), default="transformers")
    p.add_argument("--benchmark", default="model_tuning/eval/heldout_v2.jsonl")
    p.add_argument("--model-repo", default="Qwen/Qwen3-8B")
    p.add_argument("--model-revision", default="UNPINNED")
    p.add_argument("--tokenizer-repo", default="Qwen/Qwen3-8B")
    p.add_argument("--tokenizer-revision", default="UNPINNED")
    p.add_argument("--tokenizer-chat-template-sha256", default="UNPINNED")
    p.add_argument("--adapter-repo")
    p.add_argument("--adapter-revision")
    p.add_argument("--retrieval-snapshot")
    p.add_argument("--retrieval-manifest")
    p.add_argument("--dtype", choices=SUPPORTED_DTYPES, default="bfloat16")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--top-p", type=float, default=1.0)
    p.add_argument("--max-new-tokens", type=int, default=512)
    p.add_argument("--do-sample", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output-dir", default="model_tuning/runs/latest")
    p.add_argument("--run-id", default="grow-doc-eval")
    p.add_argument("--scorer-revision", default="UNPINNED")
    args = p.parse_args()
    if args.self_test:
        self_test()
        return 0
    for label, value in [("model", args.model_revision), ("tokenizer", args.tokenizer_revision), ("scorer", args.scorer_revision)]:
        if value == "UNPINNED" or len(value) < 7:
            raise SystemExit(f"{label} revision must be pinned")
    expected = args.tokenizer_chat_template_sha256.lower()
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise SystemExit("tokenizer chat-template SHA-256 must be pinned as 64 hexadecimal characters")
    if bool(args.adapter_repo) != bool(args.adapter_revision):
        raise SystemExit("adapter repo and revision must be provided together")
    if bool(args.retrieval_snapshot) != bool(args.retrieval_manifest):
        raise SystemExit("retrieval snapshot and manifest must be provided together")
    responses, manifest = execute(args)
    print(f"responses: {responses}\nmanifest: {manifest}\nRaw artifacts only; no promotion claim is made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
