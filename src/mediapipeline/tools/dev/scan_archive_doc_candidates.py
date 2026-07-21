"""Dry-run scan for active documents that may be ready for archive.

The scan is advisory. It does not move files. It classifies active documents
and reports which active architecture/control files would need link updates
before a candidate is archived.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from collections.abc import Iterable

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))

DOCUMENT_EXTENSIONS = {".md", ".txt", ".docx"}
TEXT_REFERENCE_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".rs",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}
MAX_REFERENCE_BYTES = 2_000_000

SKIP_PREFIXES = (
    ".git/",
    "LocalBase/",
    "node_modules/",
    "apps/desktop/tauri/node_modules/",
    "apps/desktop/tauri/src-tauri/target/",
    "artifacts/",
    "docs/archive/",
    "docs/generated/summaries/",
    "ops/pipeline/runtime/",
    "ops/pipeline/tools/",
)

REQUIRED_ACTIVE_DOCS = {
    "README.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "docs/ARCHIVED_MD_INDEX.md",
    "docs/architecture/ARCHITECTURE.md",
    "docs/CURRENT_PROJECT_STATE.md",
    "docs/DOCS_INDEX.md",
    "docs/OPEN_WORK_CHECKLIST.md",
    "docs/README_MediaPipelineRemuxEncodeAIO.md",
    "docs/RealMediaValidationRuns/README.md",
    # Compact authoritative navigation; the preserved payload is skipped under
    # docs/archive/remediation-changelog/ like other historical evidence.
    "docs/REMEDIATION_CHANGELOG.md",
}

CONTROL_UPDATE_SOURCES = {
    "README.md",
    "AGENTS.md",
    "docs/CURRENT_PROJECT_STATE.md",
    "docs/DOCS_INDEX.md",
    "docs/OPEN_WORK_CHECKLIST.md",
}

HISTORICAL_REFERENCE_SOURCES = {
    "CHANGELOG.md",
    "docs/REMEDIATION_CHANGELOG.md",  # compact index with legacy entry titles
    "docs/ARCHIVED_MD_INDEX.md",
    "docs/change_control/CHANGELOG.md",
    "docs/change_control/CHANGE_INDEX.md",
    "docs/change_control/RELEASE_HISTORY.md",
}

ACTIVE_TOPIC_PREFIXES = (
    "docs/change_control/",
    "docs/desktop/",
    "docs/inventories/",
    "docs/operator/",
    "docs/sample-validation/",
    "docs/testing/",
)

REVIEW_TOPIC_PREFIXES = (
    "docs/implementation/",
    "docs/reviews/",
)

STRONG_ARCHIVE_SIGNAL_RE = re.compile(
    r"\b(archive-only|obsolete|redirect|superseded)\b",
    re.IGNORECASE,
)
COMPLETION_SIGNAL_RE = re.compile(
    r"\b(completed|closed|historical)\b",
    re.IGNORECASE,
)
REVIEW_SIGNAL_RE = re.compile(
    r"\b(audit|checklist|handoff|implementation ledger|plan|review|"
    r"validation plan)\b",
    re.IGNORECASE,
)
DATE_PATH_RE = re.compile(r"\b20\d{2}[-_]\d{2}[-_]\d{2}\b")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*]\(([^)]+)\)")
BACKTICK_TOKEN_RE = re.compile(r"`([^`]+)`")
PATHISH_RE = re.compile(
    r"(?P<path>(?:\.{1,2}[\\/])?(?:docs|Docs|src|tests|ops|apps|README|AGENTS|CHANGELOG)[^\s`<>)\],;:\"']+\.(?:md|txt|docx))"
)


@dataclass(frozen=True)
class Reference:
    path: str
    line: int
    category: str


@dataclass(frozen=True)
class DocumentScanResult:
    path: str
    status: str
    confidence: str
    archive_destination: str
    reasons: tuple[str, ...]
    inbound_references: tuple[Reference, ...]
    architecture_update_required: bool
    update_required_paths: tuple[str, ...]


def normalize_path(path: str | Path) -> str:
    normalized = str(path).replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def _case_key(path: str) -> str:
    return normalize_path(path).casefold()


def _is_skipped_path(path: str) -> bool:
    rel = normalize_path(path)
    key = _case_key(rel)
    return any(key == prefix.rstrip("/").casefold() or key.startswith(prefix.casefold()) for prefix in SKIP_PREFIXES)


def _iter_files(root: Path) -> Iterable[Path]:
    def ignore_walk_error(_error: OSError) -> None:
        return

    for current, directory_names, file_names in os.walk(root, topdown=True, onerror=ignore_walk_error):
        current_path = Path(current)
        directory_names[:] = [
            name
            for name in directory_names
            if not _is_skipped_path(normalize_path((current_path / name).relative_to(root)))
        ]
        for name in file_names:
            path = current_path / name
            rel = normalize_path(path.relative_to(root))
            if _is_skipped_path(rel):
                continue
            try:
                if path.is_file():
                    yield path
            except OSError:
                continue


def collect_document_paths(root: Path = REPO_ROOT) -> list[Path]:
    docs_root = root / "docs"
    files: list[Path] = []
    if docs_root.exists():
        for path in docs_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in DOCUMENT_EXTENSIONS:
                continue
            rel = normalize_path(path.relative_to(root))
            if _is_skipped_path(rel):
                continue
            files.append(path)
    for path in root.iterdir():
        if path.is_file() and (path.suffix.lower() in DOCUMENT_EXTENSIONS or path.name in {"README.md", "AGENTS.md", "CHANGELOG.md"}):
            files.append(path)
    return sorted(set(files), key=lambda item: _case_key(str(item.relative_to(root))))


def collect_reference_paths(root: Path = REPO_ROOT) -> list[Path]:
    files: list[Path] = []
    for path in _iter_files(root):
        if path.suffix.lower() not in TEXT_REFERENCE_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > MAX_REFERENCE_BYTES:
                continue
        except OSError:
            continue
        files.append(path)
    return sorted(set(files), key=lambda item: _case_key(str(item.relative_to(root))))


def _strip_reference_token(token: str) -> str:
    value = token.strip().strip("<>").strip()
    if " " in value and not value.lower().endswith((".md", ".txt", ".docx")):
        value = value.split(" ", 1)[0]
    value = value.split("#", 1)[0]
    value = value.lstrip("([{\"'")
    return value.rstrip(".,;:)]}\"'")


def _resolve_reference_token(source_rel: str, token: str) -> str | None:
    value = _strip_reference_token(token).replace("\\", "/")
    if not value or re.match(r"^[a-z][a-z0-9+.-]*:", value, re.IGNORECASE):
        return None
    if not value.lower().endswith((".md", ".txt", ".docx")):
        return None

    if value.startswith("/"):
        return normalize_path(value)

    first = value.split("/", 1)[0].casefold()
    if first in {"docs", "src", "tests", "ops", "apps"} or value in {"README.md", "AGENTS.md", "CHANGELOG.md"}:
        return normalize_path(value)

    source_parent = PurePosixPath(normalize_path(source_rel)).parent
    resolved = PurePosixPath(source_parent, value)
    parts: list[str] = []
    for part in resolved.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return normalize_path("/".join(parts))


def _reference_tokens(line: str) -> set[str]:
    tokens = {_strip_reference_token(match) for match in MARKDOWN_LINK_RE.findall(line)}
    tokens.update(_strip_reference_token(match) for match in BACKTICK_TOKEN_RE.findall(line))
    tokens.update(_strip_reference_token(match.group("path")) for match in PATHISH_RE.finditer(line))
    return {token for token in tokens if token}


def _reference_category(rel: str) -> str:
    normalized = normalize_path(rel)
    if normalized in HISTORICAL_REFERENCE_SOURCES:
        return "historical"
    if normalized.startswith("docs/generated/"):
        return "generated"
    if normalized.startswith("docs/architecture/") or normalized in CONTROL_UPDATE_SOURCES:
        return "architecture-control"
    return "active"


def collect_reference_index(
    target_rels: Iterable[str],
    reference_paths: Iterable[Path],
    root: Path = REPO_ROOT,
) -> dict[str, tuple[Reference, ...]]:
    target_by_key = {_case_key(rel): normalize_path(rel) for rel in target_rels}
    references: dict[str, set[Reference]] = {rel: set() for rel in target_by_key.values()}
    for path in reference_paths:
        rel = normalize_path(path.relative_to(root))
        rel_key = _case_key(rel)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        category = _reference_category(rel)
        for line_no, line in enumerate(lines, start=1):
            if not any(ext in line.lower() for ext in (".md", ".txt", ".docx")):
                continue
            for token in _reference_tokens(line):
                resolved = _resolve_reference_token(rel, token)
                if not resolved:
                    continue
                target = target_by_key.get(_case_key(resolved))
                if target and _case_key(target) != rel_key:
                    references[target].add(Reference(rel, line_no, category))
    return {
        rel: tuple(sorted(refs, key=lambda ref: (ref.path.casefold(), ref.line, ref.category)))
        for rel, refs in references.items()
    }


def _read_document_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _archive_destination(rel: str, as_of: str) -> str:
    normalized = normalize_path(rel)
    if normalized.startswith("docs/"):
        return f"docs/archive/docs-housekeeping/{as_of}-active-doc-archive-scan/{normalized[len('docs/'):]}"
    return f"docs/archive/docs-housekeeping/{as_of}-active-doc-archive-scan/root/{normalized}"


def _path_signals(rel: str, text: str) -> list[str]:
    normalized = normalize_path(rel)
    lower = normalized.lower()
    opening = text[:800]
    signals: list[str] = []
    if any(lower.startswith(prefix) for prefix in REVIEW_TOPIC_PREFIXES):
        signals.append("dated review or implementation pack")
    if lower.startswith("docs/audits/"):
        signals.append("audit document")
    if DATE_PATH_RE.search(normalized):
        signals.append("dated documentation path")
    if STRONG_ARCHIVE_SIGNAL_RE.search(normalized) or STRONG_ARCHIVE_SIGNAL_RE.search(opening):
        signals.append("filename or opening text says archive-only, obsolete, redirect, or superseded")
    elif signals and COMPLETION_SIGNAL_RE.search(f"{normalized}\n{opening}"):
        signals.append("content or filename says completed, closed, or historical")
    if REVIEW_SIGNAL_RE.search(normalized):
        signals.append("filename has review, audit, checklist, handoff, or plan wording")
    filename = PurePosixPath(normalized).name.lower()
    if filename.startswith(("08-final-review", "09-implementation-ledger")):
        signals.append("final review or implementation ledger file")
    return signals


def _classify_document(
    rel: str,
    text: str,
    references: tuple[Reference, ...],
    *,
    as_of: str,
) -> DocumentScanResult:
    normalized = normalize_path(rel)
    lower = normalized.lower()
    reasons: list[str] = []
    signals = _path_signals(normalized, text)
    active_refs = tuple(ref for ref in references if ref.category in {"active", "architecture-control"})
    update_required_paths = tuple(sorted({ref.path for ref in references if ref.category == "architecture-control"}))
    architecture_update_required = bool(update_required_paths) or lower.startswith("docs/architecture/")

    if normalized in REQUIRED_ACTIVE_DOCS:
        return DocumentScanResult(
            normalized,
            "keep-active",
            "high",
            "",
            ("required active onboarding, current-state, or architecture document",),
            references,
            architecture_update_required,
            update_required_paths,
        )

    if lower.startswith("docs/generated/"):
        return DocumentScanResult(
            normalized,
            "keep-active",
            "high",
            "",
            ("generated navigation output; refresh instead of archiving manually",),
            references,
            architecture_update_required,
            update_required_paths,
        )

    if lower.startswith("docs/architecture/"):
        if not any("archive-only, obsolete" in reason for reason in signals):
            reason = "architecture document with no archive/completion signal"
            if signals:
                reason = "architecture document needs human review before any archive move: " + "; ".join(signals)
            return DocumentScanResult(
                normalized,
                "keep-active" if not signals else "review",
                "medium" if not signals else "low",
                "" if not signals else _archive_destination(normalized, as_of),
                (reason,),
                references,
                architecture_update_required,
                update_required_paths,
            )

    if lower.startswith(ACTIVE_TOPIC_PREFIXES) and not signals:
        return DocumentScanResult(
            normalized,
            "keep-active",
            "medium",
            "",
            ("active topic document with no archive/completion signal",),
            references,
            architecture_update_required,
            update_required_paths,
        )

    if signals:
        reasons.extend(signals)
        if active_refs:
            reasons.append("active references must be updated or intentionally left as historical pointers")
        status = "archive-candidate"
        confidence = "medium"
        if update_required_paths or lower.startswith("docs/architecture/"):
            confidence = "low"
        elif not active_refs and any("completed" in reason or "dated" in reason or "audit" in reason for reason in reasons):
            confidence = "high"
        return DocumentScanResult(
            normalized,
            status,
            confidence,
            _archive_destination(normalized, as_of),
            tuple(dict.fromkeys(reasons)),
            references,
            architecture_update_required,
            update_required_paths,
        )

    if not active_refs:
        return DocumentScanResult(
            normalized,
            "review",
            "low",
            _archive_destination(normalized, as_of),
            ("no active inbound references found; human review needed before archive",),
            references,
            architecture_update_required,
            update_required_paths,
        )

    return DocumentScanResult(
        normalized,
        "review",
        "low",
        _archive_destination(normalized, as_of),
        ("active references found but no archive/completion signal",),
        references,
        architecture_update_required,
        update_required_paths,
    )


def scan_documents(root: Path = REPO_ROOT, *, as_of: str | None = None) -> list[DocumentScanResult]:
    scan_date = as_of or date.today().isoformat()
    documents = collect_document_paths(root)
    references = collect_reference_paths(root)
    document_rels = [normalize_path(path.relative_to(root)) for path in documents]
    reference_index = collect_reference_index(document_rels, references, root)
    results: list[DocumentScanResult] = []
    for path, rel in zip(documents, document_rels, strict=False):
        text = _read_document_text(path)
        inbound = reference_index.get(rel, ())
        results.append(_classify_document(rel, text, inbound, as_of=scan_date))
    return sorted(results, key=lambda result: (result.status != "archive-candidate", result.path.casefold()))


def _count_by_status(results: Iterable[DocumentScanResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return dict(sorted(counts.items()))


def render_markdown(results: list[DocumentScanResult], *, root: Path, statuses: set[str] | None = None, limit: int = 0) -> str:
    filtered = [result for result in results if not statuses or result.status in statuses]
    if limit > 0:
        filtered = filtered[:limit]
    counts = _count_by_status(results)
    lines = [
        "# Document Archive Candidate Scan",
        "",
        "Root: repository root.",
        "",
        "This is a dry-run advisory scan. Move nothing until the listed active references are reconciled.",
        "",
        "## Summary",
        "",
        f"- Scanned documents: {len(results)}",
        f"- Status counts: {', '.join(f'{status}={count}' for status, count in counts.items()) or 'none'}",
        "",
        "## Results",
        "",
        "| Status | Confidence | Document | Active refs | Architecture/control updates | Reasons |",
        "|---|---|---|---:|---|---|",
    ]
    for result in filtered:
        active_ref_count = sum(1 for ref in result.inbound_references if ref.category in {"active", "architecture-control"})
        updates = ", ".join(f"`{path}`" for path in result.update_required_paths)
        if result.architecture_update_required and not updates:
            updates = "document is under `docs/architecture/`"
        if not updates:
            updates = "-"
        reasons = "; ".join(result.reasons)
        lines.append(
            f"| {result.status} | {result.confidence} | `{result.path}` | {active_ref_count} | {updates} | {reasons} |"
        )

    candidates = [result for result in results if result.status == "archive-candidate"]
    if candidates:
        lines.extend(["", "## Archive Destinations", ""])
        for result in candidates:
            lines.append(f"- `{result.path}` -> `{result.archive_destination}`")
            if result.update_required_paths:
                lines.append(f"  Update first: {', '.join(f'`{path}`' for path in result.update_required_paths)}")
    return "\n".join(lines) + "\n"


def render_json(results: list[DocumentScanResult]) -> str:
    return json.dumps([asdict(result) for result in results], indent=2) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root to scan.")
    parser.add_argument("--as-of", default=date.today().isoformat(), help="Date label used in proposed archive destinations.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown", help="Output format.")
    parser.add_argument(
        "--status",
        action="append",
        choices=("archive-candidate", "review", "keep-active"),
        help="Limit markdown output to one or more statuses.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit markdown rows after filtering. 0 means no limit.")
    parser.add_argument("--output", type=Path, help="Optional output file. Parent directories must already exist.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    results = scan_documents(root, as_of=args.as_of)
    if args.format == "json":
        output = render_json(results)
    else:
        output = render_markdown(results, root=root, statuses=set(args.status or []), limit=args.limit)

    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
