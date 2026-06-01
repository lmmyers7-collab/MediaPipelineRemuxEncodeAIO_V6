"""AI preflight/postflight guardrail checks for repository safety work."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_risky_file_registry  # noqa: E402


Mode = Literal["preflight", "postflight"]


@dataclass(frozen=True)
class CommandCheck:
    name: str
    command: tuple[str, ...]
    required: bool = True


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    returncode: int
    output: str
    command: tuple[str, ...] = ()
    required: bool = True


def _python_command(script: str, *args: str) -> tuple[str, ...]:
    return (sys.executable, script, *args)


def build_check_plan(mode: Mode) -> list[CommandCheck]:
    # One architectural-integrity gate covering the four drift vectors:
    #   - structural drift / generated-artifact staleness (the generate_* --check
    #     scripts plus active-doc-references),
    #   - god files and bloat (check_godfiles.py),
    #   - layout/naming architecture (check_architecture_guardrails.py, lint-naming),
    #   - marketecture language (check_marketecture.py).
    # Preflight and postflight run the same plan so the working tree is held to
    # one standard before and after edits.
    common = [
        CommandCheck("summary-freshness", _python_command("scripts/dev/refresh_summaries.py", "--check")),
        CommandCheck("project-index", _python_command("scripts/dev/generate_project_index.py", "--check")),
        CommandCheck("pipeline-map", _python_command("scripts/dev/generate_pipeline_map.py", "--check")),
        CommandCheck("lifecycle-map", _python_command("scripts/dev/generate_lifecycle_map.py", "--check")),
        CommandCheck("config-schema", _python_command("scripts/dev/generate_config_schema.py", "--check")),
        CommandCheck("stage-schema", _python_command("scripts/dev/generate_stage_schema.py", "--check")),
        CommandCheck("active-doc-references", _python_command("scripts/dev/check_active_doc_references.py")),
        CommandCheck("dependency-boundaries", _python_command("scripts/dev/check_dependency_boundaries.py")),
        CommandCheck("architecture-guardrails", _python_command("scripts/dev/check_architecture_guardrails.py")),
        CommandCheck("naming-lint", _python_command("scripts/lint-naming.py")),
        CommandCheck("god-file-guard", _python_command("scripts/dev/check_godfiles.py")),
        CommandCheck("marketecture-guard", _python_command("scripts/dev/check_marketecture.py")),
        CommandCheck("risky-file-registry", _python_command("scripts/dev/check_risky_file_registry.py")),
    ]
    if mode == "preflight":
        return common
    return common


def run_command_check(check: CommandCheck) -> CheckResult:
    try:
        result = subprocess.run(
            list(check.command),
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output = result.stdout.strip()
        return CheckResult(
            name=check.name,
            ok=result.returncode == 0,
            returncode=result.returncode,
            output=output,
            command=check.command,
            required=check.required,
        )
    except OSError as exc:
        return CheckResult(
            name=check.name,
            ok=False,
            returncode=127,
            output=str(exc),
            command=check.command,
            required=check.required,
        )


def git_status_summary() -> CheckResult:
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        return CheckResult("git-status", False, 2, str(exc), required=True)
    lines = [f"branch: {branch or '(detached)'}"]
    lines.append(f"changed paths: {len(status.splitlines()) if status else 0}")
    if status:
        lines.extend(status.splitlines()[:80])
    return CheckResult("git-status", True, 0, "\n".join(lines), required=False)


def git_status_paths() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        payload = line[3:].strip()
        if " -> " in payload:
            _source, payload = payload.split(" -> ", 1)
        if payload:
            paths.append(check_risky_file_registry.normalize_path(payload))
    return paths


def risk_classification(paths: list[str]) -> tuple[list[check_risky_file_registry.RegistryFinding], list[check_risky_file_registry.RiskMatch]]:
    try:
        registry = check_risky_file_registry.load_registry()
    except (OSError, json.JSONDecodeError) as exc:
        return [check_risky_file_registry.RegistryFinding("RISKLOAD", str(check_risky_file_registry.REGISTRY_PATH), str(exc))], []
    findings = check_risky_file_registry.validate_registry(registry)
    matches = check_risky_file_registry.classify_paths(paths, registry) if not findings else []
    return findings, matches


def run_guardrail(mode: Mode, *, run_checks: bool = True) -> dict[str, object]:
    checks = build_check_plan(mode)
    git_result = git_status_summary()
    changed = git_status_paths()
    registry_findings, risk_matches = risk_classification(changed)
    results = [git_result]
    if run_checks:
        results.extend(run_command_check(check) for check in checks)
    ok = all(result.ok or not result.required for result in results) and not registry_findings
    return {
        "mode": mode,
        "ok": ok,
        "checks": results,
        "planned_checks": checks,
        "changed_paths": changed,
        "registry_findings": registry_findings,
        "risk_matches": risk_matches,
    }


def _text_report(payload: dict[str, object]) -> str:
    lines = [f"AI guardrail {payload['mode']}: {'OK' if payload['ok'] else 'FAILED'}"]
    for result in payload["checks"]:  # type: ignore[index]
        assert isinstance(result, CheckResult)
        status = "OK" if result.ok else "FAIL"
        lines.append(f"- {status}: {result.name}")
        if result.output:
            for line in result.output.splitlines()[:12]:
                lines.append(f"  {line}")
    registry_findings = payload["registry_findings"]  # type: ignore[index]
    if registry_findings:
        lines.append("Registry findings:")
        for finding in registry_findings:
            lines.append(f"- {finding.rule_id}: {finding.path}: {finding.message}")
    risk_matches = payload["risk_matches"]  # type: ignore[index]
    if risk_matches:
        lines.append("Task-appropriate validation requirements from risky file registry:")
        grouped: dict[str, list[check_risky_file_registry.RiskMatch]] = {}
        for match in risk_matches:
            grouped.setdefault(match.entry_id, []).append(match)
        for entry_id, matches in sorted(grouped.items()):
            first = matches[0]
            lines.append(f"- {entry_id}: {first.risk_level} ({first.validation_rung}); matched paths: {len(matches)}")
            for match in matches[:8]:
                lines.append(f"  Path: {match.path}")
            if len(matches) > 8:
                lines.append(f"  Path: ... {len(matches) - 8} more")
            if first.required_checks:
                lines.append("  Required checks: " + "; ".join(first.required_checks))
            if first.manual_gates:
                lines.append("  Manual gates: " + "; ".join(first.manual_gates))
    else:
        lines.append("No changed paths matched the risky file registry.")
    return "\n".join(lines)


def _json_default(value: object) -> object:
    if isinstance(value, (CheckResult, CommandCheck)):
        data = value.__dict__.copy()
        data["command"] = list(data.get("command", ()))
        return data
    if isinstance(value, (check_risky_file_registry.RegistryFinding, check_risky_file_registry.RiskMatch)):
        data = value.__dict__.copy()
        if "required_checks" in data:
            data["required_checks"] = list(data["required_checks"])
        if "manual_gates" in data:
            data["manual_gates"] = list(data["manual_gates"])
        return data
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "postflight"))
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--no-run", action="store_true", help="Plan checks without running command checks.")
    args = parser.parse_args(argv)

    payload = run_guardrail(args.mode, run_checks=not args.no_run)
    if args.json:
        print(json.dumps(payload, indent=2, default=_json_default))
    else:
        print(_text_report(payload))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
