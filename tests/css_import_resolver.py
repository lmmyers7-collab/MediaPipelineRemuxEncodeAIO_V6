from __future__ import annotations

import re
from pathlib import Path


_LOCAL_CSS_IMPORT_RE = re.compile(
    r"@import\s+url\(\s*(?P<quote>['\"])(?P<path>\./[^'\"]+)(?P=quote)\s*\)\s*;[ \t]*(?:\r?\n)?"
)
_ANY_CSS_IMPORT_RE = re.compile(r"@import\s+url\(")


def _assert_under_assets(path: Path, assets_root: Path) -> None:
    try:
        path.relative_to(assets_root)
    except ValueError as exc:
        raise AssertionError(f"CSS import escapes assets root: {path}") from exc


def local_css_import_paths(css_path: Path, assets_root: Path) -> list[Path]:
    assets_root = assets_root.resolve()
    css_path = css_path.resolve()
    _assert_under_assets(css_path, assets_root)
    source = css_path.read_text(encoding="utf-8")
    paths: list[Path] = []
    for match in _LOCAL_CSS_IMPORT_RE.finditer(source):
        target = (css_path.parent / match.group("path")).resolve()
        _assert_under_assets(target, assets_root)
        paths.append(target)
    return paths


def resolve_css_imports(css_path: Path, assets_root: Path) -> str:
    assets_root = assets_root.resolve()

    def resolve(path: Path, stack: tuple[Path, ...]) -> str:
        path = path.resolve()
        _assert_under_assets(path, assets_root)
        if path in stack:
            cycle = " -> ".join(str(item) for item in (*stack, path))
            raise AssertionError(f"CSS import cycle detected: {cycle}")

        source = path.read_text(encoding="utf-8")
        pieces: list[str] = []
        cursor = 0
        matched_spans: list[tuple[int, int]] = []
        for match in _LOCAL_CSS_IMPORT_RE.finditer(source):
            matched_spans.append(match.span())
            pieces.append(source[cursor : match.start()])
            target = (path.parent / match.group("path")).resolve()
            _assert_under_assets(target, assets_root)
            pieces.append(resolve(target, (*stack, path)))
            cursor = match.end()
        pieces.append(source[cursor:])

        for match in _ANY_CSS_IMPORT_RE.finditer(source):
            if not any(start <= match.start() < end for start, end in matched_spans):
                raise AssertionError(f"Unsupported CSS import in {path}: {source[match.start():match.start() + 80]!r}")
        return "".join(pieces)

    return resolve(css_path, ())


def resolved_css_asset_bundle(assets_root: Path) -> str:
    return "\n".join(
        resolve_css_imports(path, assets_root)
        for path in sorted(assets_root.glob("styles*.css"))
    )
