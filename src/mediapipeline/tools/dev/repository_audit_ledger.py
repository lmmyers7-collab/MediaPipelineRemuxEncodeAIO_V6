"""Build and validate the exhaustive repository-audit coverage ledger.

The ledger deliberately starts every reviewable file in a non-terminal state.
Automated inventory is evidence about presence, hashes, ownership, and size; it
is not evidence that a human or agent semantically reviewed the file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from fnmatch import fnmatchcase
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "reviews" / "full-repository-audit-2026-07-20"
PROJECT_INDEX_PATH = REPO_ROOT / "docs" / "generated" / "PROJECT_INDEX.jsonl"
RISKY_FILE_REGISTRY_PATH = REPO_ROOT / "docs" / "inventories" / "RISKY_FILE_REGISTRY.v1.json"
AUDIT_CHANGE_PACKET_PATH = "ops/release/changes/unreleased/MP-CHANGE-2026-0720-011.json"
SCHEMA_VERSION = 2
WINDOWS_RESERVED_COMPONENT_STEMS = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        "conin$",
        "conout$",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
        *(f"com{number}" for number in ("¹", "²", "³")),
        *(f"lpt{number}" for number in ("¹", "²", "³")),
    }
)
WINDOWS_INVALID_COMPONENT_CHARACTERS = frozenset('<>:"|?*')
ALLOWED_GIT_INDEX_MODES = frozenset({"100644", "100755", "120000", "160000"})

TERMINAL_STATUSES = frozenset(
    {
        "line_reviewed_no_findings",
        "line_reviewed_with_findings",
        "generated_verified",
        "vendor_verified",
        "binary_inventoried",
        "archive_inventoried",
        "metadata_verified",
        "blocked_with_reason",
    }
)
ACHIEVED_STATUSES = TERMINAL_STATUSES.difference({"blocked_with_reason"})
ALLOWED_STATUSES = frozenset({"pending", "in_review", *TERMINAL_STATUSES})
ALLOWED_CATEGORIES = frozenset(
    {
        "first-party executable source",
        "first-party test or fixture",
        "behavior-defining configuration/schema/workflow",
        "active documentation",
        "generated artifact",
        "vendored/third-party source",
        "bundled runtime/tool",
        "binary/media/font/image/archive",
        "historical archived evidence",
        "metadata/packaging",
    }
)
REQUIRED_ROW_FIELDS = frozenset(
    {
        "path",
        "is_tracked",
        "git_blob_hash",
        "content_sha256",
        "file_category",
        "owner_domain",
        "architectural_layer",
        "language_or_type",
        "total_lines",
        "source_lines",
        "assigned_worker",
        "review_status",
        "review_depth",
        "reviewed_symbols_or_sections",
        "responsibility_summary",
        "incoming_dependencies",
        "outgoing_dependencies",
        "api_routes",
        "commands",
        "state_files",
        "config_keys",
        "process_boundaries",
        "artifacts",
        "relevant_tests",
        "finding_ids",
        "error_ids",
        "prior_audit_coverage",
        "evidence_commands",
        "reviewer",
        "reviewer_notes",
        "second_review_status",
        "risk_tier",
        "schema_version",
        "git_mode",
        "file_size_bytes",
        "generated",
        "vendor",
        "archive",
        "binary",
        "runtime",
        "evidence_snapshot",
        "line_count_method",
        "invoked_tools",
        "project_index_present",
        "project_index_hash_matches",
        "project_index_reconciliation",
        "verification_obligations",
        "verified_obligations",
        "content_source",
    }
)
REQUIRED_ERROR_FIELDS = frozenset(
    {
        "id",
        "timestamp",
        "command",
        "working_directory",
        "exit_code",
        "output_summary",
        "phase",
        "classification",
        "reproduction_status",
        "retry_result",
        "linked_finding_ids",
        "coverage_blocked",
        "disposition",
    }
)
REQUIRED_FINDING_FIELDS = frozenset(
    {
        "id",
        "severity",
        "confidence",
        "category",
        "title",
        "locations",
        "observed_behavior",
        "expected_invariant",
        "root_cause",
        "failure_scenario",
        "evidence",
        "affected_flows",
        "existing_safeguards",
        "safeguard_gap",
        "tests_present",
        "tests_missing",
        "recommended_remediation",
        "remediation_risk",
        "validation_rung",
        "related_finding_ids",
        "prior_audit_relationship",
        "disposition",
    }
)
ALLOWED_FINDING_SEVERITIES = frozenset({"P0", "P1", "P2", "P3"})
ALLOWED_FINDING_CONFIDENCE = frozenset({"low", "medium", "high"})
FINDING_CONFIDENCE_ALIASES = {"high for the redaction mechanism; medium for accepted-route reachability": "medium"}
ALLOWED_FINDING_DISPOSITIONS = frozenset(
    {"confirmed", "needs-runtime-proof", "expected-by-design", "false-positive-with-proof", "blocked", "deferred-with-reason", "resolved-in-audit"}
)
FINDING_DISPOSITION_ALIASES = {"still_present": "confirmed"}
LINE_REVIEW_CATEGORIES = frozenset(
    {
        "first-party executable source",
        "first-party test or fixture",
        "behavior-defining configuration/schema/workflow",
        "active documentation",
    }
)
CATEGORY_TERMINAL_STATUSES: dict[str, frozenset[str]] = {
    **{category: frozenset({"line_reviewed_no_findings", "line_reviewed_with_findings"}) for category in LINE_REVIEW_CATEGORIES},
    "generated artifact": frozenset({"generated_verified"}),
    "vendored/third-party source": frozenset({"vendor_verified"}),
    "bundled runtime/tool": frozenset({"vendor_verified"}),
    "binary/media/font/image/archive": frozenset({"binary_inventoried"}),
    "historical archived evidence": frozenset({"archive_inventoried"}),
    "metadata/packaging": frozenset({"metadata_verified"}),
}
ALLOWED_PROJECT_INDEX_RECONCILIATIONS = frozenset(
    {"not_reconciled", "hash_matched", "stale_unreconciled", "stale_with_finding", "not_indexed_with_rationale"}
)
ALLOWED_ERROR_CLASSIFICATIONS = frozenset(
    {
        "confirmed repository defect",
        "test failure",
        "expected negative-path result",
        "environment/setup issue",
        "missing external fixture",
        "sandbox/permission failure",
        "flaky/non-deterministic",
        "informational warning",
    }
)
LEGACY_ERROR_CLASSIFICATION_MAP = {
    "agent-orchestration parameter error": "environment/setup issue",
    "aggregate-test-coverage-gap": "confirmed repository defect",
    "artifact-append-context-mismatch": "environment/setup issue",
    "assignment-scope-limitation": "informational warning",
    "audit-suite-coverage-gap": "confirmed repository defect",
    "audit-tool defect plus concurrent-worktree drift": "confirmed repository defect",
    "benign-stderr": "informational warning",
    "bounded-context-omission": "informational warning",
    "browser-skip-downshift-risk": "confirmed repository defect",
    "ci-dependency-gap": "confirmed repository defect",
    "ci-trigger-coverage-gap": "confirmed repository defect",
    "codec-dependent-green-skip": "confirmed repository defect",
    "confirmed-current-test-failure": "test failure",
    "coverage-instrumentation-gap": "confirmed repository defect",
    "dependency-declaration-gap": "confirmed repository defect",
    "dirty-worktree-warning": "informational warning",
    "display-format-truncation": "informational warning",
    "environment-gated-test-coverage": "missing external fixture",
    "expected adversarial regression failures": "expected negative-path result",
    "expected discovery no-match": "expected negative-path result",
    "expected error log in passing regression suite": "expected negative-path result",
    "expected monitoring timeout": "expected negative-path result",
    "expected negative-path result with concurrent-worktree drift": "expected negative-path result",
    "expected synthetic route exception": "expected negative-path result",
    "expected-test-fixture-warning": "expected negative-path result",
    "expected-negative-search": "expected negative-path result",
    "generated-artifact-drift": "confirmed repository defect",
    "incorrect-discovery-path": "environment/setup issue",
    "incorrect-path-invocation": "environment/setup issue",
    "informational bounded-context omission": "informational warning",
    "input-artifact truncation": "informational warning",
    "inspection-command-construction-error": "environment/setup issue",
    "inspection-nonzero": "environment/setup issue",
    "inspection-orchestration-error": "environment/setup issue",
    "inspection-script-syntax-error": "environment/setup issue",
    "inspection-warning": "informational warning",
    "intentional-validation-skip": "informational warning",
    "methodology-error-corrected": "informational warning",
    "methodology/evidence correction": "informational warning",
    "misleading-validation-scope": "confirmed repository defect",
    "missing generated dependency": "confirmed repository defect",
    "missing-input-path": "environment/setup issue",
    "missing-local-tool": "missing external fixture",
    "missing-shell-entrypoint-with-fallback": "environment/setup issue",
    "mixed truncation-and-path-error": "environment/setup issue",
    "mixed-success-path-error": "environment/setup issue",
    "navigation-summary-gap": "confirmed repository defect",
    "non-gating-security-scan": "confirmed repository defect",
    "nonexecuting-plan": "informational warning",
    "optional-tool-green-skip": "missing external fixture",
    "powershell-parser-error": "environment/setup issue",
    "read-only-validation-gap": "confirmed repository defect",
    "record-payload-misalignment": "environment/setup issue",
    "release-gate-downshift": "confirmed repository defect",
    "review-capacity-skip": "informational warning",
    "safety-scope-limitation": "informational warning",
    "script-runtime-exception": "environment/setup issue",
    "script-syntax-exception": "environment/setup issue",
    "security-result-publication-gap": "confirmed repository defect",
    "shell-expansion-warning": "environment/setup issue",
    "shell-quoting-error": "environment/setup issue",
    "soft-fail-static-analysis": "confirmed repository defect",
    "soft-fail-toolchain-prerequisite": "confirmed repository defect",
    "stale-snapshot-limitation": "informational warning",
    "test-discovery-gap": "confirmed repository defect",
    "tool output-limit warning": "informational warning",
    "tool-missing-green-skip": "confirmed repository defect",
    "tool-output-truncation": "informational warning",
    "tool-output-truncation-data-loss": "informational warning",
    "windows-path-glob-error": "environment/setup issue",
    "wrapper-inventory-gap": "confirmed repository defect",
}
HISTORICAL_FINDING_PREFIXES = ("CPA-2026-07-19-", "FR-")
LEGACY_EXTERNAL_FINDING_IDS = frozenset({"AUDIT-FIND-002"})
BASELINE_EVIDENCE_COMMANDS = frozenset({"git ls-files -z", "docs/generated/PROJECT_INDEX.jsonl"})
DEFAULT_RESPONSIBILITY_SUMMARY = "Inventory classification pending semantic review."

CODE_EXTENSIONS = frozenset(
    {".bat", ".cjs", ".cmd", ".css", ".html", ".js", ".mjs", ".ps1", ".psd1", ".psm1", ".py", ".rs", ".ts", ".tsx"}
)
CONFIG_EXTENSIONS = frozenset(
    {".cfg", ".ini", ".json", ".jsonl", ".lock", ".toml", ".xml", ".yaml", ".yml"}
)
TEXT_EXTENSIONS = frozenset(
    {
        *CODE_EXTENSIONS,
        *CONFIG_EXTENSIONS,
        ".csv",
        ".gitignore",
        ".gitattributes",
        ".md",
        ".properties",
        ".rst",
        ".txt",
    }
)
BINARY_EXTENSIONS = frozenset(
    {
        ".7z",
        ".a",
        ".avi",
        ".bin",
        ".bmp",
        ".class",
        ".dll",
        ".dylib",
        ".eot",
        ".exe",
        ".gif",
        ".gz",
        ".ico",
        ".jar",
        ".jpeg",
        ".jpg",
        ".lib",
        ".mkv",
        ".mov",
        ".mp3",
        ".mp4",
        ".o",
        ".otf",
        ".pdf",
        ".png",
        ".pyc",
        ".so",
        ".tar",
        ".ttf",
        ".wasm",
        ".webm",
        ".webp",
        ".woff",
        ".woff2",
        ".zip",
    }
)

RUNTIME_PREFIXES = (
    "apps/desktop/runtime/",
    "ops/pipeline/runtime/",
    "ops/pipeline/tools/",
)
GENERATED_PREFIXES = (
    "artifacts/",
    "docs/generated/",
    "apps/desktop/tauri/src-tauri/gen/",
)
VENDOR_MARKERS = (
    "/node_modules/",
    "/third_party/",
    "/third-party/",
    "/vendor/",
    "/vendors/",
)
TEST_PREFIXES = (
    "tests/",
    "ops/pipeline/tests/",
)
FIRST_PARTY_PREFIXES = (
    ".github/",
    "apps/desktop/launchers/",
    "apps/desktop/tauri/",
    "apps/desktop/webview/",
    "ops/pipeline/config/",
    "ops/pipeline/engine/",
    "ops/pipeline/entrypoints/",
    "ops/scripts/",
    "src/",
)

PRESERVED_REVIEW_FIELDS = (
    "review_status",
    "review_depth",
    "reviewed_symbols_or_sections",
    "reviewer",
    "finding_ids",
    "error_ids",
    "prior_audit_coverage",
    "evidence_commands",
    "reviewer_notes",
    "second_review_status",
    "project_index_reconciliation",
    "verified_obligations",
)
REVIEW_OVERRIDE_FIELDS = frozenset(
    {
        *PRESERVED_REVIEW_FIELDS,
        "responsibility_summary",
        "incoming_dependencies",
        "outgoing_dependencies",
        "api_routes",
        "commands",
        "state_files",
        "config_keys",
        "process_boundaries",
        "artifacts",
        "relevant_tests",
    }
)
REQUIRED_REVIEW_FRAGMENT_FIELDS = frozenset(
    {
        "path",
        "content_sha256",
        "assigned_worker",
        "review_status",
        "review_depth",
        "reviewed_symbols_or_sections",
        "reviewer",
        "finding_ids",
        "error_ids",
        "prior_audit_coverage",
        "evidence_commands",
        "reviewer_notes",
        "second_review_status",
        "project_index_reconciliation",
        "verified_obligations",
    }
)
REQUIRED_SECOND_REVIEW_ATTESTATION_FIELDS = frozenset(
    {
        "path",
        "content_sha256",
        "assigned_worker",
        "review_status",
        "review_depth",
        "reviewed_symbols_or_sections",
        "first_reviewer",
        "reviewer",
        "independence_basis",
        "finding_ids",
        "finding_dispositions",
        "error_ids",
        "evidence_commands",
        "reviewer_notes",
        "second_review_status",
    }
)


def canonical_path(value: str | Path) -> str:
    """Return a stable repository-relative POSIX path."""

    text = str(value).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return PurePosixPath(text).as_posix()


def strict_repository_relative_path(value: str | Path) -> str:
    """Return one unambiguous repository-relative path or raise ``ValueError``."""

    text = str(value).replace("\\", "/")
    if not text or text.startswith("/") or (len(text) >= 2 and text[0].isalpha() and text[1] == ":"):
        raise ValueError("path must be repository-relative")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("path must not contain empty, dot, or parent segments")
    for part in parts:
        if part.endswith((".", " ")):
            raise ValueError("path components must not end with a dot or space")
        if any(ord(character) < 32 or character in WINDOWS_INVALID_COMPONENT_CHARACTERS for character in part):
            raise ValueError("path contains a Windows-invalid component character")
        if part.split(".", 1)[0].casefold() in WINDOWS_RESERVED_COMPONENT_STEMS:
            raise ValueError("path contains a Windows-reserved device component")
    normalized = PurePosixPath(*parts).as_posix()
    if normalized in {"", "."}:
        raise ValueError("path must identify a repository file")
    return normalized


def resolved_repository_path(root: Path, value: str | Path) -> tuple[str, Path]:
    """Validate lexical identity and prove the resolved path stays under ``root``."""

    relative = strict_repository_relative_path(value)
    resolved_root = root.resolve()
    lexical_absolute = resolved_root / PurePosixPath(relative)
    absolute = lexical_absolute.resolve(strict=False)
    try:
        resolved_relative = absolute.relative_to(resolved_root).as_posix()
    except ValueError as exc:
        raise ValueError("path resolves outside the repository root") from exc
    same_spelling = (
        resolved_relative.casefold() == relative.casefold()
        if os.name == "nt"
        else resolved_relative == relative
    )
    if not same_spelling and not lexical_absolute.is_symlink():
        raise ValueError("path spelling does not match its resolved repository-relative identity")
    return relative, absolute


def resolved_regular_worktree_path(root: Path, value: str | Path) -> Path:
    """Return a contained regular-path candidate without following a leaf link."""

    relative, absolute = resolved_repository_path(root, value)
    lexical_absolute = root.resolve() / PurePosixPath(relative)
    if lexical_absolute.is_symlink():
        raise ValueError("worktree path is a symlink but the Git index mode is regular")
    return absolute


def run_git(args: Sequence[str], *, root: Path = REPO_ROOT) -> bytes:
    """Run a read-only Git query and return its bytes."""

    return subprocess.check_output(["git", *args], cwd=root)


def nul_paths(payload: bytes) -> list[str]:
    return [item.decode("utf-8", errors="surrogateescape") for item in payload.split(b"\0") if item]


def git_tracked_paths(*, root: Path = REPO_ROOT) -> list[str]:
    return sorted((canonical_path(path) for path in nul_paths(run_git(["ls-files", "-z"], root=root))), key=str.casefold)


def git_untracked_paths(*, root: Path = REPO_ROOT) -> list[str]:
    return sorted(
        (canonical_path(path) for path in nul_paths(run_git(["ls-files", "--others", "--exclude-standard", "-z"], root=root))),
        key=str.casefold,
    )


def git_blob_map(*, root: Path = REPO_ROOT) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    unresolved_paths: set[str] = set()
    windows_identities: dict[str, str] = {}
    for raw_record in run_git(["ls-files", "--stage", "-z"], root=root).split(b"\0"):
        if not raw_record:
            continue
        metadata, raw_path = raw_record.split(b"\t", 1)
        mode, blob_hash, stage = metadata.decode("ascii").split()
        path = canonical_path(raw_path.decode("utf-8", errors="surrogateescape"))
        try:
            strict_repository_relative_path(path)
        except ValueError as exc:
            raise ValueError(f"invalid Windows-portable Git index path {path!r}: {exc}") from exc
        windows_identity = path.casefold()
        prior_spelling = windows_identities.get(windows_identity)
        if prior_spelling is not None and prior_spelling != path:
            raise ValueError(f"ambiguous Windows Git path identity: {prior_spelling}, {path}")
        windows_identities[windows_identity] = path
        if stage != "0":
            unresolved_paths.add(path)
            continue
        if path in result:
            raise ValueError(f"duplicate stage-0 Git index entry: {path}")
        if mode not in ALLOWED_GIT_INDEX_MODES:
            raise ValueError(f"unsupported stage-0 Git index mode {mode} for {path}")
        result[path] = (mode, blob_hash)
    if unresolved_paths:
        raise ValueError("unresolved Git index stages: " + ", ".join(sorted(unresolved_paths, key=str.casefold)))
    return result


def audit_owned_untracked_paths(*, root: Path = REPO_ROOT) -> set[str]:
    """Return task-owned nonignored paths without absorbing concurrent work."""

    owned = {
        AUDIT_CHANGE_PACKET_PATH,
        "src/mediapipeline/tools/dev/repository_audit_ledger.py",
        "tests/python/tooling/test_repository_audit_ledger.py",
    }
    packet_path = root / AUDIT_CHANGE_PACKET_PATH
    if packet_path.is_file():
        try:
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            packet = {}
        owned.update(canonical_path(path) for path in packet.get("files_touched", []) if isinstance(path, str))
    return owned


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git_blob_bytes(blob_hash: str, *, root: Path = REPO_ROOT) -> bytes:
    """Read the exact stage-0 Git object used when a tracked worktree file is absent."""

    return run_git(["cat-file", "blob", blob_hash], root=root)


def is_probably_text_bytes(payload: bytes, rel_path: str) -> bool:
    suffix = PurePosixPath(rel_path).suffix.casefold()
    if suffix in BINARY_EXTENSIONS:
        return False
    if suffix in TEXT_EXTENSIONS or PurePosixPath(rel_path).name.casefold() in {
        "dockerfile",
        "license",
        "makefile",
        "notice",
    }:
        return True
    sample = payload[:65536]
    if sample.startswith((b"\xff\xfe", b"\xfe\xff")):
        return True
    return b"\0" not in sample


def is_probably_text(path: Path, rel_path: str) -> bool:
    try:
        sample = path.read_bytes()[:65536]
    except OSError:
        return False
    return is_probably_text_bytes(sample, rel_path)


def text_line_counts_bytes(raw: bytes) -> tuple[int, int]:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = raw.decode("utf-16", errors="replace")
    else:
        text = raw.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    return len(lines), sum(1 for line in lines if line.strip())


def text_line_counts(path: Path) -> tuple[int | None, int | None]:
    """Return total and nonblank line counts for a text file."""

    try:
        raw = path.read_bytes()
    except OSError:
        return None, None
    return text_line_counts_bytes(raw)


def bool_path_marker(rel_path: str, markers: Iterable[str]) -> bool:
    lowered = f"/{canonical_path(rel_path).casefold().strip('/')}/"
    return any(marker.casefold() in lowered for marker in markers)


def classification_for(rel_path: str, *, text: bool, binary: bool) -> tuple[str, dict[str, bool]]:
    path = canonical_path(rel_path)
    lowered = path.casefold()
    suffix = PurePosixPath(path).suffix.casefold()
    generated = lowered.startswith(GENERATED_PREFIXES) or "/generated/" in f"/{lowered}"
    archived = lowered.startswith(("docs/archive/", "archive/"))
    runtime = lowered.startswith(RUNTIME_PREFIXES)
    vendor = bool_path_marker(lowered, VENDOR_MARKERS)

    flags = {
        "generated": generated,
        "vendor": vendor,
        "archive": archived,
        "binary": binary,
        "runtime": runtime,
        "evidence_snapshot": lowered.startswith(("docs/audits/", "docs/reviews/")),
    }
    if archived:
        return "historical archived evidence", flags
    if runtime:
        return "bundled runtime/tool", flags
    if vendor:
        return "vendored/third-party source", flags
    if generated:
        return "generated artifact", flags
    if binary:
        return "binary/media/font/image/archive", flags
    if lowered.startswith(TEST_PREFIXES):
        return "first-party test or fixture", flags
    if lowered.startswith("ops/release/changes/"):
        return "metadata/packaging", flags
    config_names = {".gitattributes", ".gitignore", ".pre-commit-config.yaml", ".rgignore"}
    if (
        lowered.startswith((".github/workflows/", "requirements/"))
        or PurePosixPath(lowered).name in config_names
        or suffix in CONFIG_EXTENSIONS
        or suffix == ".psd1"
    ):
        return "behavior-defining configuration/schema/workflow", flags
    if suffix in CODE_EXTENSIONS and lowered.startswith(FIRST_PARTY_PREFIXES):
        return "first-party executable source", flags
    if suffix == ".md" or PurePosixPath(path).name.casefold() in {"agents.md", "readme"}:
        return "active documentation", flags
    if text and lowered.startswith(FIRST_PARTY_PREFIXES):
        return "behavior-defining configuration/schema/workflow", flags
    return "metadata/packaging", flags


def fallback_owner_and_layer(path: str, category: str) -> tuple[str, str]:
    parts = PurePosixPath(path).parts
    if path.startswith("src/mediapipeline/core/") and len(parts) > 3:
        return parts[3], "python-domain"
    if path.startswith("src/mediapipeline/contracts/"):
        return "contracts", "state-config"
    if path.startswith("src/mediapipeline/desktop/api/"):
        return "api", "local-api"
    if path.startswith("src/mediapipeline/desktop/"):
        return "desktop", "python-domain"
    if path.startswith("apps/desktop/webview/"):
        return "webview", "webview-tauri"
    if path.startswith("apps/desktop/tauri/"):
        return "shell", "webview-tauri"
    if path.startswith("ops/pipeline/engine/") and len(parts) > 3:
        return parts[3], "powershell-engine"
    if path.startswith("tests/") or path.startswith("ops/pipeline/tests/"):
        return "tests", "tests"
    if path.startswith("docs/"):
        return "documentation", "boundary-validation-docs" if "/architecture/" in path or "/operator/" in path else "secondary-evidence"
    if category == "bundled runtime/tool":
        return "runtime", "runtime-artifact"
    return "repository", "secondary-evidence"


@lru_cache(maxsize=8)
def load_risky_file_registry(path: Path = RISKY_FILE_REGISTRY_PATH) -> list[dict[str, Any]]:
    """Load and validate the authoritative risky-path registry."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load risky-file registry {path}: {exc}") from exc
    if payload.get("schema_version") != "risky_file_registry.v1" or not isinstance(payload.get("entries"), list):
        raise ValueError(f"invalid risky-file registry shape: {path}")
    entries: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(payload["entries"], start=1):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"risky-file registry entry {index} is not an object")
        entry_id = str(raw_entry.get("id", "")).strip()
        risk_level = str(raw_entry.get("risk_level", "")).strip()
        globs = raw_entry.get("path_globs")
        if not entry_id or risk_level not in {"low", "medium", "high", "critical"}:
            raise ValueError(f"risky-file registry entry {index} has invalid id or risk_level")
        if not isinstance(globs, list) or not globs or any(not isinstance(pattern, str) or not pattern.strip() for pattern in globs):
            raise ValueError(f"risky-file registry entry {entry_id} has invalid path_globs")
        entries.append(raw_entry)
    return entries


