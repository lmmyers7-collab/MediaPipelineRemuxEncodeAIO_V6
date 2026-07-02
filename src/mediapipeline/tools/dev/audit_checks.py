"""Shared audit/check definitions for local hooks, CI, and release gates."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))


@dataclass(frozen=True)
class AuditCheck:
    id: str
    label: str
    module: str
    arguments: tuple[str, ...] = ()
    source_tree_only: bool = False
    rationale: str = ""


@dataclass(frozen=True)
class AuditCheckResult:
    check: AuditCheck
    ok: bool
    returncode: int
    output: str


def _check(
    check_id: str,
    label: str,
    module: str,
    *arguments: str,
    source_tree_only: bool = False,
    rationale: str = "",
) -> AuditCheck:
    return AuditCheck(
        id=check_id,
        label=label,
        module=module,
        arguments=tuple(arguments),
        source_tree_only=source_tree_only,
        rationale=rationale,
    )


CHECKS: dict[str, AuditCheck] = {
    "summary-freshness": _check(
        "summary-freshness",
        "summary freshness",
        "mediapipeline.tools.dev.refresh_summaries",
        "--check",
        source_tree_only=True,
    ),
    "project-index": _check(
        "project-index",
        "project index freshness",
        "mediapipeline.tools.dev.generate_project_index",
        "--check",
        source_tree_only=True,
    ),
    "feature-file-map": _check(
        "feature-file-map",
        "feature file map freshness",
        "mediapipeline.tools.dev.generate_feature_file_map",
        "--check",
        source_tree_only=True,
    ),
    "pipeline-map": _check(
        "pipeline-map",
        "pipeline map freshness",
        "mediapipeline.tools.dev.generate_pipeline_map",
        "--check",
        source_tree_only=True,
    ),
    "lifecycle-map": _check(
        "lifecycle-map",
        "lifecycle map freshness",
        "mediapipeline.tools.dev.generate_lifecycle_map",
        "--check",
        source_tree_only=True,
    ),
    "smoke-wrapper-map": _check(
        "smoke-wrapper-map",
        "smoke wrapper map freshness",
        "mediapipeline.tools.dev.generate_smoke_wrapper_map",
        "--check",
        source_tree_only=True,
    ),
    "duplicate-test-name-report": _check(
        "duplicate-test-name-report",
        "duplicate test-name report freshness",
        "mediapipeline.tools.dev.generate_duplicate_test_name_report",
        "--check",
        source_tree_only=True,
    ),
    "config-schema": _check(
        "config-schema",
        "config schema freshness",
        "mediapipeline.tools.dev.generate_config_schema",
        "--check",
    ),
    "stage-schema": _check(
        "stage-schema",
        "stage schema freshness",
        "mediapipeline.tools.dev.generate_stage_schema",
        "--check",
    ),
    "risky-file-registry": _check(
        "risky-file-registry",
        "risky file registry",
        "mediapipeline.tools.dev.check_risky_file_registry",
    ),
    "architecture-guardrails": _check(
        "architecture-guardrails",
        "architecture guardrails",
        "mediapipeline.tools.dev.check_architecture_guardrails",
    ),
    "architecture-guardrails-staged": _check(
        "architecture-guardrails-staged",
        "architecture guardrails",
        "mediapipeline.tools.dev.check_architecture_guardrails",
        "--staged",
    ),
    "active-doc-references": _check(
        "active-doc-references",
        "active doc references",
        "mediapipeline.tools.dev.check_active_doc_references",
        source_tree_only=True,
    ),
    "dependency-boundaries": _check(
        "dependency-boundaries",
        "dependency boundaries",
        "mediapipeline.tools.dev.check_dependency_boundaries",
    ),
    "dependency-boundaries-max-internal-1": _check(
        "dependency-boundaries-max-internal-1",
        "dependency boundaries",
        "mediapipeline.tools.dev.check_dependency_boundaries",
        "--max-internal-imports",
        "1",
    ),
    "naming-lint": _check(
        "naming-lint",
        "naming lint",
        "mediapipeline.tools.lint_naming",
    ),
    "naming-lint-staged": _check(
        "naming-lint-staged",
        "naming lint",
        "mediapipeline.tools.lint_naming",
        "--staged",
    ),
    "change-packets": _check(
        "change-packets",
        "change packets",
        "mediapipeline.tools.change_control.validate_changes",
    ),
    "change-packet-staged-coverage": _check(
        "change-packet-staged-coverage",
        "change packet staged coverage",
        "mediapipeline.tools.change_control.validate_changes",
        "--require-staged-coverage",
    ),
    "python-typing": _check(
        "python-typing",
        "Python typing",
        "mediapipeline.tools.dev.check_python_typing",
    ),
    "python-lint": _check(
        "python-lint",
        "Python lint",
        "mediapipeline.tools.dev.check_python_lint",
        source_tree_only=True,
        rationale="Runs Ruff check only; no formatting or fixes.",
    ),
    "legacy-removal-readiness": _check(
        "legacy-removal-readiness",
        "legacy removal readiness",
        "mediapipeline.tools.dev.check_legacy_removal_readiness",
    ),
    "god-file-guard": _check(
        "god-file-guard",
        "god-file guard",
        "mediapipeline.tools.dev.check_godfiles",
    ),
    "marketecture-guard": _check(
        "marketecture-guard",
        "marketecture guard",
        "mediapipeline.tools.dev.check_marketecture",
    ),
}


SUITES: dict[str, tuple[str, ...]] = {
    "precommit": (
        "summary-freshness",
        "project-index",
        "pipeline-map",
        "lifecycle-map",
        "config-schema",
        "stage-schema",
        "risky-file-registry",
        "architecture-guardrails-staged",
        "dependency-boundaries-max-internal-1",
        "naming-lint-staged",
        "active-doc-references",
        "change-packet-staged-coverage",
        "python-typing",
    ),
    "phase1-generated": (
        "summary-freshness",
        "project-index",
        "pipeline-map",
        "lifecycle-map",
        "config-schema",
        "stage-schema",
        "risky-file-registry",
        "architecture-guardrails",
        "active-doc-references",
        "python-typing",
        "python-lint",
    ),
    "deep-audit": (
        "summary-freshness",
        "project-index",
        "feature-file-map",
        "pipeline-map",
        "lifecycle-map",
        "config-schema",
        "stage-schema",
        "risky-file-registry",
        "architecture-guardrails",
        "active-doc-references",
        "change-packets",
        "python-typing",
        "python-lint",
        "dependency-boundaries",
        "naming-lint",
        "god-file-guard",
        "marketecture-guard",
    ),
    "release-self-test": (
        "summary-freshness",
        "project-index",
        "feature-file-map",
        "pipeline-map",
        "lifecycle-map",
        "smoke-wrapper-map",
        "duplicate-test-name-report",
        "config-schema",
        "active-doc-references",
        "dependency-boundaries-max-internal-1",
        "python-lint",
        "legacy-removal-readiness",
    ),
    "ai-guardrail": (
        "summary-freshness",
        "project-index",
        "pipeline-map",
        "feature-file-map",
        "lifecycle-map",
        "config-schema",
        "stage-schema",
        "active-doc-references",
        "dependency-boundaries",
        "architecture-guardrails",
        "naming-lint",
        "god-file-guard",
        "marketecture-guard",
        "risky-file-registry",
    ),
}


def suite_names() -> tuple[str, ...]:
    return tuple(sorted(SUITES))


def suite_checks(suite: str) -> tuple[AuditCheck, ...]:
    try:
        check_ids = SUITES[suite]
    except KeyError as exc:
        raise ValueError(f"Unknown audit check suite: {suite}") from exc
    return tuple(CHECKS[check_id] for check_id in check_ids)


def command_for_check(check: AuditCheck, *, python_executable: str | None = None) -> tuple[str, ...]:
    executable = python_executable or sys.executable
    return (executable, "-m", check.module, *check.arguments)


def subprocess_environment() -> dict[str, str]:
    env = os.environ.copy()
    src_root = str(REPO_ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_root if not existing else src_root + os.pathsep + existing
    return env


def run_check(check: AuditCheck, *, python_executable: str | None = None) -> AuditCheckResult:
    command = command_for_check(check, python_executable=python_executable)
    try:
        result = subprocess.run(
            list(command),
            cwd=REPO_ROOT,
            env=subprocess_environment(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        return AuditCheckResult(check=check, ok=False, returncode=127, output=str(exc))
    return AuditCheckResult(
        check=check,
        ok=result.returncode == 0,
        returncode=result.returncode,
        output=result.stdout.strip(),
    )


def run_suite(suite: str, *, python_executable: str | None = None) -> tuple[AuditCheckResult, ...]:
    return tuple(run_check(check, python_executable=python_executable) for check in suite_checks(suite))


def check_to_dict(check: AuditCheck) -> dict[str, Any]:
    return {
        "id": check.id,
        "label": check.label,
        "module": check.module,
        "arguments": list(check.arguments),
        "source_tree_only": check.source_tree_only,
        "rationale": check.rationale,
    }


def suite_to_dict(suite: str) -> dict[str, Any]:
    return {"suite": suite, "checks": [check_to_dict(check) for check in suite_checks(suite)]}


def result_to_dict(result: AuditCheckResult) -> dict[str, Any]:
    return {
        "check": check_to_dict(result.check),
        "ok": result.ok,
        "returncode": result.returncode,
        "output": result.output,
    }


def _print_run_report(suite: str, results: tuple[AuditCheckResult, ...]) -> None:
    print(f"Audit check suite '{suite}' ({len(results)} checks)")
    for result in results:
        status = "OK" if result.ok else "FAIL"
        print(f"[{status}] {result.check.id}: {result.check.label}")
        if not result.ok and result.output:
            for line in result.output.splitlines()[-80:]:
                print(f"  {line}")


def _add_suite_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("suite", choices=suite_names())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List available check suites.")
    list_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    emit_parser = subparsers.add_parser("emit", help="Emit one suite manifest as JSON.")
    _add_suite_argument(emit_parser)

    run_parser = subparsers.add_parser("run", help="Run all checks in a suite.")
    _add_suite_argument(run_parser)
    run_parser.add_argument("--json", action="store_true", help="Emit machine-readable result JSON.")

    args = parser.parse_args(argv)

    if args.command == "list":
        if args.json:
            print(json.dumps({"suites": list(suite_names())}, indent=2))
        else:
            for suite in suite_names():
                print(suite)
        return 0

    if args.command == "emit":
        print(json.dumps(suite_to_dict(args.suite), indent=2))
        return 0

    if args.command == "run":
        results = run_suite(args.suite)
        ok = all(result.ok for result in results)
        if args.json:
            print(
                json.dumps(
                    {
                        "suite": args.suite,
                        "ok": ok,
                        "results": [result_to_dict(result) for result in results],
                    },
                    indent=2,
                )
            )
        else:
            _print_run_report(args.suite, results)
        return 0 if ok else 1

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
