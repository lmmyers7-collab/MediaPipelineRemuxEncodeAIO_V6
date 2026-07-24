"""Materialize a Tdarr sample matrix as local Movies/TV test libraries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path, PurePosixPath, PureWindowsPath
from collections.abc import Iterable

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
DEFAULT_INVENTORY = REPO_ROOT / "LocalBase" / "TestFixtures" / "TdarrSamples" / "inventory.csv"
DEFAULT_LIBRARY_ROOT = REPO_ROOT / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
DEFAULT_TEMPLATE = REPO_ROOT / "ops" / "pipeline" / "config" / "MediaPipeline_config_template.psd1"
SENTINEL_NAME = ".tdarr-matrix-generator.json"
MANIFEST_SCHEMA = "tdarr_matrix_materialized_library.v1"
CONFIG_NAME = "MediaPipeline_config.tdarr-matrix.psd1"
LIBRARY_ROOT_IDENTITY_SCHEMA = "mediapipeline_tdarr_matrix_root_identity.v1"
LIBRARY_ROOT_PURPOSE = "mediapipeline_tdarr_matrix_test_library"
LIBRARY_ROOT_PREFIX = "tdarrmatrix"

BUCKET_SERIES = {
    "audio-only": "TDAudio",
    "h264-h265-direct": "TDDirect",
    "av1-vp-modern": "TDModern",
    "legacy-video": "TDLegacy",
    "mjpeg-large": "TDMjpeg",
    "container-stress": "TDContainer",
}
CONTAINER_STRESS_EXTENSIONS = {"avi", "mov", "mp2", "wmv"}
MODERN_VIDEO_CODECS = {"libaom-av1", "av1", "vp8", "vp9", "libvpx", "libvpx-vp9"}
DIRECT_VIDEO_CODECS = {"h264", "h265"}
LEGACY_VIDEO_CODECS = {"flv", "h263", "h263p", "mpeg1video", "mpeg2video", "wmv1", "wmv2"}
VALID_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".m2ts", ".wmv", ".mp2")


@dataclass(frozen=True)
class TdarrSample:
    name: str
    local_path: str
    source_url: str
    source_page: str
    medium: str
    container: str
    resolution: str
    video_codec: str
    audio_codec: str
    duration: str
    advertised_size_mb: str
    actual_size_bytes: str
    sha256: str
    video_decodable: str = ""


@dataclass(frozen=True)
class MaterializedRow:
    view: str
    case_id: str
    bucket: str
    generated_path: Path
    source_path: Path
    sample: TdarrSample


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def resolve_repo_path(value: str | Path, *, repo_root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def resolve_inventory_local_path(value: str, *, inventory_root: Path) -> Path:
    text = str(value or "").replace("\\", "/").strip()
    if not text:
        raise ValueError("local_path must be a non-empty inventory-relative path")
    windows_path = PureWindowsPath(text)
    if PurePosixPath(text).is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise ValueError(f"local_path must be inventory-relative, not absolute or drive-qualified: {text}")
    if ".." in PurePosixPath(text).parts:
        raise ValueError(f"local_path must not contain parent traversal: {text}")
    inventory_root = inventory_root.resolve(strict=False)
    source_path = (inventory_root / text).resolve(strict=False)
    try:
        source_path.relative_to(inventory_root)
    except ValueError as exc:
        raise ValueError(f"local_path resolves outside inventory root {inventory_root}: {text}") from exc
    return source_path


def ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("/", "\\").replace("'", "''") + "'"


def ps_bool(value: bool) -> str:
    return "$true" if value else "$false"


def ps_array(values: Iterable[str]) -> str:
    return "@(" + ", ".join(ps_quote(value) for value in values) + ")"


def safe_token(value: str, *, fallback: str) -> str:
    token = str(value or "").strip().lower()
    if not token or token == "-":
        token = fallback
    token = re.sub(r"[^a-z0-9._=-]+", "-", token).strip("-")
    return token or fallback


def display_tokens(sample: TdarrSample) -> tuple[str, str, str, str]:
    resolution = safe_token(sample.resolution, fallback="audio")
    video = safe_token(sample.video_codec, fallback="novideo")
    audio = safe_token(sample.audio_codec, fallback="noaudio")
    container = safe_token(sample.container, fallback="container")
    return resolution, video, audio, container


def classify_bucket(medium: str, video_codec: str, container: str) -> tuple[str, bool]:
    """Classify a sample into a diagnostic bucket.

    Returns ``(bucket, is_fallback)``. ``is_fallback`` is ``True`` only when the codec
    matched no explicit rule and was defaulted to ``legacy-video``; callers (the audit) use
    it to surface unmapped codecs instead of silently mis-bucketing them (G6). Bucket
    assignment is unchanged from the original precedence order.

    Precedence note (G7): ``container-stress`` is matched on container BEFORE the codec
    buckets, so any h264/h265/av1/vp9 file in an avi/mov/wmv/mp2 container is filed as
    ``container-stress`` rather than by codec. The container is the dominant test axis here,
    which is why the codec buckets (``h264-h265-direct``, ``av1-vp-modern``, ``legacy-video``)
    only ever see mkv/mp4 inputs and the overall distribution is heavily weighted toward
    ``container-stress``. ``mjpeg`` is matched before container so mjpeg-in-avi stays
    ``mjpeg-large``. Change this ordering only with a matching update to the audit and tests.
    """
    medium_token = safe_token(medium, fallback="unknown")
    video = safe_token(video_codec, fallback="novideo")
    container_token = safe_token(container, fallback="")

    if medium_token == "audio" or video == "novideo":
        return "audio-only", False
    if video == "mjpeg":
        return "mjpeg-large", False
    if container_token in CONTAINER_STRESS_EXTENSIONS:
        return "container-stress", False
    if video in DIRECT_VIDEO_CODECS:
        return "h264-h265-direct", False
    if video in MODERN_VIDEO_CODECS:
        return "av1-vp-modern", False
    if video in LEGACY_VIDEO_CODECS:
        return "legacy-video", False
    return "legacy-video", True


def diagnostic_bucket(sample: TdarrSample) -> str:
    bucket, _is_fallback = classify_bucket(sample.medium, sample.video_codec, sample.container)
    return bucket


def case_id(index: int) -> str:
    return f"tdarr-{index:04d}"


def movie_relative_path(index: int, sample: TdarrSample) -> Path:
    bucket = diagnostic_bucket(sample)
    resolution, video, audio, container = display_tokens(sample)
    suffix = Path(sample.name).suffix
    stem = f"Fake Title {index:04d} (2026) [Tdarr {resolution} {video} {audio} {container} {case_id(index)}]"
    return Path("source") / "Movies" / bucket / f"{stem}{suffix}"


def tv_relative_path(index: int, sample: TdarrSample) -> Path:
    bucket = diagnostic_bucket(sample)
    series = BUCKET_SERIES[bucket]
    season = ((index - 1) // 100) + 1
    episode = ((index - 1) % 100) + 1
    resolution, video, audio, container = display_tokens(sample)
    suffix = Path(sample.name).suffix
    stem = (
        f"{series} - S{season:02d}E{episode:02d} - "
        f"Fake Episode [Tdarr {resolution} {video} {audio} {container} {case_id(index)}]"
    )
    return Path("source") / "TV" / series / f"Season {season:02d}" / f"{stem}{suffix}"


def load_inventory(path: Path) -> list[TdarrSample]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = [
            TdarrSample(
                name=str(row.get("name") or ""),
                local_path=str(row.get("local_path") or ""),
                source_url=str(row.get("source_url") or ""),
                source_page=str(row.get("source_page") or ""),
                medium=str(row.get("medium") or ""),
                container=str(row.get("container") or ""),
                resolution=str(row.get("resolution") or ""),
                video_codec=str(row.get("video_codec") or ""),
                audio_codec=str(row.get("audio_codec") or ""),
                duration=str(row.get("duration") or ""),
                advertised_size_mb=str(row.get("advertised_size_mb") or ""),
                actual_size_bytes=str(row.get("actual_size_bytes") or ""),
                sha256=str(row.get("sha256") or ""),
                video_decodable=str(row.get("video_decodable") or ""),
            )
            for row in reader
        ]
    if not rows:
        raise ValueError(f"Inventory has no rows: {path}")
    missing = [sample.name for sample in rows if not sample.name or not sample.local_path]
    if missing:
        raise ValueError(f"Inventory rows are missing name/local_path: {missing[:5]}")
    return rows


def parse_views(value: str) -> tuple[str, ...]:
    views = tuple(part.strip().casefold() for part in value.split(",") if part.strip())
    allowed = {"movies", "tv"}
    invalid = [view for view in views if view not in allowed]
    if invalid:
        raise ValueError(f"Unsupported view(s): {', '.join(invalid)}")
    if not views:
        raise ValueError("At least one view is required.")
    return views


def path_has_link_component(path: Path) -> bool:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if not current.exists() and not current.is_symlink():
            continue
        is_junction = bool(getattr(current, "is_junction", lambda: False)())
        file_attributes = int(getattr(current.lstat(), "st_file_attributes", 0))
        is_reparse_point = bool(file_attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)))
        if current.is_symlink() or is_junction or is_reparse_point:
            return True
    return False


def library_root_path_identity(library_root: Path) -> str:
    normalized = os.path.normcase(str(library_root.resolve()))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def library_root_identity_payload(library_root: Path) -> dict[str, str]:
    return {
        "schema_version": LIBRARY_ROOT_IDENTITY_SCHEMA,
        "purpose": LIBRARY_ROOT_PURPOSE,
        "library_root_sha256": library_root_path_identity(library_root),
        "build_nonce": str(uuid.uuid4()),
    }


def validate_library_root_sentinel(library_root: Path) -> dict[str, object]:
    sentinel_path = library_root / SENTINEL_NAME
    try:
        payload = json.loads(sentinel_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Tdarr library sentinel is unreadable or malformed: {sentinel_path}") from exc
    identity = payload.get("root_identity")
    if not isinstance(identity, dict):
        raise ValueError(f"Tdarr library sentinel has no root identity: {sentinel_path}")
    expected = {
        "schema_version": LIBRARY_ROOT_IDENTITY_SCHEMA,
        "purpose": LIBRARY_ROOT_PURPOSE,
        "library_root_sha256": library_root_path_identity(library_root),
    }
    for key, value in expected.items():
        if identity.get(key) != value:
            raise ValueError(f"Tdarr library sentinel {key} does not match this root: {sentinel_path}")
    try:
        nonce = uuid.UUID(str(identity.get("build_nonce", "")))
    except ValueError as exc:
        raise ValueError(f"Tdarr library sentinel build_nonce is invalid: {sentinel_path}") from exc
    if nonce.int == 0:
        raise ValueError(f"Tdarr library sentinel build_nonce is invalid: {sentinel_path}")
    if payload.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError(f"Tdarr library sentinel schema does not match: {sentinel_path}")
    if Path(str(payload.get("library_root", ""))).resolve() != library_root.resolve():
        raise ValueError(f"Tdarr library sentinel path does not match this root: {sentinel_path}")
    return payload


def assert_allowed_library_root(library_root: Path, *, repo_root: Path) -> Path:
    original = library_root if library_root.is_absolute() else repo_root / library_root
    if path_has_link_component(original):
        raise ValueError(f"Library root must not contain a symlink or junction component: {original}")
    resolved = original.resolve()
    allowed_root = (repo_root / "LocalBase" / "Scratch" / "TestLibraries").resolve()
    try:
        relative = resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(f"Library root must be under {allowed_root}") from exc
    if not relative.parts:
        raise ValueError(f"Library root must be a tool-owned child of {allowed_root}, not the shared parent")
    if len(relative.parts) != 1 or not relative.name.casefold().startswith(LIBRARY_ROOT_PREFIX):
        raise ValueError(f"Library root must be a direct TdarrMatrix* child of {allowed_root}")
    return resolved


def prepare_library_root(library_root: Path, *, repo_root: Path, rebuild: bool) -> dict[str, object]:
    library_root = assert_allowed_library_root(library_root, repo_root=repo_root)
    sentinel = library_root / SENTINEL_NAME
    existing_children = list(library_root.iterdir()) if library_root.exists() else []
    if existing_children and not rebuild:
        raise FileExistsError(f"{library_root} already has content; pass --rebuild to regenerate it.")
    if existing_children and rebuild and not sentinel.exists():
        raise FileExistsError(f"{library_root} has no {SENTINEL_NAME}; refusing destructive rebuild.")
    quarantine_root: Path | None = None
    if existing_children and rebuild:
        validate_library_root_sentinel(library_root)
        suffix = f"{datetime.now(UTC):%Y%m%d_%H%M%S}.{uuid.uuid4().hex}"
        quarantine_root = library_root.with_name(f"{library_root.name}.replaced.{suffix}")
        if quarantine_root.exists():
            raise FileExistsError(f"Tdarr library quarantine already exists: {quarantine_root}")
        library_root.rename(quarantine_root)
    library_root.mkdir(parents=True, exist_ok=True)
    return {"quarantine_root": quarantine_root}


def restore_library_root_after_failure(library_root: Path, quarantine_root: Path) -> Path | None:
    failed_root: Path | None = None
    if library_root.exists():
        suffix = f"{datetime.now(UTC):%Y%m%d_%H%M%S}.{uuid.uuid4().hex}"
        failed_root = library_root.with_name(f"{library_root.name}.failed.{suffix}")
        library_root.rename(failed_root)
    quarantine_root.rename(library_root)
    return failed_root


def materialized_rows(
    samples: list[TdarrSample],
    *,
    inventory_root: Path,
    library_root: Path,
    views: tuple[str, ...],
) -> list[MaterializedRow]:
    rows: list[MaterializedRow] = []
    for index, sample in enumerate(samples, start=1):
        source_path = resolve_inventory_local_path(sample.local_path, inventory_root=inventory_root)
        if not source_path.exists():
            raise FileNotFoundError(f"Source sample is missing: {source_path}")
        if "movies" in views:
            rows.append(
                MaterializedRow(
                    view="movies",
                    case_id=case_id(index),
                    bucket=diagnostic_bucket(sample),
                    generated_path=library_root / movie_relative_path(index, sample),
                    source_path=source_path,
                    sample=sample,
                )
            )
        if "tv" in views:
            rows.append(
                MaterializedRow(
                    view="tv",
                    case_id=case_id(index),
                    bucket=diagnostic_bucket(sample),
                    generated_path=library_root / tv_relative_path(index, sample),
                    source_path=source_path,
                    sample=sample,
                )
            )
    return rows


def link_or_copy(source: Path, destination: Path, *, mode: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Generated target already exists: {destination}")
    if mode == "copy":
        shutil.copy2(source, destination)
        return
    os.link(source, destination)


def manifest_record(row: MaterializedRow, *, library_root: Path) -> dict[str, str]:
    sample = row.sample
    return {
        "schema_version": MANIFEST_SCHEMA,
        "view": row.view,
        "case_id": row.case_id,
        "diagnostic_bucket": row.bucket,
        "generated_path": str(row.generated_path.relative_to(library_root)).replace("\\", "/"),
        "source_path": str(row.source_path),
        "original_name": sample.name,
        "source_url": sample.source_url,
        "source_page": sample.source_page,
        "medium": sample.medium,
        "container": sample.container,
        "resolution": sample.resolution,
        "video_codec": sample.video_codec,
        "audio_codec": sample.audio_codec,
        "duration": sample.duration,
        "advertised_size_mb": sample.advertised_size_mb,
        "actual_size_bytes": sample.actual_size_bytes,
        "sha256": sample.sha256,
    }


def write_manifest(library_root: Path, rows: list[MaterializedRow], *, mode: str) -> None:
    manifest_dir = library_root / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    records = [manifest_record(row, library_root=library_root) | {"link_mode": mode} for row in rows]
    fieldnames = list(records[0].keys()) if records else []
    with (manifest_dir / "materialized_library.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    payload = {
        "schema_version": MANIFEST_SCHEMA,
        "generated_at_utc": utc_now(),
        "library_root": str(library_root),
        "link_mode": mode,
        "count": len(records),
        "files": records,
    }
    (manifest_dir / "materialized_library.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def replace_psd1_key(text: str, key: str, rendered_value: str) -> str:
    pattern = re.compile(rf"^(\s*){re.escape(key)}\s*=.*$", re.MULTILINE)
    updated, count = pattern.subn(lambda match: f"{match.group(1)}{key} = {rendered_value}", text)
    if count == 0:
        raise ValueError(f"Config template is missing key: {key}")
    return updated


def render_library_profiles(source_movies: Path, source_tv: Path, output_root: Path) -> str:
    movie_output = output_root / "Movies"
    tv_output = output_root / "TV"
    return "\n".join(
        [
            "    LibraryProfiles = @(",
            "        @{",
            "            id = 'movies'",
            "            name = 'Tdarr Matrix Movies'",
            "            enabled = $true",
            "            designation = 'movie'",
            f"            source_path = {ps_quote(source_movies)}",
            f"            output_path = {ps_quote(movie_output)}",
            "            promotion_enabled = $false",
            "            promotion_destination = ''",
            "            overrides = @{}",
            "        },",
            "        @{",
            "            id = 'tv'",
            "            name = 'Tdarr Matrix TV'",
            "            enabled = $true",
            "            designation = 'tv'",
            f"            source_path = {ps_quote(source_tv)}",
            f"            output_path = {ps_quote(tv_output)}",
            "            promotion_enabled = $false",
            "            promotion_destination = ''",
            "            overrides = @{}",
            "        }",
            "    )",
        ]
    )


def render_config(template_path: Path, library_root: Path) -> str:
    text = template_path.read_text(encoding="utf-8")
    source_movies = library_root / "source" / "Movies"
    source_tv = library_root / "source" / "TV"
    output_root = library_root / "output"
    scratch_root = library_root / "scratch"
    replacements = {
        "SourceMovies": ps_quote(source_movies),
        "SourceTV": ps_quote(source_tv),
        "Outsource": ps_quote(output_root),
        "LocalBase": ps_quote(scratch_root),
        "FinalLibraryPromotionEnabled": ps_bool(False),
        "FinalLibraryPromotionRules": "@()",
        "FinalLibraryPromotionCleanupAfterVerified": ps_bool(False),
        "FinalLibraryPromotionOverwriteExisting": ps_bool(False),
        "OutputContainer": ps_quote("mkv"),
        "DynamicHdrPolicy": ps_quote("preserve_or_review"),
        "EncodeLadder": ps_quote("auto"),
        "ValidExtensions": ps_array(VALID_EXTENSIONS),
    }
    for key, rendered_value in replacements.items():
        text = replace_psd1_key(text, key, rendered_value)
    profiles = render_library_profiles(source_movies, source_tv, output_root)
    if "LibraryProfiles" in text:
        text = replace_psd1_key(text, "LibraryProfiles", profiles.strip())
    else:
        text = re.sub(
            r"^(\s*)LocalBase\s*=.*$",
            lambda match: f"{match.group(0)}\n{profiles}",
            text,
            count=1,
            flags=re.MULTILINE,
        )
    return text if text.endswith("\n") else text + "\n"


def write_config(template_path: Path, library_root: Path) -> Path:
    config_dir = library_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / CONFIG_NAME
    config_path.write_text(render_config(template_path, library_root), encoding="utf-8", newline="\n")
    return config_path


def write_sentinel(
    library_root: Path,
    *,
    inventory_path: Path,
    mode: str,
    views: tuple[str, ...],
    materialized_count: int,
) -> None:
    payload = {
        "schema_version": MANIFEST_SCHEMA,
        "generated_at_utc": utc_now(),
        "inventory_path": str(inventory_path),
        "link_mode": mode,
        "views": list(views),
        "materialized_count": materialized_count,
        "library_root": str(library_root.resolve()),
        "root_identity": library_root_identity_payload(library_root),
    }
    (library_root / SENTINEL_NAME).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def is_quarantined_sample(sample: TdarrSample) -> bool:
    """A sample is quarantined when the inventory marks its video as undecodable.

    ``video_decodable == "false"`` means ffprobe found a declared video stream
    that carries no decodable packets (a header-only/partial source). Linking
    such a file into the test library only manufactures guaranteed encode
    failures, so it is skipped. Any absent/empty/other value (e.g. "true",
    "n/a", "unknown") is treated as include, keeping older inventories that
    predate the column fully backward compatible.
    """
    return str(sample.video_decodable).strip().casefold() == "false"


def partition_quarantined_samples(
    samples: list[TdarrSample],
) -> tuple[list[TdarrSample], list[TdarrSample]]:
    included: list[TdarrSample] = []
    quarantined: list[TdarrSample] = []
    for sample in samples:
        (quarantined if is_quarantined_sample(sample) else included).append(sample)
    return included, quarantined


def materialize(
    *,
    inventory_path: Path,
    library_root: Path,
    repo_root: Path = REPO_ROOT,
    mode: str = "hardlink",
    views: tuple[str, ...] = ("movies", "tv"),
    rebuild: bool = False,
    write_config_file: bool = False,
    template_path: Path = DEFAULT_TEMPLATE,
) -> dict[str, object]:
    if mode not in {"hardlink", "copy"}:
        raise ValueError("mode must be hardlink or copy")
    repo_root = repo_root.resolve()
    inventory_path = resolve_repo_path(inventory_path, repo_root=repo_root)
    library_root = assert_allowed_library_root(Path(library_root), repo_root=repo_root)
    template_path = resolve_repo_path(template_path, repo_root=repo_root)
    inventory_root = inventory_path.parent

    all_samples = load_inventory(inventory_path)
    samples, quarantined = partition_quarantined_samples(all_samples)
    rows = materialized_rows(samples, inventory_root=inventory_root, library_root=library_root, views=views)
    state = prepare_library_root(library_root, repo_root=repo_root, rebuild=rebuild)
    quarantine_root = state.get("quarantine_root")
    try:
        for path in (
            library_root / "output" / "Movies",
            library_root / "output" / "TV",
            library_root / "scratch",
            library_root / "config",
            library_root / "manifests",
        ):
            path.mkdir(parents=True, exist_ok=True)
        for row in rows:
            link_or_copy(row.source_path, row.generated_path, mode=mode)

        write_manifest(library_root, rows, mode=mode)
        config_path = write_config(template_path, library_root) if write_config_file else None
        write_sentinel(
            library_root,
            inventory_path=inventory_path,
            mode=mode,
            views=views,
            materialized_count=len(rows),
        )
        return {
            "library_root": str(library_root),
            "inventory_path": str(inventory_path),
            "mode": mode,
            "views": list(views),
            "samples": len(all_samples),
            "quarantined_samples": len(quarantined),
            "materialized_files": len(rows),
            "manifest_csv": str(library_root / "manifests" / "materialized_library.csv"),
            "manifest_json": str(library_root / "manifests" / "materialized_library.json"),
            "config_path": str(config_path) if config_path else "",
            "quarantine_root": str(quarantine_root) if isinstance(quarantine_root, Path) else "",
        }
    except Exception:
        if isinstance(quarantine_root, Path) and quarantine_root.exists():
            restore_library_root_after_failure(library_root, quarantine_root)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize Tdarr samples as Movies/TV test libraries.")
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--library-root", default=str(DEFAULT_LIBRARY_ROOT))
    parser.add_argument("--mode", choices=("hardlink", "copy"), default="hardlink")
    parser.add_argument("--views", default="movies,tv")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--write-config", action="store_true")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = materialize(
        inventory_path=Path(args.inventory),
        library_root=Path(args.library_root),
        mode=args.mode,
        views=parse_views(args.views),
        rebuild=args.rebuild,
        write_config_file=args.write_config,
        template_path=Path(args.template),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