def registry_risk_tier(path: str, *, registry_path: Path = RISKY_FILE_REGISTRY_PATH) -> str:
    """Return the strongest risk tier matched by the authoritative registry."""

    normalized = canonical_path(path).casefold()
    risk_rank = {"low": 0, "medium": 1, "high": 2, "critical": 2}
    strongest = "low"
    for entry in load_risky_file_registry(registry_path):
        if any(fnmatchcase(normalized, canonical_path(pattern).casefold()) for pattern in entry["path_globs"]):
            candidate = "high" if entry["risk_level"] == "critical" else str(entry["risk_level"])
            if risk_rank[candidate] > risk_rank[strongest]:
                strongest = candidate
    return strongest


def fallback_risk_tier(
    path: str,
    category: str,
    *,
    registry_path: Path = RISKY_FILE_REGISTRY_PATH,
) -> str:
    registry_risk = registry_risk_tier(path, registry_path=registry_path)
    if registry_risk == "high" or category not in LINE_REVIEW_CATEGORIES:
        return registry_risk
    lowered = canonical_path(path).casefold()
    high_markers = (
        "ffmpeg",
        "transcode",
        "subtitle",
        "audio",
        "publish",
        "final_library",
        "rename",
        "network",
        "queue",
        "settings",
        "config",
        "lifecycle",
        "process",
        "command_journal",
        "close_readiness",
        "mediapipeline.ps1",
    )
    if any(marker in lowered for marker in high_markers):
        return "high"
    if path.startswith(("src/mediapipeline/", "ops/pipeline/engine/", "ops/pipeline/entrypoints/", "apps/desktop/tauri/")):
        return "medium" if registry_risk == "low" else registry_risk
    return registry_risk


