"""Segment and verify the preserved remediation changelog evidence ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SOURCE_RELATIVE_PATH = Path("docs/REMEDIATION_CHANGELOG.md")
ARCHIVE_RELATIVE_DIR = Path("docs/archive/remediation-changelog")
MANIFEST_NAME = "manifest.json"
DEFAULT_SEGMENT_SIZE = 250
COMPACT_INDEX_MARKER = "<!-- remediation-changelog-compact-index -->"

SECTION_RE = re.compile(rb"(?m)^## (?P<heading>20\d{2}-\d{2}-\d{2} - [^\r\n]+)\r?\n")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
EXPLICIT_ANCHOR_RE = re.compile(r'<a\s+(?:id|name)="([^"]+)"\s*></a>', re.IGNORECASE)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
LEGACY_LINK_RE = re.compile(r"\[([^\]]+)\]\(#([^)]+)\)")
NAVIGATION_LINE_RE = re.compile(rb'(?m)^<a id="[^"]+"></a>\r?\n(?=## 20\d{2}-\d{2}-\d{2} - )')


class ArchiveVerificationError(RuntimeError):
    """Raised when segmented evidence no longer matches its preservation manifest."""


@dataclass(frozen=True)
class HistoricalSection:
    ordinal: int
    heading: str
    date: str
    anchor: str
    preserved_bytes: bytes
    legacy_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArchiveSegment:
    path: str
    start_ordinal: int
    end_ordinal: int
    sections: tuple[HistoricalSection, ...]
    preserved_bytes: bytes
    archive_bytes: bytes


@dataclass(frozen=True)
class ArchivePlan:
    source_bytes: bytes
    navigation_bytes: bytes
    history_offset: int
    segment_size: int
    sections: tuple[HistoricalSection, ...]
    segments: tuple[ArchiveSegment, ...]
    unresolved_legacy_links: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class VerificationReport:
    source_bytes_before: int
    history_bytes: int
    index_bytes: int
    section_count: int
    segment_count: int
    history_sha256: str
    heading_order_sha256: str
    checked_links: int


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _github_anchor_base(heading: str) -> str:
    without_tags = re.sub(r"<[^>]*>", "", heading)
    without_punctuation = re.sub(r"[^\w\- ]", "", without_tags, flags=re.UNICODE)
    return without_punctuation.strip().lower().replace(" ", "-")


def _unique_anchors(headings: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    anchors: list[str] = []
    for heading in headings:
        base = _github_anchor_base(heading)
        occurrence = counts.get(base, 0)
        anchors.append(base if occurrence == 0 else f"{base}-{occurrence}")
        counts[base] = occurrence + 1
    return anchors


def _normalized_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _resolve_legacy_links(
    navigation_text: str,
    sections: list[HistoricalSection],
) -> tuple[dict[int, set[str]], list[tuple[str, str]]]:
    aliases: dict[int, set[str]] = {section.ordinal: set() for section in sections}
    by_anchor = {section.anchor: section for section in sections}
    by_title: dict[str, list[HistoricalSection]] = {}
    by_date: dict[str, list[HistoricalSection]] = {}
    for section in sections:
        title = section.heading.split(" - ", 1)[1]
        by_title.setdefault(_normalized_title(title), []).append(section)
        by_date.setdefault(section.date, []).append(section)

    unresolved: list[tuple[str, str]] = []
    seen_fragments: set[str] = set()
    for label, fragment in LEGACY_LINK_RE.findall(navigation_text):
        if fragment in seen_fragments:
            continue
        seen_fragments.add(fragment)
        section = by_anchor.get(fragment)
        if section is None and re.fullmatch(r"20\d{2}-\d{2}-\d{2}", label):
            dated = by_date.get(label, [])
            section = dated[0] if dated else None
        if section is None:
            candidates = by_title.get(_normalized_title(label), [])
            section = candidates[0] if candidates else None
        if section is None:
            unresolved.append((label, fragment))
            continue
        if fragment != section.anchor:
            aliases[section.ordinal].add(fragment)
    return aliases, unresolved


def build_archive_plan(source_bytes: bytes, *, segment_size: int = DEFAULT_SEGMENT_SIZE) -> ArchivePlan:
    """Build a deterministic, order-preserving segmentation plan."""
    if segment_size < 1:
        raise ValueError("segment_size must be positive")
    if COMPACT_INDEX_MARKER.encode("utf-8") in source_bytes:
        raise ValueError("source is already a compact remediation changelog index")

    matches = list(SECTION_RE.finditer(source_bytes))
    if not matches:
        raise ValueError("no historical '## YYYY-MM-DD - ...' sections found")
    history_offset = matches[0].start()
    navigation_bytes = source_bytes[:history_offset]
    headings = [match.group("heading").decode("utf-8") for match in matches]
    anchors = _unique_anchors(headings)

    sections: list[HistoricalSection] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source_bytes)
        preserved = source_bytes[match.start() : end]
        heading = headings[index]
        sections.append(
            HistoricalSection(
                ordinal=index + 1,
                heading=heading,
                date=heading[:10],
                anchor=anchors[index],
                preserved_bytes=preserved,
            )
        )

    reconstructed = b"".join(section.preserved_bytes for section in sections)
    if reconstructed != source_bytes[history_offset:]:
        raise ValueError("section parsing did not cover the historical source bytes exactly")

    aliases, unresolved = _resolve_legacy_links(navigation_bytes.decode("utf-8"), sections)
    sections = [
        HistoricalSection(
            ordinal=section.ordinal,
            heading=section.heading,
            date=section.date,
            anchor=section.anchor,
            preserved_bytes=section.preserved_bytes,
            legacy_aliases=tuple(sorted(aliases[section.ordinal])),
        )
        for section in sections
    ]

    segments: list[ArchiveSegment] = []
    for start in range(0, len(sections), segment_size):
        group = tuple(sections[start : start + segment_size])
        start_ordinal = group[0].ordinal
        end_ordinal = group[-1].ordinal
        path = f"entries-{start_ordinal:04d}-{end_ordinal:04d}.md"
        preserved = b"".join(section.preserved_bytes for section in group)
        archived = b"".join(
            f'<a id="{section.anchor}"></a>\n'.encode("utf-8") + section.preserved_bytes
            for section in group
        )
        segments.append(
            ArchiveSegment(
                path=path,
                start_ordinal=start_ordinal,
                end_ordinal=end_ordinal,
                sections=group,
                preserved_bytes=preserved,
                archive_bytes=archived,
            )
        )

    return ArchivePlan(
        source_bytes=source_bytes,
        navigation_bytes=navigation_bytes,
        history_offset=history_offset,
        segment_size=segment_size,
        sections=tuple(sections),
        segments=tuple(segments),
        unresolved_legacy_links=tuple(unresolved),
    )


def _render_index(plan: ArchivePlan) -> bytes:
    source_lines = plan.source_bytes.count(b"\n")
    history = plan.source_bytes[plan.history_offset :]
    lines = [
        "# MediaPipelineRemuxEncodeAIO V6 Remediation Changelog History Index",
        "",
        COMPACT_INDEX_MARKER,
        "",
        "> This is the authoritative navigation surface for the closed remediation ledger. "
        "It is forensic history, not the current backlog and not a competing changelog authority.",
        "",
        "For current work, start with [Current Project State](CURRENT_PROJECT_STATE.md), "
        "[Open Work Checklist](OPEN_WORK_CHECKLIST.md), and the repository [CHANGELOG](../CHANGELOG.md).",
        "",
        "Historical sections were moved mechanically, in their original order, into fixed bands of "
        f"{plan.segment_size} entries. "
        "Each archived section keeps its heading and body verbatim; explicit `<a>` lines are navigation metadata.",
        "",
        "## Search",
        "",
        "Search all preserved history without loading it as one document:",
        "",
        "```powershell",
        "rg -n --glob '*.md' '2026-05-15|C-019|Pending Publish' docs/archive/remediation-changelog",
        "```",
        "",
        "The entry index below retains dates, identifiers, topics, generated heading anchors, and legacy "
        "navigation fragments. Old links to this file land on the matching index row; that row links to the "
        "preserved section.",
        "",
        "## Preservation evidence",
        "",
        f"- Original ledger: {len(plan.source_bytes):,} bytes and {source_lines:,} newline-terminated lines.",
        f"- Preserved history: {len(history):,} bytes across {len(plan.sections):,} ordered sections.",
        f"- Preserved-history SHA-256: `{_sha256(history)}`.",
        f"- Ordered-heading SHA-256: `{_sha256(_heading_order_bytes(plan.sections))}`.",
        "- Machine-readable evidence: [archive manifest](archive/remediation-changelog/manifest.json).",
        "- Verification: `apps/desktop/runtime/Python/python.exe ops/scripts/dev/run-python-tool.py "
        "mediapipeline.tools.dev.remediation_changelog_archive verify`.",
        "",
        "## Archive segments",
        "",
        "| Original ordinals | Dates encountered | Sections | Preserved bytes | File |",
        "|---:|---|---:|---:|---|",
    ]
    section_to_segment: dict[int, ArchiveSegment] = {}
    for segment in plan.segments:
        for section in segment.sections:
            section_to_segment[section.ordinal] = segment
        dates = list(dict.fromkeys(section.date for section in segment.sections))
        date_summary = ", ".join(dates)
        lines.append(
            f"| {segment.start_ordinal:04d}-{segment.end_ordinal:04d} | {date_summary} | "
            f"{len(segment.sections)} | {len(segment.preserved_bytes):,} | "
            f"[{segment.path}](archive/remediation-changelog/{segment.path}) |"
        )

    lines.extend(["", "## Entry index in original ledger order", ""])
    for section in plan.sections:
        segment = section_to_segment[section.ordinal]
        aliases = [section.anchor, *section.legacy_aliases]
        anchor_markup = "".join(f'<a id="{alias}"></a>' for alias in aliases)
        title = section.heading.split(" - ", 1)[1]
        lines.append(
            f'{anchor_markup}- {section.ordinal:04d} [{section.date} — {title}]'
            f'(archive/remediation-changelog/{segment.path}#{section.anchor})'
        )

    if plan.unresolved_legacy_links:
        lines.extend(["", "## Unresolved legacy navigation fragments", ""])
        for label, fragment in plan.unresolved_legacy_links:
            lines.append(f'<a id="{fragment}"></a>- `{label}` (legacy index label retained for discovery)')

    return ("\n".join(lines) + "\n").encode("utf-8")


def _heading_order_bytes(sections: tuple[HistoricalSection, ...] | list[HistoricalSection]) -> bytes:
    return ("\n".join(section.heading for section in sections) + "\n").encode("utf-8")


def _manifest_for(plan: ArchivePlan, index_bytes: bytes) -> dict[str, object]:
    history = plan.source_bytes[plan.history_offset :]
    return {
        "schema_version": 1,
        "authority": "docs/REMEDIATION_CHANGELOG.md is the compact navigation index; CHANGELOG.md remains the shipped change authority.",
        "split_rule": f"contiguous original ledger order in fixed bands of {plan.segment_size} historical sections",
        "source_before_segmentation": {
            "path": SOURCE_RELATIVE_PATH.as_posix(),
            "bytes": len(plan.source_bytes),
            "newline_count": plan.source_bytes.count(b"\n"),
            "sha256": _sha256(plan.source_bytes),
        },
        "replaced_navigation_metadata": {
            "bytes": len(plan.navigation_bytes),
            "sha256": _sha256(plan.navigation_bytes),
        },
        "preserved_history": {
            "source_offset": plan.history_offset,
            "bytes": len(history),
            "sha256": _sha256(history),
            "section_count": len(plan.sections),
            "heading_order_sha256": _sha256(_heading_order_bytes(plan.sections)),
            "first_heading": plan.sections[0].heading,
            "last_heading": plan.sections[-1].heading,
        },
        "compact_index": {
            "path": SOURCE_RELATIVE_PATH.as_posix(),
            "bytes": len(index_bytes),
            "sha256": _sha256(index_bytes),
            "entry_count": len(plan.sections),
            "legacy_alias_count": sum(len(section.legacy_aliases) for section in plan.sections),
            "unresolved_legacy_link_count": len(plan.unresolved_legacy_links),
        },
        "segments": [
            {
                "path": (ARCHIVE_RELATIVE_DIR / segment.path).as_posix(),
                "start_ordinal": segment.start_ordinal,
                "end_ordinal": segment.end_ordinal,
                "section_count": len(segment.sections),
                "first_heading": segment.sections[0].heading,
                "last_heading": segment.sections[-1].heading,
                "preserved_bytes": len(segment.preserved_bytes),
                "preserved_sha256": _sha256(segment.preserved_bytes),
                "archive_bytes": len(segment.archive_bytes),
                "archive_sha256": _sha256(segment.archive_bytes),
            }
            for segment in plan.segments
        ],
    }


def segment_archive(root: Path = REPO_ROOT, *, segment_size: int = DEFAULT_SEGMENT_SIZE) -> VerificationReport:
    """Mechanically segment the giant ledger and replace it with its compact index."""
    source_path = root / SOURCE_RELATIVE_PATH
    archive_dir = root / ARCHIVE_RELATIVE_DIR
    if archive_dir.exists():
        raise FileExistsError(f"archive directory already exists: {archive_dir}")

    plan = build_archive_plan(source_path.read_bytes(), segment_size=segment_size)
    index_bytes = _render_index(plan)
    manifest = _manifest_for(plan, index_bytes)

    archive_dir.mkdir(parents=True)
    for segment in plan.segments:
        (archive_dir / segment.path).write_bytes(segment.archive_bytes)
    source_path.write_bytes(index_bytes)
    (archive_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return verify_archive(root)


def _anchors_for_markdown(text: str) -> set[str]:
    anchors = set(EXPLICIT_ANCHOR_RE.findall(text))
    headings = [match.group(2) for match in HEADING_RE.finditer(text)]
    anchors.update(_unique_anchors(headings))
    return anchors


def _verify_index_links(root: Path, index_path: Path, index_text: str) -> int:
    checked = 0
    for raw_target in MARKDOWN_LINK_RE.findall(index_text):
        if re.match(r"^[a-z][a-z0-9+.-]*:", raw_target, re.IGNORECASE):
            continue
        target, _, fragment = raw_target.partition("#")
        resolved = index_path if not target else (index_path.parent / unquote(target)).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError as exc:
            raise ArchiveVerificationError(f"index link escapes repository: {raw_target}") from exc
        if not resolved.is_file():
            raise ArchiveVerificationError(f"index link target does not exist: {raw_target}")
        if fragment:
            anchors = _anchors_for_markdown(resolved.read_text(encoding="utf-8"))
            if unquote(fragment) not in anchors:
                raise ArchiveVerificationError(f"index fragment does not resolve: {raw_target}")
        checked += 1
    return checked


def _require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ArchiveVerificationError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def verify_archive(root: Path = REPO_ROOT) -> VerificationReport:
    """Verify byte preservation, section order/count, and compact-index links."""
    manifest_path = root / ARCHIVE_RELATIVE_DIR / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ArchiveVerificationError(f"cannot load archive manifest: {manifest_path}") from exc
    _require_equal(manifest.get("schema_version"), 1, "manifest schema")

    source_metadata = manifest["source_before_segmentation"]
    history_metadata = manifest["preserved_history"]
    index_metadata = manifest["compact_index"]
    segment_metadata = manifest["segments"]
    index_path = root / SOURCE_RELATIVE_PATH
    index_bytes = index_path.read_bytes()
    _require_equal(len(index_bytes), index_metadata["bytes"], "compact index byte count")
    _require_equal(_sha256(index_bytes), index_metadata["sha256"], "compact index hash")
    if COMPACT_INDEX_MARKER.encode("utf-8") not in index_bytes:
        raise ArchiveVerificationError("compact index marker is missing")
    if source_metadata["bytes"] >= 1_000_000 and len(index_bytes) * 4 >= source_metadata["bytes"]:
        raise ArchiveVerificationError("compact index is not at least 75% smaller than the original ledger")

    expected_segment_paths = {str(item["path"]) for item in segment_metadata}
    actual_segment_paths = {
        path.relative_to(root).as_posix()
        for path in (root / ARCHIVE_RELATIVE_DIR).glob("entries-*.md")
    }
    _require_equal(actual_segment_paths, expected_segment_paths, "archive segment path set")

    preserved_parts: list[bytes] = []
    headings: list[str] = []
    expected_ordinal = 1
    for item in segment_metadata:
        path = root / Path(str(item["path"]))
        archived = path.read_bytes()
        _require_equal(len(archived), item["archive_bytes"], f"{item['path']} byte count")
        _require_equal(_sha256(archived), item["archive_sha256"], f"{item['path']} archive hash")
        preserved = NAVIGATION_LINE_RE.sub(b"", archived)
        _require_equal(len(preserved), item["preserved_bytes"], f"{item['path']} preserved byte count")
        _require_equal(_sha256(preserved), item["preserved_sha256"], f"{item['path']} preserved hash")
        matches = list(SECTION_RE.finditer(preserved))
        _require_equal(len(matches), item["section_count"], f"{item['path']} section count")
        _require_equal(item["start_ordinal"], expected_ordinal, f"{item['path']} start ordinal")
        expected_ordinal = int(item["end_ordinal"]) + 1
        headings.extend(match.group("heading").decode("utf-8") for match in matches)
        preserved_parts.append(preserved)

    history = b"".join(preserved_parts)
    _require_equal(len(history), history_metadata["bytes"], "preserved history byte count")
    _require_equal(_sha256(history), history_metadata["sha256"], "preserved history hash")
    _require_equal(len(headings), history_metadata["section_count"], "historical section count")
    heading_order = ("\n".join(headings) + "\n").encode("utf-8")
    _require_equal(_sha256(heading_order), history_metadata["heading_order_sha256"], "heading order hash")
    _require_equal(headings[0], history_metadata["first_heading"], "first heading")
    _require_equal(headings[-1], history_metadata["last_heading"], "last heading")

    index_text = index_bytes.decode("utf-8")
    checked_links = _verify_index_links(root, index_path, index_text)
    for item in segment_metadata:
        segment_name = Path(str(item["path"])).name
        expected_links = int(item["section_count"])
        actual_links = index_text.count(f"archive/remediation-changelog/{segment_name}#")
        _require_equal(actual_links, expected_links, f"{segment_name} entry-index link count")

    return VerificationReport(
        source_bytes_before=int(source_metadata["bytes"]),
        history_bytes=len(history),
        index_bytes=len(index_bytes),
        section_count=len(headings),
        segment_count=len(segment_metadata),
        history_sha256=str(history_metadata["sha256"]),
        heading_order_sha256=str(history_metadata["heading_order_sha256"]),
        checked_links=checked_links,
    )


def _format_report(report: VerificationReport) -> str:
    reduction = 100 * (1 - report.index_bytes / report.source_bytes_before)
    return (
        "Remediation changelog archive verification passed.\n"
        f"- original ledger: {report.source_bytes_before:,} bytes\n"
        f"- compact index: {report.index_bytes:,} bytes ({reduction:.1f}% smaller)\n"
        f"- preserved history: {report.history_bytes:,} bytes; SHA-256 {report.history_sha256}\n"
        f"- ordered sections: {report.section_count:,}; heading-order SHA-256 {report.heading_order_sha256}\n"
        f"- archive segments: {report.segment_count}; resolved index links: {report.checked_links}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("segment", "verify"))
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--segment-size", type=int, default=DEFAULT_SEGMENT_SIZE)
    args = parser.parse_args(argv)
    try:
        if args.action == "segment":
            report = segment_archive(args.root, segment_size=args.segment_size)
        else:
            report = verify_archive(args.root)
    except (ArchiveVerificationError, FileExistsError, ValueError) as exc:
        print(f"Remediation changelog archive check failed: {exc}", file=sys.stderr)
        return 1
    print(_format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
