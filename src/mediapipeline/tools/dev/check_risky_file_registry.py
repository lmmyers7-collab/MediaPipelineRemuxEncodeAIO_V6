"""Validate and query the machine-readable risky file registry."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from typing import Any


REPO_ROOT = find_repo_root(Path(__file__))
REGISTRY_PATH = REPO_ROOT / "docs" / "inventories" / "RISKY_FILE_REGISTRY.v1.json"
SCHEMA_PATH = REPO_ROOT / "src" / "mediapipeline" / "contracts" / "schemas" / "risky_file_registry.v1.schema.json"

REQUIRED_ENTRY_KEYS = {
    "id",
    "path_globs",
    "risk_level",
    "risk_domains",
    "validation_rung",
    "required_checks",
    "manual_gates",
    "owner_docs",
    "rationale",
}
ALLOWED_ENTRY_KEYS = REQUIRED_ENTRY_KEYS | {"allow_missing"}
VALID_RISK_LEVELS = {"critical", "high", "medium", "low"}
GIT_ENUMERATION_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class RegistryFinding:
    rule_id: str
    path: str
    message: str


@dataclass(frozen=True)
class RiskMatch:
    path: str
    entry_id: str
    risk_level: str
    validation_rung: str
    required_checks: tuple[str, ...]
    manual_gates: tuple[str, ...]


class PathEnumerationError(RuntimeError):
    """Raised when Git cannot authoritatively enumerate the requested path set."""


def normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_paths() -> set[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
            timeout=GIT_ENUMERATION_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return set()
    return {normalize_path(line) for line in result.stdout.splitlines() if line.strip()}


def _filesystem_glob_matches(pattern: str) -> set[str]:
    matches: set[str] = set()
    patterns = [pattern]
    if pattern.endswith("/**"):
        patterns.append(pattern.rstrip("*") + "**/*")
    for candidate in patterns:
        for path in REPO_ROOT.glob(candidate):
            if path.is_file():
                matches.add(path.relative_to(REPO_ROOT).as_posix())
    return matches


def _glob_matches(pattern: str, known_paths: set[str]) -> set[str]:
    normalized = normalize_path(pattern)
    matches = {path for path in known_paths if fnmatchcase(path, normalized)}
    matches.update(_filesystem_glob_matches(normalized))
    return matches


def validate_registry(registry: dict[str, Any], *, known_paths: set[str] | None = None) -> list[RegistryFinding]:
    findings: list[RegistryFinding] = []
    known = _git_paths() if known_paths is None else known_paths

    if registry.get("schema_version") != "risky_file_registry.v1":
        findings.append(RegistryFinding("RISK001", str(REGISTRY_PATH), "schema_version must be risky_file_registry.v1"))
    entries = registry.get("entries")
    if not isinstance(entries, list) or not entries:
        findings.append(RegistryFinding("RISK002", str(REGISTRY_PATH), "entries must be a non-empty list"))
        return findings

    seen_ids: set[str] = set()
    for index, raw_entry in enumerate(entries):
        path = f"entries[{index}]"
        if not isinstance(raw_entry, dict):
            findings.append(RegistryFinding("RISK003", path, "entry must be an object"))
            continue
        entry_keys = set(raw_entry)
        missing = sorted(REQUIRED_ENTRY_KEYS - entry_keys)
        extra = sorted(entry_keys - ALLOWED_ENTRY_KEYS)
        if missing:
            findings.append(RegistryFinding("RISK004", path, f"entry missing required keys: {', '.join(missing)}"))
        if extra:
            findings.append(RegistryFinding("RISK005", path, f"entry has unsupported keys: {', '.join(extra)}"))

        entry_id = raw_entry.get("id")
        if not isinstance(entry_id, str) or not entry_id.strip():
            findings.append(RegistryFinding("RISK006", path, "entry id must be a non-empty string"))
            entry_id = path
        elif entry_id in seen_ids:
            findings.append(RegistryFinding("RISK007", path, f"duplicate entry id: {entry_id}"))
        else:
            seen_ids.add(entry_id)

        risk_level = raw_entry.get("risk_level")
        if risk_level not in VALID_RISK_LEVELS:
            findings.append(RegistryFinding("RISK008", str(entry_id), f"invalid risk_level: {risk_level!r}"))

        path_globs = raw_entry.get("path_globs")
        if not isinstance(path_globs, list) or not all(isinstance(item, str) and item.strip() for item in path_globs):
            findings.append(RegistryFinding("RISK009", str(entry_id), "path_globs must be a non-empty string list"))
            path_globs = []
        if not raw_entry.get("allow_missing", False):
            for pattern in path_globs:
                if not _glob_matches(pattern, known):
                    findings.append(RegistryFinding("RISK010", str(entry_id), f"path_glob matched no files: {pattern}"))

        for key in ("risk_domains", "owner_docs"):
            value = raw_entry.get(key)
            if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
                findings.append(RegistryFinding("RISK011", str(entry_id), f"{key} must be a non-empty string list"))
                continue
            if key == "owner_docs":
                for doc_path in value:
                    normalized_doc = normalize_path(doc_path)
                    if not (REPO_ROOT / normalized_doc).is_file():
                        findings.append(
                            RegistryFinding(
                                "RISK015",
                                str(entry_id),
                                f"owner_docs entry is missing: {normalized_doc}",
                            )
                        )
        for key in ("required_checks", "manual_gates"):
            value = raw_entry.get(key)
            if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
                findings.append(RegistryFinding("RISK012", str(entry_id), f"{key} must be a string list"))
        if risk_level in {"critical", "high"} and not raw_entry.get("required_checks"):
            findings.append(RegistryFinding("RISK013", str(entry_id), "high/critical entries require required_checks"))
        for key in ("validation_rung", "rationale"):
            value = raw_entry.get(key)
            if not isinstance(value, str) or not value.strip():
                findings.append(RegistryFinding("RISK014", str(entry_id), f"{key} must be a non-empty string"))

    return findings


def classify_paths(paths: list[str], registry: dict[str, Any]) -> list[RiskMatch]:
    entries = [entry for entry in registry.get("entries", []) if isinstance(entry, dict)]
    matches: list[RiskMatch] = []
    for path in paths:
        rel = normalize_path(path)
        for entry in entries:
            for pattern in entry.get("path_globs", []):
                if fnmatchcase(rel, normalize_path(str(pattern))):
                    matches.append(
                        RiskMatch(
                            path=rel,
                            entry_id=str(entry.get("id", "")),
                            risk_level=str(entry.get("risk_level", "")),
                            validation_rung=str(entry.get("validation_rung", "")),
                            required_checks=tuple(str(item) for item in entry.get("required_checks", [])),
                            manual_gates=tuple(str(item) for item in entry.get("manual_gates", [])),
                        )
                    )
                    break
    return matches


def changed_paths(*, staged: bool = False) -> list[str]:
    args = ["git", "diff", "--name-only"]
    if staged:
        args.append("--cached")
    else:
        args.append("HEAD")
    try:
        result = subprocess.run(
            args,
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
            timeout=GIT_ENUMERATION_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise PathEnumerationError("Git executable is unavailable; use --paths only with a trusted path set.") from exc
    except subprocess.TimeoutExpired as exc:
        raise PathEnumerationError(
            f"Git changed-path enumeration timed out after {GIT_ENUMERATION_TIMEOUT_SECONDS} seconds."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = str(exc.stderr or exc.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise PathEnumerationError(f"Git changed-path enumeration failed with exit {exc.returncode}{suffix}") from exc
    except OSError as exc:
        raise PathEnumerationError(f"Git changed-path enumeration could not run: {exc}") from exc
    return [normalize_path(line) for line in result.stdout.splitlines() if line.strip()]


def render_findings(findings: list[RegistryFinding]) -> str:
    lines = ["Risky file registry validation failed:"]
    for finding in findings:
        lines.append(f"- {finding.rule_id}: {finding.path}: {finding.message}")
    return "\n".join(lines)


def render_matches(matches: list[RiskMatch]) -> str:
    if not matches:
        return "No changed paths matched the risky file registry."
    lines = ["Risky changed paths:"]
    for match in matches:
        lines.append(f"- {match.path}: {match.risk_level} via {match.entry_id} ({match.validation_rung})")
        if match.required_checks:
            lines.append("  Required checks: " + "; ".join(match.required_checks))
        if match.manual_gates:
            lines.append("  Manual gates: " + "; ".join(match.manual_gates))
    return "\n".join(lines)


def _json_payload(
    findings: list[RegistryFinding],
    matches: list[RiskMatch],
    *,
    enumeration_requested: bool,
    enumeration_error: str,
    path_count: int,
) -> str:
    return json.dumps(
        {
            "ok": not findings and not enumeration_error,
            "findings": [finding.__dict__ for finding in findings],
            "matches": [match.__dict__ for match in matches],
            "path_enumeration": {
                "requested": enumeration_requested,
                "ok": not enumeration_error if enumeration_requested else None,
                "path_count": path_count,
                "error": enumeration_error,
            },
        },
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed", action="store_true", help="Classify paths changed vs HEAD.")
    parser.add_argument("--staged", action="store_true", help="Classify staged paths.")
    parser.add_argument("--paths", nargs="*", default=[], help="Classify the listed repo-relative paths.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)

    registry = load_registry()
    findings = validate_registry(registry)
    paths = args.paths
    enumeration_requested = bool(args.changed or args.staged)
    enumeration_error = ""
    try:
        if args.changed:
            paths = changed_paths(staged=False)
        elif args.staged:
            paths = changed_paths(staged=True)
    except PathEnumerationError as exc:
        paths = []
        enumeration_error = str(exc)
    matches = classify_paths(paths, registry) if paths else []

    if args.json:
        print(
            _json_payload(
                findings,
                matches,
                enumeration_requested=enumeration_requested,
                enumeration_error=enumeration_error,
                path_count=len(paths),
            )
        )
        if enumeration_error:
            print(f"Risky changed-path enumeration failed: {enumeration_error}", file=sys.stderr)
    else:
        if findings:
            print(render_findings(findings), file=sys.stderr)
        else:
            print(f"OK: {REGISTRY_PATH.relative_to(REPO_ROOT)} is valid.")
        if enumeration_error:
            print(f"Risky changed-path enumeration failed: {enumeration_error}", file=sys.stderr)
        elif paths or enumeration_requested:
            print(render_matches(matches))
    return 1 if findings or enumeration_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