def verification_obligations_for(category: str, flags: Mapping[str, Any]) -> list[str]:
    """Derive every semantic/verification obligation from category and flags."""

    obligations: set[str] = set()
    if category in LINE_REVIEW_CATEGORIES:
        obligations.add("semantic_line_review")
    category_obligations = {
        "generated artifact": "generated_provenance_and_reproducibility",
        "vendored/third-party source": "vendor_provenance_and_integrity",
        "bundled runtime/tool": "runtime_provenance_and_integrity",
        "binary/media/font/image/archive": "binary_metadata_and_packaging",
        "historical archived evidence": "archive_reference_and_authority_check",
        "metadata/packaging": "metadata_packaging_review",
    }
    if category in category_obligations:
        obligations.add(category_obligations[category])
    flag_obligations = {
        "generated": "generated_provenance_and_reproducibility",
        "vendor": "vendor_provenance_and_integrity",
        "runtime": "runtime_provenance_and_integrity",
        "binary": "binary_metadata_and_packaging",
        "archive": "archive_reference_and_authority_check",
        "evidence_snapshot": "snapshot_authority_and_current_reference_check",
    }
    for flag, obligation in flag_obligations.items():
        if flags.get(flag):
            obligations.add(obligation)
    return sorted(obligations)


def worker_for(path: str, category: str) -> str:
    lowered = canonical_path(path).casefold()
    if category in {"bundled runtime/tool", "vendored/third-party source", "binary/media/font/image/archive"}:
        return "worker-13-runtime-vendor-binary"
    if lowered.startswith(("tests/", "ops/pipeline/tests/", "src/mediapipeline/tools/")):
        return "worker-11-tests-tooling"
    if lowered.startswith("src/mediapipeline/desktop/") or lowered.startswith("src/mediapipeline/core/api/"):
        return "worker-01-backend-api-application"
    if lowered.startswith("apps/desktop/webview/static/assets/"):
        page_tokens = ("queue", "launch", "completed", "pending", "rename", "settings", "diagnostics", "network", "schedule", "telemetry")
        return "worker-08-webview-pages" if any(token in lowered for token in page_tokens) else "worker-07-webview-common"
    if lowered.startswith("apps/desktop/webview/"):
        return "worker-07-webview-common"
    if lowered.startswith("apps/desktop/tauri/"):
        return "worker-09-tauri-shell"
    if any(token in lowered for token in ("/config/", "/settings/", "/library/", "library_profiles")):
        return "worker-02-config-settings-library"
    if any(token in lowered for token in ("/queue/", "/processes/", "/schedule/", "/status/", "/watch/")):
        return "worker-03-queue-process-status"
    if any(token in lowered for token in ("/publish/", "/completed/", "/final_library/", "/rename/")):
        return "worker-04-publish-completed-rename"
    if any(token in lowered for token in ("/decide/", "/transcode/", "/subtitles/", "/audio/", "ffmpeg", "ass_to_srt")):
        return "worker-05-media-policy"
    if any(token in lowered for token in ("/contracts/", "/storage/", "/observability/", "/telemetry/", "/failures/")):
        return "worker-06-contracts-storage-observability"
    if lowered.startswith(("ops/", ".github/")):
        return "worker-10-ops-workflows"
    return "worker-12-docs-generated-other"


def load_project_index(path: Path = PROJECT_INDEX_PATH) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return records
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            record_path = canonical_path(str(payload.get("path", "")))
            if not record_path:
                raise ValueError(f"PROJECT_INDEX record {line_number} has no path")
            if record_path in records:
                raise ValueError(f"duplicate PROJECT_INDEX path: {record_path}")
            records[record_path] = payload
    return records


def load_existing_rows(path: Path) -> dict[str, dict[str, Any]]:
    return {canonical_path(row["path"]): row for row in load_rows(path)}


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_rows(
    *,
    root: Path = REPO_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    project_records: Mapping[str, Mapping[str, Any]] | None = None,
    existing_rows: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    project_records = project_records if project_records is not None else load_project_index()
    existing_rows = existing_rows or {}
    tracked = set(git_tracked_paths(root=root))
    untracked = set(git_untracked_paths(root=root))
    candidates = tracked.union(untracked.intersection(audit_owned_untracked_paths(root=root)))
    try:
        output_rel = canonical_path(output_dir.resolve().relative_to(root.resolve()))
    except ValueError:
        output_rel = ""
    if output_rel:
        candidates = {path for path in candidates if path != output_rel and not path.startswith(output_rel + "/")}
    blob_map = git_blob_map(root=root)
    rows: list[dict[str, Any]] = []
    for rel_path in sorted(candidates, key=lambda value: (value.casefold(), value)):
        mode, blob_hash = blob_map.get(rel_path, ("", ""))
        special_git_mode = mode in {"120000", "160000"}
        worktree_absolute: Path | None = None
        worktree_path_error = ""
        if not special_git_mode:
            try:
                worktree_absolute = resolved_regular_worktree_path(root, rel_path)
            except ValueError as exc:
                worktree_path_error = str(exc)
        if mode == "120000":
            content_source = "git_index_blob"
            index_payload = git_blob_bytes(blob_hash, root=root)
            file_size = len(index_payload)
            text = True
            content_hash = sha256_bytes(index_payload)
            total_lines, source_lines = text_line_counts_bytes(index_payload)
        elif mode == "160000":
            content_source = "git_index_gitlink"
            gitlink_identity = f"gitlink:{blob_hash}".encode("ascii")
            file_size = len(gitlink_identity)
            text = False
            content_hash = sha256_bytes(gitlink_identity)
            total_lines, source_lines = None, None
        elif worktree_path_error:
            content_source = "unsafe_worktree_path"
            file_size = None
            text = False
            content_hash = ""
            total_lines, source_lines = None, None
        elif worktree_absolute is not None and worktree_absolute.is_file():
            content_source = "worktree"
            file_size = worktree_absolute.stat().st_size
            text = is_probably_text(worktree_absolute, rel_path)
            content_hash = sha256_file(worktree_absolute)
            total_lines, source_lines = text_line_counts(worktree_absolute) if text else (None, None)
        elif rel_path in tracked and blob_hash:
            content_source = "git_index_blob"
            index_payload = git_blob_bytes(blob_hash, root=root)
            file_size = len(index_payload)
            text = is_probably_text_bytes(index_payload, rel_path)
            content_hash = sha256_bytes(index_payload)
            total_lines, source_lines = text_line_counts_bytes(index_payload) if text else (None, None)
        else:
            content_source = "unavailable"
            file_size = None
            text = False
            content_hash = ""
            total_lines, source_lines = None, None
        binary = not special_git_mode and content_source not in {"unavailable", "unsafe_worktree_path"} and not text
        if special_git_mode:
            category = "metadata/packaging"
            flags = {
                "generated": False,
                "vendor": False,
                "archive": False,
                "binary": False,
                "runtime": False,
                "evidence_snapshot": False,
            }
        else:
            category, flags = classification_for(rel_path, text=text, binary=binary)
        project = dict(project_records.get(rel_path, {}))
        fallback_owner, fallback_layer = fallback_owner_and_layer(rel_path, category)
        indexed_risk = str(project.get("risk_tier", "unknown"))
        fallback_risk = fallback_risk_tier(rel_path, category)
        risk_rank = {"unknown": -1, "low": 0, "medium": 1, "high": 2}
        risk_tier = indexed_risk if risk_rank.get(indexed_risk, -1) >= risk_rank[fallback_risk] else fallback_risk
        project_index_present = rel_path in project_records
        project_index_hash_matches = bool(project) and project.get("source_hash") == content_hash
        project_index_reconciliation = (
            "hash_matched" if project_index_hash_matches else "stale_unreconciled" if project_index_present else "not_reconciled"
        )
        verification_obligations = verification_obligations_for(category, flags)
        row: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "path": rel_path,
            "is_tracked": rel_path in tracked,
            "git_mode": mode,
            "git_blob_hash": blob_hash,
            "content_sha256": content_hash,
            "content_source": content_source,
            "file_size_bytes": file_size,
            "file_category": category,
            "owner_domain": project.get("owner_domain", fallback_owner),
            "architectural_layer": project.get("layer", fallback_layer),
            "language_or_type": project.get(
                "file_type",
                "git-symlink"
                if mode == "120000"
                else "gitlink"
                if mode == "160000"
                else PurePosixPath(rel_path).suffix.casefold().lstrip(".") or "none",
            ),
            "generated": flags["generated"],
            "vendor": flags["vendor"],
            "archive": flags["archive"],
            "binary": flags["binary"],
            "runtime": flags["runtime"],
            "evidence_snapshot": flags["evidence_snapshot"],
            "total_lines": total_lines,
            "source_lines": source_lines,
            "line_count_method": (
                "Gitlink commit-object identity; no worktree or blob content"
                if mode == "160000"
                else f"physical and nonblank text lines from {content_source} bytes"
                if text
                else f"not applicable to binary content from {content_source}"
                if binary
                else "content unavailable"
            ),
            "assigned_worker": worker_for(rel_path, category),
            "review_status": "pending",
            "review_depth": "inventory_only",
            "reviewed_symbols_or_sections": [],
            "responsibility_summary": project.get("purpose", DEFAULT_RESPONSIBILITY_SUMMARY),
            "incoming_dependencies": project.get("inbound_dependents", []),
            "outgoing_dependencies": project.get("outbound_dependencies", []),
            "api_routes": project.get("api_routes", []),
            "commands": [],
            "invoked_tools": project.get("invoked_tools", []),
            "state_files": project.get("state_files", []),
            "config_keys": [],
            "process_boundaries": project.get("invoked_stages", []),
            "artifacts": [],
            "relevant_tests": project.get("associated_tests", []),
            "finding_ids": [],
            "error_ids": [],
            "prior_audit_coverage": "not_reconciled",
            "evidence_commands": ["git ls-files -z", "docs/generated/PROJECT_INDEX.jsonl"],
            "reviewer": "",
            "reviewer_notes": "",
            "risk_tier": risk_tier,
            "second_review_status": "pending" if risk_tier == "high" else "not_required",
            "project_index_present": project_index_present,
            "project_index_hash_matches": project_index_hash_matches,
            "project_index_reconciliation": project_index_reconciliation,
            "verification_obligations": verification_obligations,
            "verified_obligations": [],
        }
        previous = existing_rows.get(rel_path)
        if previous and previous.get("content_sha256") == content_hash:
            for field in PRESERVED_REVIEW_FIELDS:
                if field in previous:
                    row[field] = previous[field]
        elif previous:
            row["reviewer_notes"] = "Content changed after the prior ledger review; terminal review evidence was reset."
        rows.append(row)
    return rows


