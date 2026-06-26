from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from mediapipeline.core.failures.constants import FAILURE_CLEAR_MANIFEST_SCHEMA_VERSION
from mediapipeline.core.failures.file_io import atomic_write_text
from mediapipeline.core.paths.layout import path_boundary_check
from mediapipeline.desktop.models import ResolvedPaths


class FailureCleanupServiceMixin:
    def _failure_workspace_roots(self, resolved: ResolvedPaths) -> list[Path]:
        roots: list[Path] = []
        if resolved.state_root:
            roots.append(resolved.state_root / "Failures")
        elif resolved.local_base:
            roots.append(resolved.local_base / "State" / "Failures")
        if resolved.local_base:
            roots.append(resolved.local_base / "Failed")
        unique: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            key = os.path.normcase(os.path.abspath(str(root)))
            if key not in seen:
                unique.append(root)
                seen.add(key)
        return unique

    def _validate_failure_cleanup_folder(self, folder: Path | None, allowed_roots: list[Path], label: str) -> None:
        if folder is None:
            return
        if not any(self._path_within_root(folder, root) for root in allowed_roots):
            allowed = ", ".join(str(root) for root in allowed_roots) or "<none>"
            raise RuntimeError(f"Refusing to clear {label} outside failure workspace: {folder}. Allowed roots: {allowed}")
        boundary = next(
            (
                path_boundary_check(folder, root, allow_missing_leaf=True, allow_root_target=True)
                for root in allowed_roots
                if self._path_within_root(folder, root)
            ),
            None,
        )
        if boundary is not None and not boundary.ok:
            raise RuntimeError(f"Refusing to clear {label}; unsafe path boundary ({boundary.reason_code}): {folder}")
        if folder.exists() and not folder.is_dir():
            raise RuntimeError(f"Refusing to clear {label}; path is not a directory: {folder}")

    def _failure_clear_manifest_path(self, resolved: ResolvedPaths) -> Path:
        state_root = resolved.state_root or (resolved.local_base / "State" if resolved.local_base else self.app_root / "State")
        manifest_dir = state_root / "Failures" / "ClearManifests"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return manifest_dir / f"failure_clear_{stamp}_{uuid.uuid4().hex[:8]}.json"

    def _failure_clear_manifest_preview_path(self, resolved: ResolvedPaths, *, prefix: str) -> Path:
        state_root = resolved.state_root or (resolved.local_base / "State" if resolved.local_base else self.app_root / "State")
        manifest_dir = state_root / "Failures" / "ClearManifests"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return manifest_dir / f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}.json"

    def _file_manifest_entry(self, path: Path, *, kind: str, pattern: str) -> dict[str, Any]:
        try:
            stat = path.stat()
            size = int(stat.st_size)
            modified_at = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")
        except OSError:
            size = None
            modified_at = ""
        return {
            "kind": kind,
            "pattern": pattern,
            "path": str(path),
            "size_bytes": size,
            "modified_at": modified_at,
        }

    def _write_failure_clear_manifest(self, manifest_path: Path, manifest: dict[str, Any]) -> None:
        manifest["last_update"] = datetime.now().astimezone().isoformat(timespec="seconds")
        atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    def _failure_marker_clear_candidates(
        self,
        resolved: ResolvedPaths,
        marker_paths: list[str] | None = None,
    ) -> tuple[list[tuple[Path, dict[str, Any]]], list[dict[str, Any]], list[str]]:
        markers_dir = resolved.failed_markers_path
        if markers_dir is None:
            return [], [], ["Failure markers path is not resolved."]

        allowed_roots = self._failure_workspace_roots(resolved)
        self._validate_failure_cleanup_folder(markers_dir, allowed_roots, "failure markers")

        raw_paths = [str(item or "").strip() for item in marker_paths or [] if str(item or "").strip()]
        if raw_paths:
            paths = [Path(item) for item in raw_paths]
        else:
            paths = sorted(markers_dir.glob("*.json")) if markers_dir.exists() else []

        candidates: list[tuple[Path, dict[str, Any]]] = []
        skipped: list[dict[str, Any]] = []
        errors: list[str] = []
        seen: set[str] = set()
        for path in paths:
            key = os.path.normcase(os.path.abspath(str(path)))
            if key in seen:
                continue
            seen.add(key)
            entry = self._file_manifest_entry(path, kind="marker", pattern="selected" if raw_paths else "*.json")
            if path.suffix.lower() != ".json":
                entry["reason"] = "not a JSON marker"
                skipped.append(entry)
                continue
            if not self._path_within_root(path, markers_dir):
                entry["reason"] = "outside failure marker folder"
                skipped.append(entry)
                errors.append(f"Refusing marker outside failure marker folder: {path}")
                continue
            boundary = path_boundary_check(path, markers_dir)
            if not boundary.ok:
                entry["reason"] = boundary.reason_code
                skipped.append(entry)
                errors.append(f"Refusing marker with unsafe path boundary ({boundary.reason_code}): {path}")
                continue
            try:
                if not path.exists():
                    entry["reason"] = "missing"
                    skipped.append(entry)
                    errors.append(f"Failure marker does not exist: {path}")
                    continue
                if not path.is_file():
                    entry["reason"] = "not a file"
                    skipped.append(entry)
                    continue
            except OSError as exc:
                message = f"{path}: {exc}"
                entry["reason"] = str(exc)
                skipped.append(entry)
                errors.append(message)
                continue
            candidates.append((path, entry))
        return candidates, skipped, errors

    def _failure_report_archive_candidates(
        self,
        resolved: ResolvedPaths,
    ) -> tuple[list[tuple[Path, dict[str, Any]]], list[dict[str, Any]], list[str]]:
        reports_dir = resolved.failed_reports_path
        if reports_dir is None:
            return [], [], ["Failure reports path is not resolved."]

        allowed_roots = self._failure_workspace_roots(resolved)
        self._validate_failure_cleanup_folder(reports_dir, allowed_roots, "failure reports")

        candidates: list[tuple[Path, dict[str, Any]]] = []
        skipped: list[dict[str, Any]] = []
        errors: list[str] = []
        seen: set[str] = set()
        patterns = ("round_failures_*.json", "round_failures_*.txt")
        for pattern in patterns:
            try:
                paths = sorted(reports_dir.glob(pattern)) if reports_dir.exists() else []
            except OSError as exc:
                errors.append(f"{reports_dir}: {exc}")
                continue
            for path in paths:
                key = os.path.normcase(os.path.abspath(str(path)))
                if key in seen:
                    continue
                seen.add(key)
                entry = self._file_manifest_entry(path, kind="report", pattern=pattern)
                if not self._path_within_root(path, reports_dir):
                    entry["reason"] = "outside failure report folder"
                    skipped.append(entry)
                    errors.append(f"Refusing report outside failure report folder: {path}")
                    continue
                boundary = path_boundary_check(path, reports_dir)
                if not boundary.ok:
                    entry["reason"] = boundary.reason_code
                    skipped.append(entry)
                    errors.append(f"Refusing report with unsafe path boundary ({boundary.reason_code}): {path}")
                    continue
                try:
                    if not path.exists():
                        entry["reason"] = "missing"
                        skipped.append(entry)
                        errors.append(f"Failure report does not exist: {path}")
                        continue
                    if not path.is_file():
                        entry["reason"] = "not a file"
                        skipped.append(entry)
                        continue
                except OSError as exc:
                    message = f"{path}: {exc}"
                    entry["reason"] = str(exc)
                    skipped.append(entry)
                    errors.append(message)
                    continue
                candidates.append((path, entry))
        return candidates, skipped, errors

    def _failure_archive_fingerprint(
        self,
        *,
        scope: str,
        include_markers: bool,
        include_reports: bool,
        planned: list[dict[str, Any]],
    ) -> str:
        fingerprint_payload = {
            "schema_version": "failure_evidence_archive_fingerprint.v1",
            "scope": scope,
            "include_markers": include_markers,
            "include_reports": include_reports,
            "planned": sorted(
                [
                    {
                        "kind": entry.get("kind"),
                        "path": entry.get("path"),
                        "size_bytes": entry.get("size_bytes"),
                        "modified_at": entry.get("modified_at"),
                    }
                    for entry in planned
                ],
                key=lambda item: (str(item.get("kind") or ""), str(item.get("path") or "")),
            ),
        }
        encoded = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def clear_failure_markers(
        self,
        resolved: ResolvedPaths,
        *,
        marker_paths: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if not resolved.local_base:
            raise RuntimeError("LocalBase is not resolved; failure markers cannot be cleared.")

        candidates, skipped, errors = self._failure_marker_clear_candidates(resolved, marker_paths)
        planned = [entry for _path, entry in candidates]
        result: dict[str, Any] = {
            "schema_version": "failure_marker_clear_result.v1",
            "markers": 0,
            "planned": planned,
            "skipped": skipped,
            "errors": errors,
            "dry_run": bool(dry_run),
            "manifest_path": "",
            "archive_dir": "",
        }
        if dry_run:
            return result
        if errors:
            return result

        manifest_path = self._failure_clear_manifest_path(resolved)
        archive_dir = manifest_path.parent / "ClearedMarkers" / manifest_path.stem
        archive_dir.mkdir(parents=True, exist_ok=True)
        result["manifest_path"] = str(manifest_path)
        result["archive_dir"] = str(archive_dir)
        manifest: dict[str, Any] = {
            "schema_version": FAILURE_CLEAR_MANIFEST_SCHEMA_VERSION,
            "operation": "clear_failure_markers",
            "status": "planned",
            "dry_run": False,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "local_base": str(resolved.local_base),
            "allowed_roots": [str(root) for root in self._failure_workspace_roots(resolved)],
            "manifest_path": str(manifest_path),
            "archive_dir": str(archive_dir),
            "planned": planned,
            "moved": [],
            "skipped": skipped,
            "errors": [],
        }
        self._write_failure_clear_manifest(manifest_path, manifest)

        for path, entry in candidates:
            destination = archive_dir / path.name
            if destination.exists():
                destination = archive_dir / f"{path.stem}_{uuid.uuid4().hex[:8]}{path.suffix}"
            moved_entry = dict(entry)
            moved_entry["archive_path"] = str(destination)
            try:
                path.replace(destination)
                result["markers"] += 1
                manifest["moved"].append(moved_entry)
            except OSError as exc:
                message = f"{path}: {exc}"
                result["errors"].append(message)
                manifest["errors"].append(message)
        manifest["status"] = "completed_with_errors" if manifest["errors"] else "completed"
        self._write_failure_clear_manifest(manifest_path, manifest)
        return result

    def archive_failure_evidence(
        self,
        resolved: ResolvedPaths,
        *,
        scope: str = "all_active",
        include_markers: bool = True,
        include_reports: bool = True,
        dry_run: bool = False,
        dry_run_fingerprint: str = "",
        reason: str = "",
    ) -> dict[str, Any]:
        if not resolved.local_base:
            raise RuntimeError("LocalBase is not resolved; failure evidence cannot be archived.")
        if scope != "all_active":
            raise RuntimeError("Failure evidence archive scope must be all_active.")
        if not include_markers and not include_reports:
            raise RuntimeError("Failure evidence archive requires include_markers or include_reports.")

        candidates: list[tuple[Path, dict[str, Any]]] = []
        skipped: list[dict[str, Any]] = []
        errors: list[str] = []
        if include_markers:
            marker_candidates, marker_skipped, marker_errors = self._failure_marker_clear_candidates(resolved)
            candidates.extend(marker_candidates)
            skipped.extend(marker_skipped)
            errors.extend(marker_errors)
        if include_reports:
            report_candidates, report_skipped, report_errors = self._failure_report_archive_candidates(resolved)
            candidates.extend(report_candidates)
            skipped.extend(report_skipped)
            errors.extend(report_errors)

        planned = [entry for _path, entry in candidates]
        fingerprint = self._failure_archive_fingerprint(
            scope=scope,
            include_markers=include_markers,
            include_reports=include_reports,
            planned=planned,
        )
        manifest_path = self._failure_clear_manifest_preview_path(resolved, prefix="failure_evidence_archive")
        archive_dir = manifest_path.parent / "ClearedEvidence" / manifest_path.stem
        result: dict[str, Any] = {
            "schema_version": "failure_evidence_archive_result.v1",
            "operation": "archive_failure_evidence",
            "scope": scope,
            "include_markers": include_markers,
            "include_reports": include_reports,
            "markers": 0,
            "reports": 0,
            "planned": planned,
            "moved": [],
            "skipped": skipped,
            "errors": errors,
            "dry_run": bool(dry_run),
            "dry_run_fingerprint": fingerprint,
            "fingerprint": fingerprint,
            "manifest_path": str(manifest_path),
            "archive_dir": str(archive_dir),
            "writes_failure_evidence": False,
            "touches_media": False,
        }
        if dry_run:
            return result
        if not str(reason or "").strip():
            result["errors"].append("Failure evidence archive requires a non-empty reason.")
            return result
        if not dry_run_fingerprint or dry_run_fingerprint != fingerprint:
            result["errors"].append("Failure evidence archive fingerprint mismatch; run preview again before confirming.")
            return result
        if result["errors"]:
            return result

        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        archive_dir.mkdir(parents=True, exist_ok=True)
        manifest: dict[str, Any] = {
            "schema_version": FAILURE_CLEAR_MANIFEST_SCHEMA_VERSION,
            "operation": "archive_failure_evidence",
            "status": "planned",
            "dry_run": False,
            "reason": str(reason or "").strip(),
            "scope": scope,
            "include_markers": include_markers,
            "include_reports": include_reports,
            "dry_run_fingerprint": fingerprint,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "local_base": str(resolved.local_base),
            "allowed_roots": [str(root) for root in self._failure_workspace_roots(resolved)],
            "manifest_path": str(manifest_path),
            "archive_dir": str(archive_dir),
            "planned": planned,
            "moved": [],
            "skipped": skipped,
            "errors": [],
        }
        self._write_failure_clear_manifest(manifest_path, manifest)

        for path, entry in candidates:
            kind = str(entry.get("kind") or "")
            destination_folder = archive_dir / ("Markers" if kind == "marker" else "Reports")
            destination_folder.mkdir(parents=True, exist_ok=True)
            destination = destination_folder / path.name
            if destination.exists():
                destination = destination_folder / f"{path.stem}_{uuid.uuid4().hex[:8]}{path.suffix}"
            moved_entry = dict(entry)
            moved_entry["archive_path"] = str(destination)
            try:
                path.replace(destination)
                if kind == "marker":
                    result["markers"] += 1
                else:
                    result["reports"] += 1
                result["moved"].append(moved_entry)
                manifest["moved"].append(moved_entry)
            except OSError as exc:
                message = f"{path}: {exc}"
                result["errors"].append(message)
                manifest["errors"].append(message)
        result["writes_failure_evidence"] = bool(result["markers"] or result["reports"])
        manifest["status"] = "completed_with_errors" if manifest["errors"] else "completed"
        self._write_failure_clear_manifest(manifest_path, manifest)
        return result

    def clear_failure_workspace(self, resolved: ResolvedPaths, *, dry_run: bool = False) -> dict[str, Any]:
        if not resolved.local_base:
            raise RuntimeError("LocalBase is not resolved; failure workspace cannot be cleared.")

        allowed_roots = self._failure_workspace_roots(resolved)
        markers_dir = resolved.failed_markers_path
        reports_dir = resolved.failed_reports_path
        self._validate_failure_cleanup_folder(markers_dir, allowed_roots, "failure markers")
        self._validate_failure_cleanup_folder(reports_dir, allowed_roots, "failure reports")

        result: dict[str, Any] = {
            "markers": 0,
            "reports": 0,
            "errors": [],
            "dry_run": bool(dry_run),
            "manifest_path": "",
        }

        manifest_path = self._failure_clear_manifest_path(resolved)
        result["manifest_path"] = str(manifest_path)
        manifest: dict[str, Any] = {
            "schema_version": FAILURE_CLEAR_MANIFEST_SCHEMA_VERSION,
            "status": "dry_run" if dry_run else "planned",
            "dry_run": bool(dry_run),
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "local_base": str(resolved.local_base),
            "allowed_roots": [str(root) for root in allowed_roots],
            "manifest_path": str(manifest_path),
            "planned": [],
            "removed": [],
            "skipped": [],
            "errors": [],
        }

        def collect_matching_files(folder: Path | None, patterns: tuple[str, ...], kind: str) -> list[tuple[Path, str, dict[str, Any]]]:
            candidates: list[tuple[Path, str, dict[str, Any]]] = []
            if not folder or not folder.exists():
                return candidates
            seen: set[Path] = set()
            for pattern in patterns:
                try:
                    matches = list(folder.glob(pattern))
                except OSError as exc:
                    message = f"{folder}: {exc}"
                    result["errors"].append(message)
                    manifest["errors"].append(message)
                    continue
                for path in matches:
                    if path in seen:
                        continue
                    seen.add(path)
                    entry = self._file_manifest_entry(path, kind=kind, pattern=pattern)
                    if not any(self._path_within_root(path, root) for root in allowed_roots):
                        entry["reason"] = "outside allowed failure workspace roots"
                        manifest["skipped"].append(entry)
                        continue
                    boundary = next(
                        (
                            path_boundary_check(path, root)
                            for root in allowed_roots
                            if self._path_within_root(path, root)
                        ),
                        None,
                    )
                    if boundary is not None and not boundary.ok:
                        entry["reason"] = boundary.reason_code
                        manifest["skipped"].append(entry)
                        continue
                    try:
                        if not path.is_file():
                            entry["reason"] = "not a file"
                            manifest["skipped"].append(entry)
                            continue
                    except OSError as exc:
                        message = f"{path}: {exc}"
                        result["errors"].append(message)
                        manifest["errors"].append(message)
                        continue
                    candidates.append((path, kind, entry))
                    manifest["planned"].append(entry)
            return candidates

        candidates = []
        candidates.extend(collect_matching_files(markers_dir, ("*.json",), "markers"))
        candidates.extend(collect_matching_files(reports_dir, ("round_failures_*.json", "round_failures_*.txt"), "reports"))
        self._write_failure_clear_manifest(manifest_path, manifest)

        if not dry_run:
            for path, kind, entry in candidates:
                try:
                    path.unlink()
                    result[kind] += 1
                    manifest["removed"].append(entry)
                except OSError as exc:
                    message = f"{path}: {exc}"
                    result["errors"].append(message)
                    manifest["errors"].append(message)
            manifest["status"] = "completed_with_errors" if manifest["errors"] else "completed"
            self._write_failure_clear_manifest(manifest_path, manifest)
        return result
