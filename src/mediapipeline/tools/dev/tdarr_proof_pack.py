"""Build and clean up the durable Tdarr proof pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import uuid
from dataclasses import replace
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
from collections.abc import Sequence

from mediapipeline.core.diagnostics.tdarr_matrix_proof import (
    TDARR_PROOF_PACK_SCHEMA_VERSION,
    TDARR_PROOF_PACK_SENTINEL,
    tdarr_case_ids_for_pack,
    tdarr_expected_manifest_count,
    tdarr_expected_source_count,
    tdarr_legacy_cleanup_targets,
    tdarr_proof_pack_root,
)
from mediapipeline.tools.dev import materialize_tdarr_test_library as materializer
from mediapipeline.tools.dev import tdarr_matrix_audit
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
DEFAULT_SOURCE_LIBRARY_ROOT = Path("E:/Videos/TdarrMatrix/TestLibraries/TdarrMatrix")
DEFAULT_TEMPLATE = materializer.DEFAULT_TEMPLATE
PROOF_CASES_NAME = "proof_pack_cases.json"
PASS_HISTORY_NAME = "pass_history.json"
ARCHIVE_MANIFEST_NAME = "full_matrix_archive_manifest.json"
PROOF_ROOT_IDENTITY_SCHEMA = "mediapipeline_tdarr_proof_root_identity.v1"
PROOF_ROOT_PURPOSE = "mediapipeline_tdarr_proof_pack"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def resolve_path(value: str | Path, *, repo_root: Path = REPO_ROOT) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve(strict=False)


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


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


def proof_root_path_identity(path: Path) -> str:
    normalized = os.path.normcase(str(resolve_path(path)))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def assert_proof_root_allowed(
    proof_root: Path,
    *,
    allowed_test_parent: Path | None = None,
    original_path: Path | None = None,
) -> Path:
    original = Path(original_path if original_path is not None else proof_root)
    if path_has_link_component(original):
        raise ValueError(f"Proof root must not contain a symlink or junction component: {original}")
    resolved = resolve_path(proof_root)
    canonical = resolve_path(tdarr_proof_pack_root(REPO_ROOT))
    if resolved == canonical:
        return resolved
    if allowed_test_parent is None:
        raise ValueError(f"Proof root must equal the canonical Tdarr Proof Pack root: {canonical}")
    allowed = resolve_path(allowed_test_parent)
    if path_has_link_component(Path(allowed_test_parent)):
        raise ValueError(f"Allowed disposable proof parent must not contain a symlink or junction component: {allowed_test_parent}")
    if resolved == allowed or not is_under(resolved, allowed):
        raise ValueError(f"Disposable proof root must be a child of the allowed test parent: {allowed}")
    return resolved


def proof_root_identity_payload(proof_root: Path) -> dict[str, str]:
    return {
        "schema_version": PROOF_ROOT_IDENTITY_SCHEMA,
        "purpose": PROOF_ROOT_PURPOSE,
        "proof_root_sha256": proof_root_path_identity(proof_root),
        "build_nonce": str(uuid.uuid4()),
    }


def validate_proof_root_sentinel(proof_root: Path) -> dict[str, Any]:
    sentinel_path = proof_root / TDARR_PROOF_PACK_SENTINEL
    try:
        payload = json.loads(sentinel_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Proof root sentinel is unreadable or malformed: {sentinel_path}") from exc
    identity = payload.get("root_identity")
    if not isinstance(identity, dict):
        raise ValueError(f"Proof root sentinel has no root identity: {sentinel_path}")
    expected = {
        "schema_version": PROOF_ROOT_IDENTITY_SCHEMA,
        "purpose": PROOF_ROOT_PURPOSE,
        "proof_root_sha256": proof_root_path_identity(proof_root),
    }
    for key, value in expected.items():
        if identity.get(key) != value:
            raise ValueError(f"Proof root sentinel {key} does not match this root: {sentinel_path}")
    try:
        nonce = uuid.UUID(str(identity.get("build_nonce", "")))
    except ValueError as exc:
        raise ValueError(f"Proof root sentinel build_nonce is invalid: {sentinel_path}") from exc
    if nonce.int == 0:
        raise ValueError(f"Proof root sentinel build_nonce is invalid: {sentinel_path}")
    if payload.get("schema_version") != TDARR_PROOF_PACK_SCHEMA_VERSION:
        raise ValueError(f"Proof root sentinel schema does not match: {sentinel_path}")
    if resolve_path(payload.get("proof_root", "")) != resolve_path(proof_root):
        raise ValueError(f"Proof root sentinel path does not match this root: {sentinel_path}")
    return payload


def source_manifest_candidates(workspace_root: Path) -> tuple[Path, ...]:
    return (
        DEFAULT_SOURCE_LIBRARY_ROOT / "manifests" / "materialized_library.csv",
        workspace_root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix" / "manifests" / "materialized_library.csv",
    )


def default_source_manifest(workspace_root: Path) -> Path:
    for candidate in source_manifest_candidates(workspace_root):
        if candidate.exists():
            return candidate
    return source_manifest_candidates(workspace_root)[0]


def manifest_case_id_number(case_id: str) -> int:
    text = str(case_id or "").strip().split("-")[-1]
    try:
        return int(text)
    except ValueError:
        return 0


def proof_cache_relative_path(row: tdarr_matrix_audit.ManifestRow) -> Path:
    name = Path(row.original_name or row.source_path.name).name
    if not name:
        name = f"{row.case_id}.media"
    return Path("cache") / "files" / row.case_id / name


def proof_pack_case_metadata(rows: Sequence[tdarr_matrix_audit.ManifestRow]) -> list[dict[str, Any]]:
    by_case: dict[str, tdarr_matrix_audit.ManifestRow] = {}
    for row in rows:
        by_case.setdefault(row.case_id, row)
    records: list[dict[str, Any]] = []
    for case_id in sorted(by_case, key=manifest_case_id_number):
        row = by_case[case_id]
        records.append(
            {
                "case_id": row.case_id,
                "diagnostic_bucket": row.diagnostic_bucket,
                "resolution": row.resolution,
                "video_codec": row.video_codec,
                "audio_codec": row.audio_codec,
                "container": row.container,
                "medium": row.medium,
                "sha256": row.sha256,
                "source_url": row.source_url,
                "expected_outcome": "structured_result_no_source_mutation",
            }
        )
    return records


def load_source_manifest_rows(source_manifest: Path) -> tuple[Path, list[tdarr_matrix_audit.ManifestRow]]:
    source_library_root = source_manifest.parent.parent
    rows = tdarr_matrix_audit.load_manifest_rows(source_manifest, library_root=source_library_root)
    if not rows:
        raise ValueError(f"Source manifest has no rows: {source_manifest}")
    return source_library_root, rows


def select_proof_rows(rows: Sequence[tdarr_matrix_audit.ManifestRow]) -> list[tdarr_matrix_audit.ManifestRow]:
    wanted = set(tdarr_case_ids_for_pack("proof-pack"))
    selected = [row for row in rows if row.case_id in wanted and row.view in {"movies", "tv"}]
    found = {row.case_id for row in selected}
    missing = sorted(wanted - found, key=manifest_case_id_number)
    if missing:
        raise ValueError(f"Proof Pack case IDs missing from source manifest: {', '.join(missing)}")
    return sorted(selected, key=lambda row: (manifest_case_id_number(row.case_id), row.view))


def prepare_proof_root(
    proof_root: Path,
    *,
    rebuild: bool,
    allowed_test_parent: Path | None = None,
) -> dict[str, Any]:
    proof_root = assert_proof_root_allowed(
        proof_root,
        allowed_test_parent=allowed_test_parent,
        original_path=proof_root,
    )
    sentinel = proof_root / TDARR_PROOF_PACK_SENTINEL
    existing_children = list(proof_root.iterdir()) if proof_root.exists() else []
    if existing_children and not sentinel.exists():
        raise FileExistsError(f"{proof_root} has no {TDARR_PROOF_PACK_SENTINEL}; refusing to reuse it.")
    if existing_children and not rebuild:
        return {"already_exists": True}
    quarantine_root: Path | None = None
    if existing_children and rebuild:
        validate_proof_root_sentinel(proof_root)
        suffix = f"{datetime.now(UTC):%Y%m%d_%H%M%S}.{uuid.uuid4().hex}"
        quarantine_root = proof_root.with_name(f"{proof_root.name}.replaced.{suffix}")
        if quarantine_root.exists():
            raise FileExistsError(f"Proof root quarantine already exists: {quarantine_root}")
        proof_root.rename(quarantine_root)
    proof_root.mkdir(parents=True, exist_ok=True)
    return {"already_exists": False, "quarantine_root": quarantine_root}


def restore_proof_root_after_failure(proof_root: Path, quarantine_root: Path) -> Path | None:
    failed_root: Path | None = None
    if proof_root.exists():
        suffix = f"{datetime.now(UTC):%Y%m%d_%H%M%S}.{uuid.uuid4().hex}"
        failed_root = proof_root.with_name(f"{proof_root.name}.failed.{suffix}")
        proof_root.rename(failed_root)
    quarantine_root.rename(proof_root)
    return failed_root


def link_or_copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def copy_source_to_cache(row: tdarr_matrix_audit.ManifestRow, *, proof_root: Path) -> Path:
    source_path = row.source_path
    if not source_path.is_absolute():
        source_path = row.library_root / source_path
    source_path = source_path.resolve(strict=False)
    if not source_path.exists():
        fallback = (row.library_root / row.generated_path).resolve(strict=False)
        if fallback.exists():
            source_path = fallback
    if not source_path.exists():
        raise FileNotFoundError(f"Proof source is missing for {row.case_id}: {row.source_path}")
    destination = proof_root / proof_cache_relative_path(row)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination)
    actual_hash = tdarr_matrix_audit.sha256_file(destination)
    if row.sha256 and actual_hash.casefold() != row.sha256.casefold():
        raise ValueError(f"Copied proof source hash mismatch for {row.case_id}: expected {row.sha256}, got {actual_hash}")
    return destination


def _populate_proof_pack(
    *,
    proof_root: Path,
    source_manifest: Path,
    template_path: Path,
    source_library_root: Path,
    proof_rows: Sequence[tdarr_matrix_audit.ManifestRow],
    quarantine_root: Path | None,
) -> dict[str, Any]:
    by_case: dict[str, tdarr_matrix_audit.ManifestRow] = {}
    for row in proof_rows:
        by_case.setdefault(row.case_id, row)
    cache_paths = {
        case_id: copy_source_to_cache(row, proof_root=proof_root)
        for case_id, row in sorted(by_case.items(), key=lambda item: manifest_case_id_number(item[0]))
    }
    materialized_rows: list[tdarr_matrix_audit.ManifestRow] = []
    link_modes: set[str] = set()
    for row in proof_rows:
        cache_path = cache_paths[row.case_id]
        destination = proof_root / row.generated_path
        link_modes.add(link_or_copy(cache_path, destination))
        materialized_rows.append(
            replace(
                row,
                library_root=proof_root,
                generated_abs=destination,
                source_path=cache_path,
                record={**row.manifest_record(), "source_path": str(cache_path)},
            )
        )
    for path in (
        proof_root / "output" / "Movies",
        proof_root / "output" / "TV",
        proof_root / "scratch",
        proof_root / "config",
        proof_root / "manifests",
        proof_root / "runs",
        proof_root / "archive" / "full-matrix-reports",
    ):
        path.mkdir(parents=True, exist_ok=True)
    tdarr_matrix_audit.write_materialized_manifest(
        proof_root,
        materialized_rows,
        link_mode="hardlink" if link_modes == {"hardlink"} else "mixed",
    )
    config_path = proof_root / "config" / materializer.CONFIG_NAME
    config_path.write_text(materializer.render_config(template_path, proof_root), encoding="utf-8", newline="\n")
    cases_payload = {
        "schema_version": TDARR_PROOF_PACK_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "source_library_root": str(source_library_root),
        "source_manifest": str(source_manifest),
        "proof_root": str(proof_root),
        "source_count": len(by_case),
        "manifest_count": len(materialized_rows),
        "smoke_case_ids": list(tdarr_case_ids_for_pack("smoke-pack")),
        "proof_case_ids": list(tdarr_case_ids_for_pack("proof-pack")),
        "cases": proof_pack_case_metadata(materialized_rows),
    }
    (proof_root / "manifests" / PROOF_CASES_NAME).write_text(
        json.dumps(cases_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    pass_history_path = proof_root / "manifests" / PASS_HISTORY_NAME
    if not pass_history_path.exists():
        pass_history_path.write_text(
            json.dumps({"schema_version": "tdarr_proof_pack_pass_history.v1", "cases": {}}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    sentinel = {
        "schema_version": TDARR_PROOF_PACK_SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "source_manifest": str(source_manifest),
        "proof_root": str(proof_root),
        "source_count": len(by_case),
        "manifest_count": len(materialized_rows),
        "cache_verified": True,
        "link_modes": sorted(link_modes),
        "root_identity": proof_root_identity_payload(proof_root),
    }
    (proof_root / TDARR_PROOF_PACK_SENTINEL).write_text(
        json.dumps(sentinel, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verification = verify_proof_pack(proof_root)
    return {
        "action": "prepare-proof-pack",
        "already_exists": False,
        "config_path": str(config_path),
        "source_library_root": str(source_library_root),
        "source_manifest": str(source_manifest),
        "quarantine_root": str(quarantine_root) if quarantine_root else "",
        **verification,
    }


def materialize_proof_pack(
    *,
    proof_root: Path,
    source_manifest: Path,
    template_path: Path = DEFAULT_TEMPLATE,
    rebuild: bool = False,
    allowed_test_parent: Path | None = None,
) -> dict[str, Any]:
    original_proof_root = Path(proof_root)
    proof_root = assert_proof_root_allowed(
        original_proof_root,
        allowed_test_parent=allowed_test_parent,
        original_path=original_proof_root,
    )
    source_manifest = resolve_path(source_manifest)
    template_path = resolve_path(template_path)
    if proof_root.exists() and not rebuild and (proof_root / TDARR_PROOF_PACK_SENTINEL).exists():
        verification = verify_proof_pack(proof_root)
        if verification["ok"]:
            return {"action": "prepare-proof-pack", "already_exists": True, **verification}
    source_library_root, source_rows = load_source_manifest_rows(source_manifest)
    proof_rows = select_proof_rows(source_rows)
    state = prepare_proof_root(
        proof_root,
        rebuild=rebuild,
        allowed_test_parent=allowed_test_parent,
    )
    if state.get("already_exists"):
        verification = verify_proof_pack(proof_root)
        return {"action": "prepare-proof-pack", "already_exists": True, **verification}
    quarantine_root = state.get("quarantine_root")
    try:
        return _populate_proof_pack(
            proof_root=proof_root,
            source_manifest=source_manifest,
            template_path=template_path,
            source_library_root=source_library_root,
            proof_rows=proof_rows,
            quarantine_root=quarantine_root,
        )
    except Exception:
        if isinstance(quarantine_root, Path) and quarantine_root.exists():
            restore_proof_root_after_failure(proof_root, quarantine_root)
        raise


def verify_proof_pack(proof_root: Path) -> dict[str, Any]:
    proof_root = resolve_path(proof_root)
    sentinel_path = proof_root / TDARR_PROOF_PACK_SENTINEL
    manifest_path = proof_root / "manifests" / "materialized_library.csv"
    errors: list[str] = []
    if not sentinel_path.exists():
        errors.append(f"Missing proof sentinel: {sentinel_path}")
    else:
        try:
            validate_proof_root_sentinel(proof_root)
        except ValueError as exc:
            errors.append(str(exc))
    if not manifest_path.exists():
        errors.append(f"Missing proof manifest: {manifest_path}")
        return {"ok": False, "proof_root": str(proof_root), "errors": errors, "source_count": 0, "manifest_count": 0}
    rows = tdarr_matrix_audit.load_manifest_rows(manifest_path, library_root=proof_root)
    source_cases = {row.case_id for row in rows}
    if len(source_cases) != tdarr_expected_source_count("proof-pack"):
        errors.append(f"Expected {tdarr_expected_source_count('proof-pack')} proof sources, found {len(source_cases)}")
    if len(rows) != tdarr_expected_manifest_count("proof-pack"):
        errors.append(f"Expected {tdarr_expected_manifest_count('proof-pack')} proof manifest rows, found {len(rows)}")
    hash_mismatches: list[str] = []
    missing_files: list[str] = []
    for row in rows:
        for label, path in (("cache", row.source_path), ("generated", row.generated_abs)):
            if not path.exists():
                missing_files.append(f"{row.case_id}:{row.view}:{label}:{path}")
                continue
            actual = tdarr_matrix_audit.sha256_file(path)
            if row.sha256 and actual.casefold() != row.sha256.casefold():
                hash_mismatches.append(f"{row.case_id}:{row.view}:{label}")
    if missing_files:
        errors.append(f"Missing proof files: {len(missing_files)}")
    if hash_mismatches:
        errors.append(f"Proof hash mismatches: {len(hash_mismatches)}")
    return {
        "ok": not errors,
        "proof_root": str(proof_root),
        "sentinel_path": str(sentinel_path),
        "manifest_csv": str(manifest_path),
        "source_count": len(source_cases),
        "manifest_count": len(rows),
        "expected_source_count": tdarr_expected_source_count("proof-pack"),
        "expected_manifest_count": tdarr_expected_manifest_count("proof-pack"),
        "missing_file_count": len(missing_files),
        "hash_mismatch_count": len(hash_mismatches),
        "errors": errors,
    }


def path_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def is_directory_link(path: Path) -> bool:
    isjunction = getattr(os.path, "isjunction", None)
    try:
        attrs = int(getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0) or 0)
    except OSError:
        attrs = 0
    reparse = bool(attrs & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)))
    return bool(path.is_symlink() or (callable(isjunction) and isjunction(path)) or reparse)


def cleanup_target_rows(workspace_root: Path, *, proof_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, path in tdarr_legacy_cleanup_targets(workspace_root).items():
        rows.append(
            {
                "name": name,
                "path": str(path),
                "exists": path.exists(),
                "size_bytes": path_size_bytes(path),
                "eligible": cleanup_target_is_eligible(name, path, workspace_root=workspace_root),
            }
        )
    return rows


def cleanup_target_is_eligible(name: str, path: Path, *, workspace_root: Path) -> bool:
    if not path.exists():
        return True
    if name == "legacy_matrix_library":
        return (path / materializer.SENTINEL_NAME).exists()
    if name == "legacy_matrix_runs":
        if path.name != "TdarrMatrixRuns" or path.parent.name != "TestLibraries":
            return False
        children = [child for child in path.iterdir() if child.name != "_background"]
        return all((child / tdarr_matrix_audit.AUDIT_RUN_SENTINEL).exists() for child in children if child.is_dir())
    if name == "legacy_download_cache":
        expected = workspace_root / "LocalBase" / "TestFixtures" / "TdarrSamples"
        return path.resolve(strict=False) == expected.resolve(strict=False) and (path / "inventory.csv").exists()
    return False


def archive_full_matrix_reports(*, workspace_root: Path, proof_root: Path) -> dict[str, Any]:
    verification = verify_proof_pack(proof_root)
    if not verification["ok"]:
        raise ValueError("Proof Pack must verify before full-matrix evidence can be archived.")
    archive_root = proof_root / "archive" / "full-matrix-reports"
    archive_root.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, str]] = []
    targets = tdarr_legacy_cleanup_targets(workspace_root)
    matrix_manifest_root = targets["legacy_matrix_library"] / "manifests"
    for pattern in ("materialized_library.csv", "materialized_library.json", "audit/*.json", "audit/*.md", "audit/*.csv"):
        for source in matrix_manifest_root.glob(pattern):
            if source.is_file():
                destination = archive_root / "library" / source.relative_to(matrix_manifest_root)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                copied.append({"source": str(source), "destination": str(destination)})
    runs_root = targets["legacy_matrix_runs"]
    if runs_root.exists():
        for run_root in sorted(child for child in runs_root.iterdir() if child.is_dir() and child.name != "_background"):
            for relative in (
                Path(tdarr_matrix_audit.AUDIT_RUN_SENTINEL),
                Path("manifests") / "materialized_library.csv",
                Path("manifests") / "audit" / "tdarr_matrix_audit_report.json",
                Path("manifests") / "audit" / "tdarr_matrix_audit_summary.md",
                Path("manifests") / "audit" / "tdarr_matrix_findings.csv",
            ):
                source = run_root / relative
                if source.is_file():
                    destination = archive_root / "runs" / run_root.name / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                    copied.append({"source": str(source), "destination": str(destination)})
    manifest = {
        "schema_version": "tdarr_full_matrix_archive.v1",
        "generated_at_utc": utc_now(),
        "proof_root": str(proof_root),
        "copied_count": len(copied),
        "copied": copied,
    }
    manifest_path = archive_root / ARCHIVE_MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "action": "cleanup-archive",
        "ok": True,
        "proof_root": str(proof_root),
        "archive_root": str(archive_root),
        "archive_manifest": str(manifest_path),
        "copied_count": len(copied),
    }


def cleanup_plan(*, workspace_root: Path, proof_root: Path) -> dict[str, Any]:
    verification = verify_proof_pack(proof_root)
    rows = cleanup_target_rows(workspace_root, proof_root=proof_root)
    total_size = sum(int(row["size_bytes"]) for row in rows if row["exists"])
    archive_manifest = proof_root / "archive" / "full-matrix-reports" / ARCHIVE_MANIFEST_NAME
    return {
        "action": "cleanup-plan",
        "ok": bool(verification["ok"]) and all(bool(row["eligible"]) for row in rows),
        "proof_verification": verification,
        "archive_manifest": str(archive_manifest),
        "archive_exists": archive_manifest.exists(),
        "target_count": len(rows),
        "total_size_bytes": total_size,
        "targets": rows,
        "dry_run": True,
    }


def delete_full_matrix(*, workspace_root: Path, proof_root: Path, confirm_delete: bool) -> dict[str, Any]:
    if not confirm_delete:
        raise ValueError("confirm_delete_full_matrix is required for delete.")
    plan = cleanup_plan(workspace_root=workspace_root, proof_root=proof_root)
    if not plan["ok"]:
        raise ValueError("Cleanup plan is not eligible; proof verification or target guards failed.")
    if not plan["archive_exists"]:
        raise ValueError("Full-matrix evidence archive is required before delete.")
    removed: list[str] = []
    for row in plan["targets"]:
        path = Path(row["path"])
        if not row["exists"]:
            continue
        if not row["eligible"]:
            raise ValueError(f"Cleanup target is not eligible: {path}")
        remove_cleanup_target(str(row["name"]), path, workspace_root=workspace_root)
        removed.append(str(path))
    return {
        "action": "cleanup-delete",
        "ok": True,
        "proof_root": str(proof_root),
        "removed": removed,
        "removed_count": len(removed),
    }


def remove_cleanup_target(name: str, path: Path, *, workspace_root: Path) -> None:
    if name == "legacy_download_cache" and is_directory_link(path):
        resolved = path.resolve(strict=False)
        expected_link = (workspace_root / "LocalBase" / "TestFixtures" / "TdarrSamples").absolute()
        allowed_target = Path("E:/Videos/TdarrMatrix/TestFixtures/TdarrSamples")
        if path.absolute() != expected_link:
            raise ValueError(f"Refusing to remove unexpected Tdarr cache link: {path}")
        if resolved.resolve(strict=False) != allowed_target.resolve(strict=False):
            raise ValueError(f"Refusing to remove unexpected Tdarr cache link target: {resolved}")
        if not (resolved / "inventory.csv").exists():
            raise ValueError(f"Refusing to remove Tdarr cache target without inventory: {resolved}")
        if resolved.exists():
            shutil.rmtree(resolved)
        try:
            path.rmdir()
        except FileNotFoundError:
            pass
        except OSError:
            if path.exists() or path.is_symlink():
                path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()


def command_materialize(args: argparse.Namespace) -> int:
    proof_root = resolve_path(args.proof_root or tdarr_proof_pack_root(REPO_ROOT))
    source_manifest = resolve_path(args.source_manifest or default_source_manifest(REPO_ROOT))
    summary = materialize_proof_pack(
        proof_root=proof_root,
        source_manifest=source_manifest,
        template_path=resolve_path(args.template),
        rebuild=bool(args.rebuild),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("ok") else 1


def command_cleanup(args: argparse.Namespace) -> int:
    proof_root = resolve_path(args.proof_root or tdarr_proof_pack_root(REPO_ROOT))
    action = str(args.action or "plan").strip().casefold().replace("_", "-")
    try:
        if action == "plan":
            summary = cleanup_plan(workspace_root=REPO_ROOT, proof_root=proof_root)
        elif action == "archive":
            summary = archive_full_matrix_reports(workspace_root=REPO_ROOT, proof_root=proof_root)
        elif action == "delete":
            summary = delete_full_matrix(
                workspace_root=REPO_ROOT,
                proof_root=proof_root,
                confirm_delete=bool(args.confirm_delete_full_matrix),
            )
        else:
            raise ValueError("cleanup action must be plan, archive, or delete")
    except Exception as exc:
        summary = {"action": f"cleanup-{action}", "ok": False, "error": str(exc)}
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("ok") else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and clean up the Tdarr Proof Pack.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    materialize_parser = subparsers.add_parser("materialize", help="Create or verify the durable Proof Pack.")
    materialize_parser.add_argument("--proof-root", default=str(tdarr_proof_pack_root(REPO_ROOT)))
    materialize_parser.add_argument("--source-manifest", default="")
    materialize_parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    materialize_parser.add_argument("--rebuild", action="store_true")

    cleanup_parser = subparsers.add_parser("cleanup", help="Plan, archive, or delete the legacy full matrix.")
    cleanup_parser.add_argument("--proof-root", default=str(tdarr_proof_pack_root(REPO_ROOT)))
    cleanup_parser.add_argument("--action", choices=("plan", "archive", "delete"), default="plan")
    cleanup_parser.add_argument("--confirm-delete-full-matrix", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "materialize":
        return command_materialize(args)
    if args.command == "cleanup":
        return command_cleanup(args)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