def jsonl_text(rows: Iterable[Mapping[str, Any]]) -> str:
    return "".join(json.dumps(dict(row), ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n" for row in rows)


def stage_bytes(path: Path, payload: bytes, *, label: str) -> Path:
    """Create and durably flush a same-directory staging file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.{label}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return temp_path
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, content: str) -> None:
    """Replace one text artifact only after its complete payload is durable."""

    temp_path = stage_bytes(path, content.encode("utf-8"), label="new")
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def atomic_write_text_set(outputs: Sequence[tuple[Path, str]]) -> None:
    """Publish a text-artifact set with best-effort rollback on replacement failure."""

    items = list(outputs)
    destinations = [path for path, _content in items]
    if len(destinations) != len(set(destinations)):
        raise ValueError("artifact transaction contains duplicate destinations")
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path | None] = {}
    replaced: list[Path] = []
    try:
        for path, content in items:
            staged[path] = stage_bytes(path, content.encode("utf-8"), label="new")
        for path in destinations:
            backups[path] = stage_bytes(path, path.read_bytes(), label="backup") if path.is_file() else None
        for path in destinations:
            os.replace(staged[path], path)
            replaced.append(path)
    except BaseException as exc:
        rollback_errors: list[str] = []
        for path in reversed(replaced):
            backup = backups.get(path)
            try:
                if backup is None:
                    path.unlink(missing_ok=True)
                else:
                    os.replace(backup, path)
            except BaseException as rollback_exc:  # pragma: no cover - catastrophic filesystem failure
                rollback_errors.append(f"{path}: {rollback_exc}")
        if rollback_errors:
            raise RuntimeError(
                f"artifact publication failed ({exc}); rollback also failed: " + "; ".join(rollback_errors)
            ) from exc
        raise
    finally:
        for temp_path in [*staged.values(), *(path for path in backups.values() if path is not None)]:
            temp_path.unlink(missing_ok=True)


def load_error_fragments(output_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for fragment in sorted((output_dir / "workers").glob("*-errors.jsonl"), key=lambda path: path.name.casefold()):
        with fragment.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{fragment.name}:{line_number}: invalid JSON: {exc}") from exc
                record["source_fragment"] = fragment.relative_to(output_dir).as_posix()
                records.append(record)
    return records


def load_review_fragments(output_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    workers_dir = output_dir / "workers"
    fragments = set(workers_dir.glob("worker-*-review.jsonl"))
    legacy_prior_review = workers_dir / "prior-production-audit-review.jsonl"
    if legacy_prior_review.is_file():
        fragments.add(legacy_prior_review)
    for fragment in sorted(fragments, key=lambda path: path.name.casefold()):
        with fragment.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{fragment.name}:{line_number}: invalid JSON: {exc}") from exc
                record["source_fragment"] = fragment.relative_to(output_dir).as_posix()
                records.append(record)
    return records


def load_second_review_attestations(output_dir: Path) -> list[dict[str, Any]]:
    """Load distinct-review evidence without treating it as a first-pass override."""

    records: list[dict[str, Any]] = []
    pattern = "worker-*-independent-attestation.jsonl"
    for fragment in sorted((output_dir / "workers").glob(pattern), key=lambda path: path.name.casefold()):
        with fragment.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{fragment.name}:{line_number}: invalid JSON: {exc}") from exc
                record["source_fragment"] = fragment.relative_to(output_dir).as_posix()
                records.append(record)
    return records


def load_finding_fragments(output_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for fragment in sorted((output_dir / "workers").glob("*-findings.jsonl"), key=lambda path: path.name.casefold()):
        with fragment.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{fragment.name}:{line_number}: invalid JSON: {exc}") from exc
                record["source_fragment"] = fragment.relative_to(output_dir).as_posix()
                records.append(record)
    return records


def normalized_semantic_text(value: Any) -> str:
    return " ".join(str(value).casefold().split())


def is_historical_finding_id(value: str) -> bool:
    return value in LEGACY_EXTERNAL_FINDING_IDS or value.startswith(HISTORICAL_FINDING_PREFIXES)


def finding_root_cause_fingerprint(record: Mapping[str, Any]) -> str:
    locations = record.get("locations")
    primary = locations[0] if isinstance(locations, list) and locations and isinstance(locations[0], dict) else {}
    primary_path_value = str(primary.get("path", ""))
    try:
        primary_path = strict_repository_relative_path(primary_path_value)
    except ValueError:
        primary_path = canonical_path(primary_path_value)
    identity = {
        "category": normalized_semantic_text(record.get("category", "")),
        "expected_invariant": normalized_semantic_text(record.get("expected_invariant", "")),
        "root_cause": normalized_semantic_text(record.get("root_cause", "")),
        "primary_path": primary_path.casefold(),
        "primary_symbol": normalized_semantic_text(primary.get("symbol", "")),
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def finding_record_findings(
    records: Sequence[Mapping[str, Any]],
    *,
    root: Path | None = None,
) -> list[str]:
    findings: list[str] = []
    root_blobs = git_blob_map(root=root) if root is not None and (root / ".git").exists() else {}
    tracked_spellings = {path.casefold(): path for path in root_blobs}
    seen_ids: set[str] = set()
    known_ids = {str(record.get("id", "")).strip() for record in records if str(record.get("id", "")).strip()}
    fingerprints: dict[str, str] = {}
    for record in records:
        finding_id = str(record.get("id", "")).strip()
        missing = REQUIRED_FINDING_FIELDS.difference(record)
        if missing:
            findings.append(f"{finding_id or '<missing-id>'}: missing finding fields: {', '.join(sorted(missing))}")
        if not finding_id:
            findings.append("finding record has no id")
        elif finding_id in seen_ids:
            findings.append(f"duplicate finding id: {finding_id}")
        seen_ids.add(finding_id)
        if record.get("severity") not in ALLOWED_FINDING_SEVERITIES:
            findings.append(f"{finding_id}: invalid severity {record.get('severity')!r}")
        if record.get("confidence") not in ALLOWED_FINDING_CONFIDENCE and record.get("confidence") not in FINDING_CONFIDENCE_ALIASES:
            findings.append(f"{finding_id}: invalid confidence {record.get('confidence')!r}")
        if record.get("disposition") not in ALLOWED_FINDING_DISPOSITIONS and record.get("disposition") not in FINDING_DISPOSITION_ALIASES:
            findings.append(f"{finding_id}: invalid disposition {record.get('disposition')!r}")
        semantic_fields = (
            "category",
            "title",
            "observed_behavior",
            "expected_invariant",
            "root_cause",
            "failure_scenario",
            "safeguard_gap",
            "recommended_remediation",
            "remediation_risk",
            "validation_rung",
            "prior_audit_relationship",
        )
        for field in semantic_fields:
            if not isinstance(record.get(field), str) or not str(record.get(field)).strip():
                findings.append(f"{finding_id}: {field} must be a nonempty string")
        safeguards = record.get("existing_safeguards")
        safeguards_are_valid = isinstance(safeguards, str) and bool(safeguards.strip())
        if isinstance(safeguards, list):
            safeguards_are_valid = bool(safeguards) and all(isinstance(value, str) and value.strip() for value in safeguards)
        if not safeguards_are_valid:
            findings.append(f"{finding_id}: existing_safeguards must be a nonempty string or string array")
        locations = record.get("locations")
        if not isinstance(locations, list) or not locations:
            findings.append(f"{finding_id}: locations must be a nonempty array")
        else:
            for location in locations:
                if not isinstance(location, dict) or not location.get("path") or not location.get("start_line"):
                    findings.append(f"{finding_id}: every location needs path and start_line")
                    continue
                raw_location_path = str(location["path"])
                location_path = canonical_path(raw_location_path)
                try:
                    if root is None:
                        location_path = strict_repository_relative_path(raw_location_path)
                        absolute = None
                    else:
                        lexical_location = strict_repository_relative_path(raw_location_path)
                        tracked_location = tracked_spellings.get(lexical_location.casefold())
                        if tracked_location and root_blobs[tracked_location][0] in {"120000", "160000"}:
                            location_path = tracked_location
                            absolute = root.resolve() / PurePosixPath(location_path)
                        else:
                            location_path, absolute = resolved_repository_path(
                                root,
                                tracked_location or lexical_location,
                            )
                except ValueError as exc:
                    findings.append(f"{finding_id}: invalid finding location path {raw_location_path!r}: {exc}")
                    continue
                start_line = location.get("start_line")
                end_line = location.get("end_line", start_line)
                if (
                    isinstance(start_line, bool)
                    or not isinstance(start_line, int)
                    or start_line < 1
                    or isinstance(end_line, bool)
                    or not isinstance(end_line, int)
                    or end_line < start_line
                ):
                    findings.append(f"{finding_id}: invalid location range for {location_path}")
                    continue
                if root is not None:
                    assert absolute is not None
                    mode, location_blob_hash = root_blobs.get(location_path, ("", ""))
                    if mode == "120000":
                        raw = git_blob_bytes(location_blob_hash, root=root)
                        total_lines = text_line_counts_bytes(raw)[0]
                    elif mode == "160000":
                        total_lines = None
                    elif absolute.is_file():
                        if is_probably_text(absolute, location_path):
                            total_lines, _source_lines = text_line_counts(absolute)
                        else:
                            total_lines = None
                    else:
                        if location_path in root_blobs:
                            _mode, location_blob_hash = root_blobs[location_path]
                            raw = git_blob_bytes(location_blob_hash, root=root)
                            total_lines = (
                                text_line_counts_bytes(raw)[0]
                                if is_probably_text_bytes(raw, location_path)
                                else None
                            )
                        else:
                            findings.append(f"{finding_id}: finding location is not a current file: {location_path}")
                            total_lines = None
                    if total_lines is not None and end_line > total_lines:
                        findings.append(
                            f"{finding_id}: location {location_path}:{start_line}-{end_line} exceeds {total_lines} lines"
                        )
        for field in ("evidence", "affected_flows", "tests_present", "tests_missing", "related_finding_ids"):
            if not isinstance(record.get(field), list):
                findings.append(f"{finding_id}: {field} must be an array")
        for field in ("evidence", "affected_flows"):
            value = record.get(field)
            if isinstance(value, list) and not value:
                findings.append(f"{finding_id}: {field} must not be empty")
        related = record.get("related_finding_ids")
        if isinstance(related, list):
            if any(not isinstance(value, str) or not value.strip() for value in related):
                findings.append(f"{finding_id}: related_finding_ids must contain nonempty strings")
            for related_id in related:
                if not isinstance(related_id, str) or not related_id.strip():
                    continue
                if related_id == finding_id:
                    findings.append(f"{finding_id}: finding cannot relate to itself")
                elif related_id not in known_ids and not is_historical_finding_id(related_id):
                    findings.append(f"{finding_id}: related finding does not exist: {related_id}")
        historical_related = record.get("historical_related_finding_ids", [])
        if not isinstance(historical_related, list) or any(
            not isinstance(value, str) or not value.strip() or not is_historical_finding_id(value)
            for value in historical_related
        ):
            findings.append(f"{finding_id}: historical_related_finding_ids contains an invalid external ID")
        elif len(historical_related) != len(set(historical_related)):
            findings.append(f"{finding_id}: historical_related_finding_ids contains duplicates")
        if not missing and finding_id:
            fingerprint = finding_root_cause_fingerprint(record)
            recorded_fingerprint = record.get("root_cause_fingerprint")
            if recorded_fingerprint is not None and recorded_fingerprint != fingerprint:
                findings.append(f"{finding_id}: stored root-cause fingerprint is stale")
            prior_id = fingerprints.get(fingerprint)
            if prior_id and prior_id != finding_id:
                findings.append(f"duplicate root-cause fingerprint: {prior_id}, {finding_id}")
            else:
                fingerprints[fingerprint] = finding_id
    return findings


def findings_markdown(records: Sequence[Mapping[str, Any]]) -> str:
    severities = Counter(str(record.get("severity", "unknown")) for record in records)
    dispositions = Counter(str(record.get("disposition", "unknown")) for record in records)
    lines = [
        "# Findings Register",
        "",
        "Findings are exact-deduplicated by a deterministic root-cause fingerprint over category, invariant, root cause, and primary location/symbol. Ambiguous near-duplicates require coordinator review. Exact locations, scenarios, safeguards, tests, remediation, validation, and fragment provenance are retained in `FINDINGS.jsonl`.",
        "",
        f"- Findings: **{len(records)}**",
        "- Severity: " + ", ".join(f"{key}={value}" for key, value in sorted(severities.items())),
        "- Disposition: " + ", ".join(f"{key}={value}" for key, value in sorted(dispositions.items())),
        "",
        "| ID | Severity | Confidence | Disposition | Category | Primary location | Title |",
        "|---|---|---|---|---|---|---|",
    ]
    for record in records:
        location = record.get("locations", [{}])[0]
        location_text = f"`{location.get('path', '')}:{location.get('start_line', '')}`"
        title = str(record.get("title", "")).replace("|", "\\|")
        lines.append(
            f"| `{record.get('id', '')}` | {record.get('severity', '')} | {record.get('confidence', '')} | "
            f"{record.get('disposition', '')} | {record.get('category', '')} | {location_text} | {title} |"
        )
    lines.append("")
    return "\n".join(lines)


def prepare_finding_records(output_dir: Path, *, root: Path = REPO_ROOT) -> tuple[list[dict[str, Any]], list[str]]:
    source_records = load_finding_fragments(output_dir)
    findings = finding_record_findings(source_records, root=root)
    if findings:
        return [], findings
    records = [dict(record) for record in source_records]
    known_ids = {str(record["id"]) for record in records}
    for record in records:
        source_confidence = str(record.get("confidence", ""))
        if source_confidence in FINDING_CONFIDENCE_ALIASES:
            record["source_confidence"] = source_confidence
            record["confidence"] = FINDING_CONFIDENCE_ALIASES[source_confidence]
        source_disposition = str(record.get("disposition", ""))
        if source_disposition in FINDING_DISPOSITION_ALIASES:
            record["source_disposition"] = source_disposition
            record["disposition"] = FINDING_DISPOSITION_ALIASES[source_disposition]
        related_ids = list(record.get("related_finding_ids", []))
        record["related_finding_ids"] = [value for value in related_ids if value in known_ids]
        historical_ids = sorted(
            {
                *record.get("historical_related_finding_ids", []),
                *(value for value in related_ids if value not in known_ids),
            },
            key=lambda value: (str(value).casefold(), str(value)),
        )
        if historical_ids:
            record["historical_related_finding_ids"] = historical_ids
        record["root_cause_fingerprint"] = finding_root_cause_fingerprint(record)
    severity_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    records.sort(key=lambda record: (severity_rank[str(record["severity"])], str(record["id"]).casefold()))
    return records, []


def merge_finding_ledgers(output_dir: Path, *, root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    records, findings = prepare_finding_records(output_dir, root=root)
    if findings:
        raise ValueError("Invalid finding-ledger fragments:\n- " + "\n- ".join(findings))
    atomic_write_text_set(
        [
            (output_dir / "FINDINGS.jsonl", jsonl_text(records)),
            (output_dir / "FINDINGS_REGISTER.md", findings_markdown(records)),
        ]
    )
    return records


def review_fragment_findings(
    records: Sequence[Mapping[str, Any]],
    *,
    baseline_rows: Mapping[str, Mapping[str, Any]],
    valid_finding_ids: set[str] | None = None,
    valid_error_ids: set[str] | None = None,
    finding_ids_by_location: Mapping[str, set[str]] | None = None,
) -> list[str]:
    findings: list[str] = []
    seen_paths: set[str] = set()
    for record in records:
        path = canonical_path(str(record.get("path", "")))
        missing = REQUIRED_REVIEW_FRAGMENT_FIELDS.difference(record)
        if missing:
            findings.append(f"{path or '<missing-path>'}: missing review fields: {', '.join(sorted(missing))}")
        if not path:
            findings.append("review fragment row has no path")
            continue
        if path in seen_paths:
            findings.append(f"duplicate reviewed path: {path}")
        seen_paths.add(path)
        baseline = baseline_rows.get(path)
        if baseline is None:
            findings.append(f"reviewed path is outside the coverage matrix: {path}")
            continue
        if record.get("assigned_worker") != baseline.get("assigned_worker"):
            findings.append(
                f"{path}: fragment worker {record.get('assigned_worker')!r} does not own baseline slice "
                f"{baseline.get('assigned_worker')!r}"
            )
        if record.get("content_sha256") != baseline.get("content_sha256"):
            findings.append(f"{path}: review fragment hash does not match the coverage baseline")
        finding_ids = record.get("finding_ids")
        if isinstance(finding_ids, list):
            if len(finding_ids) != len(set(finding_ids)):
                findings.append(f"{path}: review fragment finding_ids contains duplicates")
            if valid_finding_ids is not None:
                for finding_id in finding_ids:
                    if finding_id not in valid_finding_ids:
                        findings.append(f"{path}: review fragment finding does not exist: {finding_id}")
            if record.get("review_status") == "line_reviewed_no_findings" and finding_ids:
                findings.append(f"{path}: no-findings review status has finding IDs")
            if record.get("review_status") == "line_reviewed_with_findings" and not finding_ids:
                findings.append(f"{path}: with-findings review status has no finding IDs")
            if finding_ids_by_location is not None:
                expected_finding_ids = finding_ids_by_location.get(path.casefold(), set())
                actual_finding_ids = set(finding_ids)
                missing_finding_ids = sorted(expected_finding_ids - actual_finding_ids, key=str.casefold)
                unexpected_finding_ids = sorted(actual_finding_ids - expected_finding_ids, key=str.casefold)
                if missing_finding_ids:
                    findings.append(
                        f"{path}: review fragment omits current path-local findings: "
                        + ", ".join(missing_finding_ids)
                    )
                if unexpected_finding_ids:
                    findings.append(
                        f"{path}: review fragment claims findings not located on this path: "
                        + ", ".join(unexpected_finding_ids)
                    )
        error_ids = record.get("error_ids")
        if isinstance(error_ids, list):
            if len(error_ids) != len(set(error_ids)):
                findings.append(f"{path}: review fragment error_ids contains duplicates")
            if valid_error_ids is not None:
                for error_id in error_ids:
                    if error_id not in valid_error_ids:
                        findings.append(f"{path}: review fragment error does not exist: {error_id}")
        unknown_fields = set(record).difference(REQUIRED_REVIEW_FRAGMENT_FIELDS).difference(REVIEW_OVERRIDE_FIELDS).difference(
            {"source_fragment"}
        )
        if unknown_fields:
            findings.append(f"{path}: unsupported review override fields: {', '.join(sorted(unknown_fields))}")
    return findings


def is_canonical_reviewer_identity(value: Any) -> bool:
    text = str(value).strip()
    tail = text.removeprefix("/root/")
    return (
        text.startswith("/root/")
        and bool(tail)
        and not text.endswith("/")
        and "//" not in text
        and text == text.casefold()
        and all(character.isalnum() or character in {"_", "/"} for character in tail)
    )


def second_review_attestation_findings(
    records: Sequence[Mapping[str, Any]],
    *,
    baseline_rows: Mapping[str, Mapping[str, Any]],
    first_review_records: Sequence[Mapping[str, Any]],
    valid_finding_ids: set[str] | None = None,
    valid_error_ids: set[str] | None = None,
    finding_dispositions: Mapping[str, str] | None = None,
    finding_location_paths: Mapping[str, set[str]] | None = None,
) -> list[str]:
    """Validate independent reviewer identity, current hashes, and dispositions."""

    findings: list[str] = []
    seen_paths: set[str] = set()
    first_reviews = {canonical_path(str(record.get("path", ""))): record for record in first_review_records}
    for record in records:
        raw_path = str(record.get("path", ""))
        try:
            path = strict_repository_relative_path(raw_path)
        except ValueError as exc:
            findings.append(f"{raw_path or '<missing-path>'}: invalid second-review path: {exc}")
            continue
        missing = REQUIRED_SECOND_REVIEW_ATTESTATION_FIELDS.difference(record)
        if missing:
            findings.append(f"{path}: missing second-review fields: {', '.join(sorted(missing))}")
        if path in seen_paths:
            findings.append(f"duplicate independent-review attestation path: {path}")
        seen_paths.add(path)
        baseline = baseline_rows.get(path)
        first_review = first_reviews.get(path)
        if baseline is None:
            findings.append(f"{path}: independent attestation is outside the coverage matrix")
            continue
        if first_review is None:
            findings.append(f"{path}: independent attestation has no current first-pass review fragment")
            continue
        if record.get("content_sha256") != baseline.get("content_sha256"):
            findings.append(f"{path}: independent attestation hash does not match current coverage content")
        if record.get("assigned_worker") != baseline.get("assigned_worker"):
            findings.append(f"{path}: independent attestation worker does not match coverage ownership")
        if record.get("review_status") not in ACHIEVED_STATUSES:
            findings.append(f"{path}: independent attestation does not attest an achieved review status")
        if record.get("review_status") != first_review.get("review_status"):
            findings.append(f"{path}: independent and first-pass review statuses disagree")
        if record.get("second_review_status") != "complete":
            findings.append(f"{path}: independent attestation must have second_review_status='complete'")
        first_reviewer = str(record.get("first_reviewer", "")).strip()
        reviewer = str(record.get("reviewer", "")).strip()
        if first_reviewer != str(first_review.get("reviewer", "")).strip():
            findings.append(f"{path}: attested first reviewer does not match the first-pass fragment")
        if not is_canonical_reviewer_identity(first_reviewer):
            findings.append(f"{path}: first reviewer is not a canonical /root agent identity")
        if not is_canonical_reviewer_identity(reviewer):
            findings.append(f"{path}: independent reviewer is not a canonical /root agent identity")
        if first_reviewer.casefold() == reviewer.casefold():
            findings.append(f"{path}: first and independent reviewer identities are the same")
        for field in ("review_depth", "independence_basis", "reviewer_notes"):
            if not isinstance(record.get(field), str) or not str(record.get(field)).strip():
                findings.append(f"{path}: {field} must be a nonempty string")
        for field in ("reviewed_symbols_or_sections", "finding_ids", "error_ids", "evidence_commands"):
            values = record.get(field)
            if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values):
                findings.append(f"{path}: {field} must be an array of nonempty strings")
        for field in ("reviewed_symbols_or_sections", "evidence_commands"):
            if isinstance(record.get(field), list) and not record.get(field):
                findings.append(f"{path}: {field} must not be empty")
        finding_ids = record.get("finding_ids", [])
        first_finding_ids = first_review.get("finding_ids", [])
        if isinstance(finding_ids, list) and isinstance(first_finding_ids, list):
            if set(finding_ids) != set(first_finding_ids):
                findings.append(f"{path}: independent and first-pass finding ID sets disagree")
            if len(finding_ids) != len(set(finding_ids)):
                findings.append(f"{path}: independent finding_ids contains duplicates")
        dispositions = record.get("finding_dispositions")
        if not isinstance(dispositions, dict):
            findings.append(f"{path}: finding_dispositions must be an object")
        elif isinstance(finding_ids, list):
            if set(dispositions) != set(finding_ids):
                findings.append(f"{path}: finding_dispositions keys must exactly equal finding_ids")
            for finding_id, disposition in dispositions.items():
                if disposition not in ALLOWED_FINDING_DISPOSITIONS:
                    findings.append(f"{path}: invalid independent disposition for {finding_id}: {disposition!r}")
                if finding_dispositions is not None and finding_dispositions.get(finding_id) != disposition:
                    findings.append(f"{path}: independent disposition disagrees with central finding {finding_id}")
        if valid_finding_ids is not None and isinstance(finding_ids, list):
            for finding_id in finding_ids:
                if finding_id not in valid_finding_ids:
                    findings.append(f"{path}: independently reviewed finding does not exist: {finding_id}")
                elif finding_location_paths is not None and path.casefold() not in {
                    location_path.casefold()
                    for location_path in finding_location_paths.get(finding_id, set())
                }:
                    findings.append(f"{path}: independently reviewed finding is not located on the attested path: {finding_id}")
        error_ids = record.get("error_ids", [])
        if valid_error_ids is not None and isinstance(error_ids, list):
            for error_id in error_ids:
                if error_id not in valid_error_ids:
                    findings.append(f"{path}: independent-review error does not exist: {error_id}")
    return findings


def independent_review_completion_findings(
    rows: Sequence[Mapping[str, Any]],
    finding_records: Sequence[Mapping[str, Any]],
    attestations: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Require independent evidence for high-risk files and every current P0/P1 finding."""

    findings: list[str] = []
    attested_paths = {canonical_path(str(record.get("path", ""))) for record in attestations}
    required_paths = {
        canonical_path(str(row.get("path", "")))
        for row in rows
        if row.get("risk_tier") == "high" and row.get("review_status") in ACHIEVED_STATUSES
    }
    missing_paths = sorted(required_paths - attested_paths, key=str.casefold)
    if missing_paths:
        findings.append("high-risk achieved rows lack independent attestations: " + ", ".join(missing_paths))
    attestations_by_path = {
        canonical_path(str(record.get("path", ""))).casefold(): record
        for record in attestations
    }
    missing_finding_ids: list[str] = []
    for finding_record in finding_records:
        if finding_record.get("severity") not in {"P0", "P1"}:
            continue
        finding_id = str(finding_record.get("id"))
        location_paths = {
            canonical_path(str(location.get("path", ""))).casefold()
            for location in finding_record.get("locations", [])
            if isinstance(location, Mapping) and location.get("path")
        }
        covered = any(
            finding_id in attestation.get("finding_ids", [])
            for path, attestation in attestations_by_path.items()
            if path in location_paths
        )
        if not covered:
            missing_finding_ids.append(finding_id)
    missing_finding_ids.sort(key=str.casefold)
    if missing_finding_ids:
        findings.append("P0/P1 findings lack independent disposition attestations: " + ", ".join(missing_finding_ids))
    return findings


def prepare_review_rows(output_dir: Path, *, root: Path = REPO_ROOT) -> tuple[list[dict[str, Any]], list[str]]:
    """Rebuild the current inventory and deterministically apply every review fragment."""

    project_records = load_project_index(root / "docs" / "generated" / "PROJECT_INDEX.jsonl")
    rows = build_rows(
        root=root,
        output_dir=output_dir,
        project_records=project_records,
        existing_rows={},
    )
    expected, tracked_output_paths = expected_coverage_paths(output_dir, root=root)
    findings = validation_findings(rows, expected_paths=expected)
    if tracked_output_paths:
        findings.append(
            "tracked audit output files require a non-self-referential freeze ledger: "
            + ", ".join(sorted(tracked_output_paths, key=str.casefold))
        )
    findings.extend(current_content_findings(rows, expected_paths=expected, root=root))
    baseline = {canonical_path(row["path"]): row for row in rows}
    finding_records, finding_fragment_findings = prepare_finding_records(output_dir, root=root)
    findings.extend(f"finding fragment: {value}" for value in finding_fragment_findings)
    valid_finding_ids = {str(record["id"]) for record in finding_records}
    error_records, error_fragment_findings = prepare_error_records(
        output_dir,
        valid_finding_ids=valid_finding_ids,
    )
    findings.extend(f"error fragment: {value}" for value in error_fragment_findings)
    valid_error_ids = {str(record["id"]) for record in error_records}
    finding_dispositions = {
        str(record["id"]): str(record["disposition"])
        for record in finding_records
    }
    finding_location_paths = {
        str(record["id"]): {
            canonical_path(str(location["path"])).casefold()
            for location in record.get("locations", [])
            if isinstance(location, Mapping) and location.get("path")
        }
        for record in finding_records
    }
    finding_ids_by_location: dict[str, set[str]] = {}
    for finding_id, location_paths in finding_location_paths.items():
        for location_path in location_paths:
            finding_ids_by_location.setdefault(location_path, set()).add(finding_id)
    records = load_review_fragments(output_dir)
    fragment_findings = review_fragment_findings(
        records,
        baseline_rows=baseline,
        valid_finding_ids=valid_finding_ids if not finding_fragment_findings else None,
        valid_error_ids=valid_error_ids if not error_fragment_findings else None,
        finding_ids_by_location=finding_ids_by_location if not finding_fragment_findings else None,
    )
    findings.extend(f"review fragment: {value}" for value in fragment_findings)
    if findings:
        return rows, findings
    for record in records:
        row = baseline[canonical_path(record["path"])]
        for field in REVIEW_OVERRIDE_FIELDS:
            if field != "second_review_status" and field in record:
                row[field] = record[field]
    attestations = load_second_review_attestations(output_dir)
    attestation_findings = second_review_attestation_findings(
        attestations,
        baseline_rows=baseline,
        first_review_records=records,
        valid_finding_ids=valid_finding_ids if not finding_fragment_findings else None,
        valid_error_ids=valid_error_ids if not error_fragment_findings else None,
        finding_dispositions=finding_dispositions if not finding_fragment_findings else None,
        finding_location_paths=finding_location_paths if not finding_fragment_findings else None,
    )
    findings.extend(f"independent attestation: {value}" for value in attestation_findings)
    if not attestation_findings:
        for attestation in attestations:
            baseline[canonical_path(attestation["path"])]["second_review_status"] = "complete"
    findings.extend(validation_findings(rows, expected_paths=expected))
    findings.extend(current_content_findings(rows, expected_paths=expected, root=root))
    return rows, findings


def merge_review_ledgers(output_dir: Path, *, root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    matrix_path = output_dir / "COVERAGE_MATRIX.jsonl"
    current_rows = load_rows(matrix_path)
    expected, tracked_output_paths = expected_coverage_paths(output_dir, root=root)
    baseline_findings = validation_findings(current_rows, expected_paths=expected)
    if tracked_output_paths:
        baseline_findings.append(
            "tracked audit output files require a non-self-referential freeze ledger: "
            + ", ".join(sorted(tracked_output_paths, key=str.casefold))
        )
    if baseline_findings:
        raise ValueError("Coverage baseline violates current universe invariants:\n- " + "\n- ".join(baseline_findings))
    freshness_findings = current_content_findings(current_rows, expected_paths=expected, root=root)
    if freshness_findings:
        raise ValueError("Coverage baseline is stale; review merge refused:\n- " + "\n- ".join(freshness_findings))
    rows, findings = prepare_review_rows(output_dir, root=root)
    if findings:
        raise ValueError("Current review evidence cannot be merged:\n- " + "\n- ".join(findings))
    freshness_findings = current_content_findings(rows, expected_paths=expected, root=root)
    if freshness_findings:
        raise ValueError("Covered content changed during review merge; no outputs written:\n- " + "\n- ".join(freshness_findings))
    branch = run_git(["branch", "--show-current"], root=root).decode("utf-8").strip()
    head = run_git(["rev-parse", "HEAD"], root=root).decode("ascii").strip()
    atomic_write_text_set(
        [
            (matrix_path, jsonl_text(rows)),
            (output_dir / "COVERAGE_MATRIX.csv", csv_text(rows)),
            (output_dir / "BASELINE.md", baseline_markdown(rows, head=head, branch=branch)),
        ]
    )
    return rows


def error_record_findings(
    records: Sequence[Mapping[str, Any]],
    *,
    valid_finding_ids: set[str] | None = None,
) -> list[str]:
    findings: list[str] = []
    seen_ids: set[str] = set()
    for record in records:
        record_id = str(record.get("id", "")).strip()
        missing = REQUIRED_ERROR_FIELDS.difference(record)
        if missing:
            findings.append(f"{record_id or '<missing-id>'}: missing error fields: {', '.join(sorted(missing))}")
        if not record_id:
            findings.append("error record has no id")
        elif record_id in seen_ids:
            findings.append(f"duplicate error id: {record_id}")
        seen_ids.add(record_id)
        for field in (
            "timestamp",
            "command",
            "working_directory",
            "output_summary",
            "phase",
            "classification",
            "reproduction_status",
            "retry_result",
            "disposition",
        ):
            if not isinstance(record.get(field), str) or not str(record.get(field)).strip():
                findings.append(f"{record_id}: {field} must be a nonempty string")
        timestamp = record.get("timestamp")
        if isinstance(timestamp, str) and timestamp.strip():
            try:
                datetime.fromisoformat(timestamp.strip().replace("Z", "+00:00"))
            except ValueError:
                if not (len(timestamp) == 34 and timestamp[4] == "-" and timestamp[7] == "-" and timestamp[10:] == "; exact time not emitted"):
                    findings.append(f"{record_id}: timestamp is neither ISO-8601 nor an explicit date-only precision marker")
        classification = record.get("classification")
        if classification not in ALLOWED_ERROR_CLASSIFICATIONS and classification not in LEGACY_ERROR_CLASSIFICATION_MAP:
            findings.append(f"{record_id}: invalid classification {record.get('classification')!r}")
        source_classification = record.get("source_classification")
        if source_classification is not None and LEGACY_ERROR_CLASSIFICATION_MAP.get(str(source_classification)) != classification:
            findings.append(f"{record_id}: source_classification does not map to canonical classification")
        exit_code = record.get("exit_code")
        if exit_code is not None and (isinstance(exit_code, bool) or not isinstance(exit_code, int)):
            findings.append(f"{record_id}: exit_code must be an integer or null")
        linked_ids = record.get("linked_finding_ids")
        if not isinstance(linked_ids, list):
            findings.append(f"{record_id}: linked_finding_ids must be an array")
        else:
            linked_ids_are_strings = all(isinstance(value, str) and value.strip() for value in linked_ids)
            if not linked_ids_are_strings:
                findings.append(f"{record_id}: linked_finding_ids must contain nonempty strings")
            if linked_ids_are_strings and len(linked_ids) != len(set(linked_ids)):
                findings.append(f"{record_id}: linked_finding_ids contains duplicates")
            if valid_finding_ids is not None:
                for finding_id in linked_ids:
                    if (
                        isinstance(finding_id, str)
                        and finding_id.strip()
                        and finding_id not in valid_finding_ids
                        and not is_historical_finding_id(finding_id)
                    ):
                        findings.append(f"{record_id}: linked finding does not exist: {finding_id}")
        historical_ids = record.get("historical_linked_finding_ids", [])
        if not isinstance(historical_ids, list) or any(
            not isinstance(value, str) or not value.strip() or not is_historical_finding_id(value)
            for value in historical_ids
        ):
            findings.append(f"{record_id}: historical_linked_finding_ids contains an invalid external ID")
        elif len(historical_ids) != len(set(historical_ids)):
            findings.append(f"{record_id}: historical_linked_finding_ids contains duplicates")
        if not isinstance(record.get("coverage_blocked"), bool):
            findings.append(f"{record_id}: coverage_blocked must be boolean")
    return findings


def error_ledger_markdown(records: Sequence[Mapping[str, Any]]) -> str:
    classifications = Counter(str(record.get("classification", "unknown")) for record in records)
    blocked = sum(bool(record.get("coverage_blocked")) for record in records)
    lines = [
        "# Audit Error Ledger",
        "",
        "Every nonzero audit command, parser/analysis error, confidence-affecting warning, missing dependency, output truncation, skip/downshift, and external-evidence gap is recorded here. Expected negative-path results remain evidence; they are not product defects unless linked to a confirmed finding.",
        "",
        f"- Recorded events: **{len(records)}**",
        f"- Events currently blocking some coverage: **{blocked}**",
        "",
        "## Classification counts",
        "",
        "| Classification | Events |",
        "|---|---:|",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in sorted(classifications.items()))
    lines.extend(
        [
            "",
            "## Event index",
            "",
            "| ID | Phase | Exit | Classification | Coverage blocked | Disposition |",
            "|---|---|---:|---|---|---|",
        ]
    )
    for record in records:
        exit_code = record.get("exit_code")
        exit_text = "n/a" if exit_code is None else str(exit_code)
        disposition = str(record.get("disposition", "")).replace("|", "\\|")
        lines.append(
            f"| `{record.get('id', '')}` | {record.get('phase', '')} | {exit_text} | "
            f"{record.get('classification', '')} | {'yes' if record.get('coverage_blocked') else 'no'} | {disposition} |"
        )
    lines.extend(
        [
            "",
            "Full commands, decisive output, retry results, and source-fragment provenance are in `ERROR_LEDGER.jsonl`.",
            "",
        ]
    )
    return "\n".join(lines)


def prepare_error_records(
    output_dir: Path,
    *,
    valid_finding_ids: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    records = load_error_fragments(output_dir)
    findings = error_record_findings(records, valid_finding_ids=valid_finding_ids)
    if findings:
        return [], findings
    records = [dict(record) for record in records]
    for record in records:
        source_classification = str(record.get("classification", ""))
        if source_classification in LEGACY_ERROR_CLASSIFICATION_MAP:
            record["source_classification"] = source_classification
            record["classification"] = LEGACY_ERROR_CLASSIFICATION_MAP[source_classification]
        linked_ids = list(record.get("linked_finding_ids", []))
        record["linked_finding_ids"] = [value for value in linked_ids if value in valid_finding_ids]
        historical_ids = sorted(
            {
                *record.get("historical_linked_finding_ids", []),
                *(value for value in linked_ids if value not in valid_finding_ids),
            },
            key=lambda value: (str(value).casefold(), str(value)),
        )
        if historical_ids:
            record["historical_linked_finding_ids"] = historical_ids
    records.sort(key=lambda record: str(record["id"]).casefold())
    return records, []


def merge_error_ledgers(output_dir: Path, *, root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    finding_records, finding_findings = prepare_finding_records(output_dir, root=root)
    if finding_findings:
        raise ValueError("Cannot validate error links because finding fragments are invalid:\n- " + "\n- ".join(finding_findings))
    valid_finding_ids = {str(record["id"]) for record in finding_records}
    records, findings = prepare_error_records(output_dir, valid_finding_ids=valid_finding_ids)
    if findings:
        raise ValueError("Invalid error-ledger fragments:\n- " + "\n- ".join(findings))
    atomic_write_text_set(
        [
            (output_dir / "ERROR_LEDGER.jsonl", jsonl_text(records)),
            (output_dir / "ERROR_LEDGER.md", error_ledger_markdown(records)),
        ]
    )
    return records


def csv_text(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return ""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=sorted(rows[0], key=lambda value: (value.casefold(), value)), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: json.dumps(value, ensure_ascii=False, separators=(",", ":")) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            }
        )
    return output.getvalue()


def baseline_markdown(rows: Sequence[Mapping[str, Any]], *, head: str, branch: str) -> str:
    categories = Counter(str(row["file_category"]) for row in rows)
    types = Counter(str(row["language_or_type"]) for row in rows)
    workers = Counter(str(row["assigned_worker"]) for row in rows)
    tracked_count = sum(bool(row["is_tracked"]) for row in rows)
    index_blob_count = sum(
        row.get("content_source") == "git_index_blob" and row.get("git_mode") != "120000"
        for row in rows
    )
    symlink_count = sum(row.get("git_mode") == "120000" for row in rows)
    gitlink_count = sum(row.get("git_mode") == "160000" for row in rows)
    total_lines = sum(int(row["total_lines"] or 0) for row in rows)
    source_lines = sum(int(row["source_lines"] or 0) for row in rows)
    indexed = sum(bool(row["project_index_present"]) for row in rows)
    achieved_count = sum(row.get("review_status") in ACHIEVED_STATUSES for row in rows)
    blocked_count = sum(row.get("review_status") == "blocked_with_reason" for row in rows)
    open_count = len(rows) - achieved_count - blocked_count
    lines = [
        "# Audit Baseline",
        "",
        "> Evidence snapshot only. Project authority remains with the canonical documentation and executable source.",
        "",
        f"- Branch: `{branch}`",
        f"- HEAD: `{head}`",
        f"- Files in ledger: **{len(rows)}**",
        f"- Git-tracked files: **{tracked_count}**",
        f"- Nonignored task-created files: **{len(rows) - tracked_count}**",
        f"- Tracked paths inventoried from stage-0 Git blobs because worktree files are absent: **{index_blob_count}**",
        f"- Git symlinks inventoried from link blobs: **{symlink_count}**",
        f"- Gitlinks inventoried from commit-object identities: **{gitlink_count}**",
        f"- Files represented in `PROJECT_INDEX.jsonl`: **{indexed}**",
        f"- Physical text lines inventoried: **{total_lines}**",
        f"- Nonblank text lines inventoried: **{source_lines}**",
        f"- Review/verification status: **achieved={achieved_count}; blocked={blocked_count}; open={open_count}**",
        "",
        "## File categories",
        "",
        "| Category | Files |",
        "|---|---:|",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in sorted(categories.items()))
    lines.extend(["", "## Language and type inventory", "", "| Type | Files |", "|---|---:|"])
    lines.extend(f"| `{name}` | {count} |" for name, count in types.most_common())
    lines.extend(["", "## Assigned review slices", "", "| Worker slice | Files |", "|---|---:|"])
    lines.extend(f"| `{name}` | {count} |" for name, count in sorted(workers.items()))
    lines.extend(
        [
            "",
            "## Counting semantics",
            "",
            "`total_lines` is the physical line count for decodable text. `source_lines` is the nonblank line count, not a claim of executable SLOC. `content_source` identifies whether the hashed bytes came from the worktree or an exact stage-0 Git blob; unavailable content is rejected. Binary files have null line counts. Inventory metadata does not constitute semantic review.",
            "",
        ]
    )
    return "\n".join(lines)


def validation_findings(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected_paths: set[str],
    require_complete: bool = False,
) -> list[str]:
    findings: list[str] = []
    missing_category_rules = ALLOWED_CATEGORIES.difference(CATEGORY_TERMINAL_STATUSES)
    extra_category_rules = set(CATEGORY_TERMINAL_STATUSES).difference(ALLOWED_CATEGORIES)
    if missing_category_rules or extra_category_rules:
        findings.append(
            "category/status compatibility table mismatch: "
            f"missing={sorted(missing_category_rules)}, extra={sorted(extra_category_rules)}"
        )
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        missing_fields = REQUIRED_ROW_FIELDS.difference(row)
        if missing_fields:
            findings.append(f"coverage row missing required fields: {', '.join(sorted(missing_fields))}")
        path = canonical_path(str(row.get("path", "")))
        if not path:
            findings.append("coverage row has no path")
            continue
        if path in seen:
            duplicates.add(path)
        seen.add(path)
        status = str(row.get("review_status", ""))
        if status not in ALLOWED_STATUSES:
            findings.append(f"{path}: invalid review_status {status!r}")
        category = str(row.get("file_category", ""))
        if category not in ALLOWED_CATEGORIES:
            findings.append(f"{path}: invalid file_category {category!r}")
        if row.get("schema_version") != SCHEMA_VERSION:
            findings.append(f"{path}: coverage schema version is not {SCHEMA_VERSION}")
        content_source = row.get("content_source")
        if content_source not in {"worktree", "git_index_blob", "git_index_gitlink"}:
            findings.append(f"{path}: invalid or unavailable content_source {content_source!r}")
        if content_source in {"git_index_blob", "git_index_gitlink"} and row.get("is_tracked") is not True:
            findings.append(f"{path}: untracked row cannot use a Git-index blob as its content source")
        if row.get("git_mode") == "120000" and content_source != "git_index_blob":
            findings.append(f"{path}: Git symlink must be inventoried from its index link blob")
        if row.get("git_mode") == "160000" and content_source != "git_index_gitlink":
            findings.append(f"{path}: Gitlink must be inventoried from its commit-object identity")
        if row.get("is_tracked") is True and row.get("git_mode") not in ALLOWED_GIT_INDEX_MODES:
            findings.append(f"{path}: tracked row has invalid Git index mode {row.get('git_mode')!r}")
        if row.get("is_tracked") is False and row.get("git_mode") not in {"", None}:
            findings.append(f"{path}: untracked row unexpectedly has Git index mode {row.get('git_mode')!r}")
        if require_complete and status not in ACHIEVED_STATUSES:
            if status == "blocked_with_reason":
                findings.append(f"{path}: review is blocked and does not satisfy achieved completion")
            else:
                findings.append(f"{path}: review is not achieved ({status})")
        compatible_statuses = CATEGORY_TERMINAL_STATUSES.get(category, frozenset())
        if status in ACHIEVED_STATUSES and status not in compatible_statuses:
            findings.append(f"{path}: {category or '<unknown category>'} has incompatible terminal status {status}")
        if status == "blocked_with_reason" and not str(row.get("reviewer_notes", "")).strip():
            findings.append(f"{path}: blocked status has no reason")
        if status in TERMINAL_STATUSES and not str(row.get("reviewer", "")).strip():
            findings.append(f"{path}: terminal review has no reviewer")
        if status in TERMINAL_STATUSES and row.get("review_depth") in {"", "inventory_only", None}:
            findings.append(f"{path}: terminal review has no semantic/verification depth")
        if status == "line_reviewed_with_findings" and not row.get("finding_ids"):
            findings.append(f"{path}: with-findings status has no finding IDs")
        if row.get("risk_tier") not in {"low", "medium", "high"}:
            findings.append(f"{path}: invalid risk_tier {row.get('risk_tier')!r}")
        if row.get("second_review_status") not in {"pending", "not_required", "complete"}:
            findings.append(f"{path}: invalid second_review_status {row.get('second_review_status')!r}")
        if (
            require_complete
            and row.get("risk_tier") == "high"
            and status in ACHIEVED_STATUSES
            and row.get("second_review_status") != "complete"
        ):
            findings.append(f"{path}: high-risk terminal review lacks independent second review")
        for flag in ("generated", "vendor", "archive", "binary", "runtime", "evidence_snapshot"):
            if not isinstance(row.get(flag), bool):
                findings.append(f"{path}: {flag} flag must be boolean")
        for field in (
            "reviewed_symbols_or_sections",
            "incoming_dependencies",
            "outgoing_dependencies",
            "api_routes",
            "commands",
            "invoked_tools",
            "state_files",
            "config_keys",
            "process_boundaries",
            "artifacts",
            "relevant_tests",
            "finding_ids",
            "error_ids",
            "evidence_commands",
            "verification_obligations",
            "verified_obligations",
        ):
            if not isinstance(row.get(field), list):
                findings.append(f"{path}: {field} must be an array")
        if not isinstance(row.get("project_index_present"), bool) or not isinstance(row.get("project_index_hash_matches"), bool):
            findings.append(f"{path}: PROJECT_INDEX presence/hash fields must be boolean")
        reconciliation = row.get("project_index_reconciliation")
        if reconciliation not in ALLOWED_PROJECT_INDEX_RECONCILIATIONS:
            findings.append(f"{path}: invalid PROJECT_INDEX reconciliation {reconciliation!r}")
        flags = {flag: row.get(flag) for flag in ("generated", "vendor", "archive", "binary", "runtime", "evidence_snapshot")}
        expected_obligations = verification_obligations_for(category, flags)
        if row.get("verification_obligations") != expected_obligations:
            findings.append(f"{path}: verification obligations do not match category/flags")
        if require_complete and status in ACHIEVED_STATUSES:
            if not row.get("reviewed_symbols_or_sections"):
                findings.append(f"{path}: achieved review has no reviewed symbols/sections")
            responsibility = str(row.get("responsibility_summary", "")).strip()
            if not responsibility or responsibility == DEFAULT_RESPONSIBILITY_SUMMARY:
                findings.append(f"{path}: achieved review retains placeholder responsibility")
            evidence_commands = row.get("evidence_commands")
            if not isinstance(evidence_commands, list) or not any(
                isinstance(command, str) and command.strip() and command not in BASELINE_EVIDENCE_COMMANDS
                for command in evidence_commands
            ):
                findings.append(f"{path}: achieved review has only inventory/default evidence")
            if str(row.get("prior_audit_coverage", "")).strip() in {"", "not_reconciled"}:
                findings.append(f"{path}: prior-audit coverage is not reconciled")
            if not str(row.get("reviewer_notes", "")).strip():
                findings.append(f"{path}: achieved review has no reviewer notes")
            verified = row.get("verified_obligations")
            verified_is_string_list = isinstance(verified, list) and all(isinstance(value, str) for value in verified)
            if (
                not verified_is_string_list
                or sorted(set(verified)) != expected_obligations
                or len(verified) != len(set(verified))
            ):
                findings.append(f"{path}: verified obligations do not exactly satisfy all applicable obligations")
            index_present = row.get("project_index_present")
            index_matches = row.get("project_index_hash_matches")
            if index_present:
                if index_matches and reconciliation != "hash_matched":
                    findings.append(f"{path}: matching PROJECT_INDEX entry is not reconciled as hash_matched")
                if not index_matches and reconciliation != "stale_with_finding":
                    findings.append(f"{path}: stale PROJECT_INDEX entry lacks a stale_with_finding disposition")
                if not index_matches and not row.get("finding_ids"):
                    findings.append(f"{path}: stale PROJECT_INDEX entry has no linked finding")
            elif reconciliation != "not_indexed_with_rationale":
                findings.append(f"{path}: unindexed path lacks an explicit reconciliation rationale")
    findings.extend(f"duplicate coverage path: {path}" for path in sorted(duplicates))
    findings.extend(f"missing coverage path: {path}" for path in sorted(expected_paths - seen, key=str.casefold))
    findings.extend(f"unexpected coverage path: {path}" for path in sorted(seen - expected_paths, key=str.casefold))
    return findings


def current_content_findings(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected_paths: set[str],
    root: Path = REPO_ROOT,
) -> list[str]:
    findings: list[str] = []
    tracked = set(git_tracked_paths(root=root))
    blobs = git_blob_map(root=root)
    for row in rows:
        path = canonical_path(str(row.get("path", "")))
        if not path or path not in expected_paths:
            continue
        actual_tracked = path in tracked
        mode, blob_hash = blobs.get(path, ("", ""))
        if mode == "120000":
            actual_source = "git_index_blob"
            actual_hash = sha256_bytes(git_blob_bytes(blob_hash, root=root))
        elif mode == "160000":
            actual_source = "git_index_gitlink"
            actual_hash = sha256_bytes(f"gitlink:{blob_hash}".encode("ascii"))
        else:
            try:
                worktree_absolute = resolved_regular_worktree_path(root, path)
            except ValueError as exc:
                findings.append(f"{path}: unsafe worktree path: {exc}")
                continue
            if worktree_absolute.is_file():
                actual_source = "worktree"
                actual_hash = sha256_file(worktree_absolute)
            elif actual_tracked and blob_hash:
                actual_source = "git_index_blob"
                actual_hash = sha256_bytes(git_blob_bytes(blob_hash, root=root))
            else:
                findings.append(f"{path}: covered content is unavailable from both worktree and stage-0 Git index")
                continue
        if row.get("content_source") != actual_source:
            findings.append(f"{path}: content source changed after ledger generation")
        if row.get("content_sha256") != actual_hash:
            findings.append(f"{path}: content hash changed after ledger generation")
        if bool(row.get("is_tracked")) != actual_tracked:
            findings.append(f"{path}: tracked-state flag is stale")
        if actual_tracked:
            if row.get("git_mode") != mode:
                findings.append(f"{path}: Git index mode changed after ledger generation")
            if row.get("git_blob_hash") != blob_hash:
                findings.append(f"{path}: Git blob hash is stale")
    return findings


def expected_coverage_paths(output_dir: Path, *, root: Path = REPO_ROOT) -> tuple[set[str], set[str]]:
    tracked = set(git_tracked_paths(root=root))
    expected = set(tracked)
    expected.update(set(git_untracked_paths(root=root)).intersection(audit_owned_untracked_paths(root=root)))
    try:
        output_rel = canonical_path(output_dir.resolve().relative_to(root.resolve()))
    except ValueError:
        output_rel = ""
    tracked_output_paths = {path for path in tracked if output_rel and (path == output_rel or path.startswith(output_rel + "/"))}
    if output_rel:
        expected = {path for path in expected if path != output_rel and not path.startswith(output_rel + "/")}
    return expected, tracked_output_paths


def evidence_ledger_findings(
    output_dir: Path,
    *,
    root: Path = REPO_ROOT,
    require_complete: bool = False,
) -> list[str]:
    """Validate fragment schemas and prove central ledgers are current derivatives."""

    findings: list[str] = []
    finding_records, finding_fragment_findings = prepare_finding_records(output_dir, root=root)
    if finding_fragment_findings:
        findings.extend(f"finding fragment: {value}" for value in finding_fragment_findings)
        valid_finding_ids: set[str] | None = None
    else:
        valid_finding_ids = {str(record["id"]) for record in finding_records}
        central_findings_path = output_dir / "FINDINGS.jsonl"
        central_findings = load_rows(central_findings_path)
        findings.extend(f"central finding ledger: {value}" for value in finding_record_findings(central_findings, root=root))
        if jsonl_text(central_findings) != jsonl_text(finding_records):
            findings.append("central finding ledger is missing, stale, or not the deterministic merge of worker fragments")
        register_path = output_dir / "FINDINGS_REGISTER.md"
        if not register_path.is_file() or register_path.read_text(encoding="utf-8") != findings_markdown(finding_records):
            findings.append("FINDINGS_REGISTER.md is missing or stale relative to finding fragments")

    error_records, error_fragment_findings = prepare_error_records(
        output_dir,
        valid_finding_ids=valid_finding_ids or set(),
    )
    if valid_finding_ids is None:
        error_records = load_error_fragments(output_dir)
        error_fragment_findings = error_record_findings(error_records)
    if error_fragment_findings:
        findings.extend(f"error fragment: {value}" for value in error_fragment_findings)
    else:
        central_errors_path = output_dir / "ERROR_LEDGER.jsonl"
        central_errors = load_rows(central_errors_path)
        findings.extend(
            f"central error ledger: {value}"
            for value in error_record_findings(central_errors, valid_finding_ids=valid_finding_ids or set())
        )
        if jsonl_text(central_errors) != jsonl_text(error_records):
            findings.append("central error ledger is missing, stale, or not the deterministic merge of worker fragments")
        error_markdown_path = output_dir / "ERROR_LEDGER.md"
        if not error_markdown_path.is_file() or error_markdown_path.read_text(encoding="utf-8") != error_ledger_markdown(error_records):
            findings.append("ERROR_LEDGER.md is missing or stale relative to error fragments")
        if require_complete:
            blocking_ids = [str(record["id"]) for record in error_records if record.get("coverage_blocked") is True]
            if blocking_ids:
                findings.append("coverage-blocking error records remain unresolved: " + ", ".join(blocking_ids))
    matrix_rows = load_rows(output_dir / "COVERAGE_MATRIX.jsonl")
    matrix_by_path = {canonical_path(str(row.get("path", ""))): row for row in matrix_rows}
    first_reviews = load_review_fragments(output_dir)
    attestations = load_second_review_attestations(output_dir)
    central_dispositions = {
        str(record.get("id")): str(record.get("disposition")) for record in finding_records
    }
    finding_location_paths = {
        str(record.get("id")): {
            canonical_path(str(location.get("path", ""))).casefold()
            for location in record.get("locations", [])
            if isinstance(location, Mapping) and location.get("path")
        }
        for record in finding_records
    }
    attestation_findings = second_review_attestation_findings(
        attestations,
        baseline_rows=matrix_by_path,
        first_review_records=first_reviews,
        valid_finding_ids=valid_finding_ids,
        valid_error_ids={str(record.get("id")) for record in error_records} if not error_fragment_findings else None,
        finding_dispositions=central_dispositions if valid_finding_ids is not None else None,
        finding_location_paths=finding_location_paths if valid_finding_ids is not None else None,
    )
    findings.extend(f"independent attestation: {value}" for value in attestation_findings)
    if require_complete and not attestation_findings and valid_finding_ids is not None:
        findings.extend(independent_review_completion_findings(matrix_rows, finding_records, attestations))
    return findings


def write_outputs(output_dir: Path, *, root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    rows, findings = prepare_review_rows(output_dir, root=root)
    if findings:
        raise ValueError("Current review evidence cannot be written:\n- " + "\n- ".join(findings))
    matrix_path = output_dir / "COVERAGE_MATRIX.jsonl"
    branch = run_git(["branch", "--show-current"], root=root).decode("utf-8").strip()
    head = run_git(["rev-parse", "HEAD"], root=root).decode("ascii").strip()
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text_set(
        [
            (matrix_path, jsonl_text(rows)),
            (output_dir / "COVERAGE_MATRIX.csv", csv_text(rows)),
            (output_dir / "BASELINE.md", baseline_markdown(rows, head=head, branch=branch)),
        ]
    )
    return rows


def check_outputs(
    output_dir: Path,
    *,
    require_complete: bool = False,
    root: Path = REPO_ROOT,
) -> list[str]:
    matrix_path = output_dir / "COVERAGE_MATRIX.jsonl"
    rows = load_rows(matrix_path)
    expected, tracked_output_paths = expected_coverage_paths(output_dir, root=root)
    findings = validation_findings(rows, expected_paths=expected, require_complete=require_complete)
    if tracked_output_paths:
        findings.append(
            "tracked audit output files require a non-self-referential freeze ledger: "
            + ", ".join(sorted(tracked_output_paths, key=str.casefold))
        )
    findings.extend(current_content_findings(rows, expected_paths=expected, root=root))
    prepared_rows, review_findings = prepare_review_rows(output_dir, root=root)
    findings.extend(review_findings)
    if not review_findings and jsonl_text(rows) != jsonl_text(prepared_rows):
        findings.append("coverage matrix is missing, stale, or not the deterministic merge of current review fragments")
    coverage_csv_path = output_dir / "COVERAGE_MATRIX.csv"
    if not coverage_csv_path.is_file() or coverage_csv_path.read_text(encoding="utf-8") != csv_text(rows):
        findings.append("COVERAGE_MATRIX.csv is missing or stale relative to COVERAGE_MATRIX.jsonl")
    branch = run_git(["branch", "--show-current"], root=root).decode("utf-8").strip()
    head = run_git(["rev-parse", "HEAD"], root=root).decode("ascii").strip()
    baseline_path = output_dir / "BASELINE.md"
    if not baseline_path.is_file() or baseline_path.read_text(encoding="utf-8") != baseline_markdown(
        rows, head=head, branch=branch
    ):
        findings.append("BASELINE.md is missing or stale relative to the current coverage generation")
    findings.extend(evidence_ledger_findings(output_dir, root=root, require_complete=require_complete))
    return findings


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true", help="Write or refresh the baseline and coverage matrices.")
    action.add_argument("--check", action="store_true", help="Validate path coverage and review-state invariants.")
    action.add_argument("--merge-errors", action="store_true", help="Validate worker error fragments and rebuild the central error ledger.")
    action.add_argument("--merge-reviews", action="store_true", help="Validate worker review fragments and merge them into the coverage matrix.")
    action.add_argument("--merge-findings", action="store_true", help="Validate worker finding fragments and rebuild the central finding register.")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="With --check, require achieved category-compatible review evidence, current ledgers, and zero blocking errors.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = args.output_dir if args.output_dir.is_absolute() else REPO_ROOT / args.output_dir
    if args.write:
        rows = write_outputs(output_dir)
        print(f"Wrote repository audit baseline with {len(rows)} coverage rows to {output_dir.relative_to(REPO_ROOT)}.")
        return 0
    if args.merge_errors:
        records = merge_error_ledgers(output_dir)
        print(f"Merged {len(records)} audit error records from worker fragments.")
        return 0
    if args.merge_reviews:
        rows = merge_review_ledgers(output_dir)
        achieved = sum(row["review_status"] in ACHIEVED_STATUSES for row in rows)
        blocked = sum(row["review_status"] == "blocked_with_reason" for row in rows)
        print(f"Merged review fragments into {len(rows)} coverage rows; {achieved} rows achieved and {blocked} blocked.")
        return 0
    if args.merge_findings:
        records = merge_finding_ledgers(output_dir)
        print(f"Merged {len(records)} exact-root-cause-deduplicated audit findings from worker fragments.")
        return 0
    findings = check_outputs(output_dir, require_complete=args.require_complete)
    if findings:
        print("Repository audit coverage check failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Repository audit coverage paths and review-state invariants are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
