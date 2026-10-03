#!/usr/bin/env python3
"""Generate a final Grow Doc contribution receipt from the actual Git diff."""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROLLER_PATH = ROOT / "scripts/grow-doc-contribution.py"

def load_controller():
    spec = importlib.util.spec_from_file_location("grow_doc_contribution", CONTROLLER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load contribution controller: {CONTROLLER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

CTRL = load_controller()

def git(root: pathlib.Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()

def resolve_commit(ref: str, root: pathlib.Path = ROOT) -> str:
    value = git(root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{ref}: expected an exact lowercase 40-character Git commit SHA")
    return value

def current_branch(root: pathlib.Path = ROOT) -> str:
    return git(root, "branch", "--show-current")

def changed_paths(base: str, head: str, root: pathlib.Path = ROOT) -> list[str]:
    output = git(root, "diff", "--name-only", "--diff-filter=ACMRTUXB", f"{base}...{head}")
    return [line.strip() for line in output.splitlines() if line.strip()]

def build_receipt(
    *,
    task_id: str,
    base_commit: str,
    head_commit: str,
    branch: str,
    paths: list[str],
    source_ids: list[str],
    completed_validators: list[str],
    contribution_id: str | None = None,
) -> dict:
    tasks = CTRL.task_map()
    task = tasks.get(task_id)
    if task is None:
        raise ValueError(f"unknown task_id: {task_id}")
    lane = task.get("lane")
    task_contract, rule, errors = CTRL.route_contract(lane, task_id)
    if task_contract is None or rule is None:
        raise ValueError("; ".join(errors))
    errors.extend(CTRL.validate_paths(lane, task_contract, rule, paths))
    required = CTRL.stable_union(rule.get("required_validators"), task_contract.get("required_validators"))
    missing = [name for name in required if name not in completed_validators]
    extras = [name for name in completed_validators if name not in required]
    if missing:
        errors.append(f"required validators not completed: {missing}")
    if extras:
        errors.append(f"completed validators not declared required: {extras}")
    if errors:
        raise ValueError("; ".join(errors))

    receipt = {
        "schema_version": CTRL.RECEIPT_SCHEMA,
        "contribution_id": contribution_id or f"{task_id.lower()}-{head_commit[:12]}",
        "task_id": task_id,
        "lane": lane,
        "base_commit": base_commit,
        "head_commit": head_commit,
        "branch": branch,
        "changed_paths": paths,
        "source_ids": list(dict.fromkeys(source_ids)),
        "validation": {"required": required, "completed": completed_validators},
    }
    if rule.get("training_eligible") is False:
        receipt["training_eligible"] = False
        receipt["weight_training_eligible"] = False
    if rule.get("default_training_eligible") is False:
        receipt["training_eligible"] = False
        receipt["weight_training_eligible"] = False
    if lane == "rag":
        receipt["weight_training_eligible"] = False

    receipt_errors = CTRL.validate_receipt_data(receipt)
    if receipt_errors:
        raise ValueError("; ".join(receipt_errors))
    return receipt

def self_test() -> None:
    task, rule, errors = CTRL.route_contract("system", "GD-SYS-001")
    assert not errors
    required = CTRL.stable_union(rule.get("required_validators"), task.get("required_validators"))
    receipt = build_receipt(
        task_id="GD-SYS-001",
        base_commit="a" * 40,
        head_commit="b" * 40,
        branch="work/grow-doc/test/session",
        paths=["scripts/example.py"],
        source_ids=[],
        completed_validators=required,
    )
    assert receipt["head_commit"] == "b" * 40
    assert receipt["changed_paths"] == ["scripts/example.py"]
    try:
        build_receipt(
            task_id="GD-SYS-001",
            base_commit="a" * 40,
            head_commit="b" * 40,
            branch="work/grow-doc/test/session",
            paths=["scripts/example.py"],
            source_ids=[],
            completed_validators=required[:-1],
        )
    except ValueError as exc:
        assert "not completed" in str(exc)
    else:
        raise AssertionError("incomplete validation must not generate a final receipt")

    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture"], cwd=root, check=True)
        (root / "a.txt").write_text("a\n", encoding="utf-8")
        subprocess.run(["git", "add", "a.txt"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
        base = resolve_commit("HEAD", root)
        (root / "scripts").mkdir()
        (root / "scripts" / "x.py").write_text("print('x')\n", encoding="utf-8")
        subprocess.run(["git", "add", "scripts/x.py"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "head"], cwd=root, check=True)
        head = resolve_commit("HEAD", root)
        assert changed_paths(base, head, root) == ["scripts/x.py"]
    print("Grow Doc Git receipt generator self-test: PASS")

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a validated Grow Doc contribution receipt from Git history.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--head-commit", default="HEAD")
    parser.add_argument("--branch")
    parser.add_argument("--contribution-id")
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--completed-validator", action="append", default=[])
    parser.add_argument("--out", type=pathlib.Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    base = resolve_commit(args.base_commit)
    head = resolve_commit(args.head_commit)
    if base == head:
        parser.error("base and head commits must differ")
    branch = args.branch or current_branch()
    if not branch.startswith("work/grow-doc/"):
        parser.error("branch must start with work/grow-doc/; pass --branch when running from detached HEAD")
    paths = changed_paths(base, head)
    if not paths:
        parser.error("Git diff contains no changed paths")

    try:
        receipt = build_receipt(
            task_id=args.task_id,
            base_commit=base,
            head_commit=head,
            branch=branch,
            paths=paths,
            source_ids=args.source_id,
            completed_validators=args.completed_validator,
            contribution_id=args.contribution_id,
        )
    except ValueError as exc:
        parser.error(str(exc))

    raw = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(raw, encoding="utf-8")
    else:
        print(raw, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
