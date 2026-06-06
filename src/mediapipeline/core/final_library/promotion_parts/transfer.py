from __future__ import annotations

import contextlib
import hashlib
from pathlib import Path
import shutil
from typing import Any, Iterable
import uuid

from mediapipeline.core.files.constants import MEDIA_FILE_SUFFIXES

from .planning import normalized_path_key, path_within_root
from .results import utc_now_text


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_copy(source: Path, destination: Path, mode: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_path": str(source),
        "destination_path": str(destination),
        "mode": mode,
        "exists": destination.exists(),
        "size_match": False,
        "hash_match": None,
        "ok": False,
    }
    if not result["exists"]:
        result["error"] = "Destination file does not exist."
        return result
    try:
        source_size = source.stat().st_size
        destination_size = destination.stat().st_size
    except OSError as exc:
        result["error"] = str(exc)
        return result
    result["source_size"] = source_size
    result["destination_size"] = destination_size
    result["size_match"] = source_size == destination_size
    if not result["size_match"]:
        result["error"] = "Destination byte size does not match source."
        return result
    if mode == "cautious":
        source_hash = sha256_file(source)
        destination_hash = sha256_file(destination)
        result["source_sha256"] = source_hash
        result["destination_sha256"] = destination_hash
        result["hash_match"] = source_hash == destination_hash
        if not result["hash_match"]:
            result["error"] = "Destination SHA-256 hash does not match source."
            return result
    result["ok"] = True
    return result


def copy_file_with_verification(
    source: Path,
    destination: Path,
    *,
    destination_root: Path,
    verification_mode: str,
    overwrite_existing: bool,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "source_path": str(source),
        "destination_path": str(destination),
        "destination_root": str(destination_root),
        "verification_mode": verification_mode,
        "overwritten": False,
        "ok": False,
    }
    if not source.exists():
        evidence["error"] = "Source file selected for promotion no longer exists."
        return evidence
    if not path_within_root(destination, destination_root):
        evidence["error"] = "Destination file is outside the final library destination root."
        return evidence
    if normalized_path_key(destination) == normalized_path_key(destination_root):
        evidence["error"] = "Destination file targets the final library destination root."
        return evidence

    destination_exists = destination.exists()
    if destination_exists:
        if not overwrite_existing:
            evidence["error"] = "Destination file already exists and overwrite is disabled."
            return evidence

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(f".{destination.name}.promotion-{uuid.uuid4().hex}.tmp")
    backup_path: Path | None = None
    published_destination = False
    try:
        shutil.copy2(source, temp_path)
        temp_verification = verify_copy(source, temp_path, verification_mode)
        evidence["temp_verification"] = temp_verification
        if not temp_verification.get("ok"):
            evidence["error"] = str(temp_verification.get("error") or "Temporary copy verification failed.")
            return evidence

        if destination_exists:
            backup_path = destination.with_name(f".{destination.name}.promotion-backup-{uuid.uuid4().hex}.tmp")
            destination.replace(backup_path)

        temp_path.replace(destination)
        published_destination = True
        final_verification = verify_copy(source, destination, verification_mode)
        evidence["final_verification"] = final_verification
        if not final_verification.get("ok"):
            evidence["error"] = str(final_verification.get("error") or "Final copy verification failed.")
            if backup_path is not None and backup_path.exists():
                with contextlib.suppress(OSError):
                    if destination.exists():
                        destination.unlink()
                    backup_path.replace(destination)
                    evidence["restored_existing"] = True
            elif not destination_exists:
                try:
                    if destination.exists():
                        destination.unlink()
                        evidence["removed_unverified_destination"] = True
                except OSError as cleanup_exc:
                    evidence["unverified_destination_cleanup_error"] = str(cleanup_exc)
            return evidence
        if destination_exists:
            evidence["overwritten"] = True
            evidence["overwritten_path"] = str(destination)
        evidence["ok"] = True
        evidence["verified_at"] = utc_now_text()
        if backup_path is not None and backup_path.exists():
            with contextlib.suppress(OSError):
                backup_path.unlink()
        return evidence
    except Exception as exc:
        evidence["error"] = str(exc)
        if backup_path is not None and backup_path.exists():
            with contextlib.suppress(OSError):
                if destination.exists():
                    destination.unlink()
                backup_path.replace(destination)
                evidence["restored_existing"] = True
        elif published_destination and not destination_exists:
            try:
                if destination.exists():
                    destination.unlink()
                    evidence["removed_unverified_destination"] = True
            except OSError as cleanup_exc:
                evidence["unverified_destination_cleanup_error"] = str(cleanup_exc)
        return evidence
    finally:
        with contextlib.suppress(OSError):
            if temp_path.exists():
                temp_path.unlink()


def _target_paths(target: Any) -> tuple[Path, Path]:
    return Path(target.source_path), Path(target.destination_path)


def _file_evidence(source: Path, destination: Path, destination_root: Path, verification_mode: str) -> dict[str, Any]:
    return {
        "source_path": str(source),
        "destination_path": str(destination),
        "destination_root": str(destination_root),
        "verification_mode": verification_mode,
        "overwritten": False,
        "ok": False,
    }


def _transaction_failure(source: Path, destination: Path, error: str) -> dict[str, str]:
    return {
        "source_path": str(source),
        "destination_path": str(destination),
        "error": error,
    }


def _cleanup_transaction_temps(staged_files: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for staged in staged_files:
        temp_path = staged.get("temp_path")
        if isinstance(temp_path, Path):
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError as exc:
                errors.append({"path": str(temp_path), "error": str(exc)})
    return errors


def _rollback_revealed_transaction_files(revealed_files: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rolled_back: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for staged in reversed(list(revealed_files)):
        destination = staged["destination_path"]
        backup_path = staged.get("backup_path")
        destination_exists = bool(staged.get("destination_existed"))
        rollback: dict[str, Any] = {
            "source_path": str(staged["source_path"]),
            "destination_path": str(destination),
            "restored_existing": False,
            "removed_destination": False,
        }
        try:
            if destination.exists():
                destination.unlink()
                rollback["removed_destination"] = True
            if destination_exists and isinstance(backup_path, Path) and backup_path.exists():
                backup_path.replace(destination)
                rollback["restored_existing"] = True
            rolled_back.append(rollback)
        except OSError as exc:
            errors.append({"path": str(destination), "error": str(exc)})
    return rolled_back, errors


def _delete_transaction_backups(staged_files: Iterable[dict[str, Any]]) -> None:
    for staged in staged_files:
        backup_path = staged.get("backup_path")
        if isinstance(backup_path, Path):
            with contextlib.suppress(OSError):
                if backup_path.exists():
                    backup_path.unlink()


def copy_files_transactionally(
    targets: Iterable[Any],
    *,
    destination_root: Path,
    verification_mode: str,
    overwrite_existing: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "copied_files": [],
        "overwritten_files": [],
        "failures": [],
        "rolled_back_files": [],
        "rollback_errors": [],
    }
    entries: list[dict[str, Any]] = []
    destination_root_key = normalized_path_key(destination_root)
    for target in targets:
        source, destination = _target_paths(target)
        evidence = _file_evidence(source, destination, destination_root, verification_mode)
        if not source.exists():
            result["failures"].append(
                _transaction_failure(source, destination, "Source file selected for promotion no longer exists.")
            )
            return result
        if not path_within_root(destination, destination_root):
            result["failures"].append(
                _transaction_failure(source, destination, "Destination file is outside the final library destination root.")
            )
            return result
        if normalized_path_key(destination) == destination_root_key:
            result["failures"].append(
                _transaction_failure(source, destination, "Destination file targets the final library destination root.")
            )
            return result
        destination_existed = destination.exists()
        if destination_existed and not overwrite_existing:
            result["failures"].append(
                _transaction_failure(source, destination, "Destination file already exists and overwrite is disabled.")
            )
            return result
        entries.append(
            {
                "source_path": source,
                "destination_path": destination,
                "destination_existed": destination_existed,
                "evidence": evidence,
            }
        )

    staged_files: list[dict[str, Any]] = []
    revealed_files: list[dict[str, Any]] = []
    try:
        for entry in entries:
            source = entry["source_path"]
            destination = entry["destination_path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp_path = destination.with_name(f".{destination.name}.promotion-{uuid.uuid4().hex}.tmp")
            entry["temp_path"] = temp_path
            staged_files.append(entry)
            try:
                shutil.copy2(source, temp_path)
                temp_verification = verify_copy(source, temp_path, verification_mode)
                entry["evidence"]["temp_verification"] = temp_verification
                if not temp_verification.get("ok"):
                    result["failures"].append(
                        _transaction_failure(
                            source,
                            destination,
                            str(temp_verification.get("error") or "Temporary copy verification failed."),
                        )
                    )
                    return result
            except Exception as exc:
                result["failures"].append(_transaction_failure(source, destination, str(exc)))
                return result

        for entry in staged_files:
            source = entry["source_path"]
            destination = entry["destination_path"]
            if entry["destination_existed"]:
                backup_path = destination.with_name(f".{destination.name}.promotion-backup-{uuid.uuid4().hex}.tmp")
                destination.replace(backup_path)
                entry["backup_path"] = backup_path
                revealed_files.append(entry)
            elif destination.exists():
                if not overwrite_existing:
                    result["failures"].append(
                        _transaction_failure(
                            source,
                            destination,
                            "Destination file appeared during promotion transaction and overwrite is disabled.",
                        )
                    )
                    return result
                backup_path = destination.with_name(f".{destination.name}.promotion-backup-{uuid.uuid4().hex}.tmp")
                destination.replace(backup_path)
                entry["destination_existed"] = True
                entry["backup_path"] = backup_path
                revealed_files.append(entry)
            temp_path = entry["temp_path"]
            temp_path.replace(destination)
            if not entry["destination_existed"]:
                revealed_files.append(entry)
            final_verification = verify_copy(source, destination, verification_mode)
            entry["evidence"]["final_verification"] = final_verification
            if not final_verification.get("ok"):
                result["failures"].append(
                    _transaction_failure(
                        source,
                        destination,
                        str(final_verification.get("error") or "Final copy verification failed."),
                    )
                )
                return result
            if entry["destination_existed"]:
                entry["evidence"]["overwritten"] = True
                entry["evidence"]["overwritten_path"] = str(destination)
                result["overwritten_files"].append(str(destination))
            entry["evidence"]["ok"] = True
            entry["evidence"]["verified_at"] = utc_now_text()

        result["copied_files"] = [entry["evidence"] for entry in staged_files]
        result["ok"] = True
        return result
    except Exception as exc:
        failing = revealed_files[-1] if revealed_files else staged_files[-1] if staged_files else None
        source = Path(str(failing.get("source_path") or "")) if failing else Path("")
        destination = Path(str(failing.get("destination_path") or "")) if failing else Path("")
        result["failures"].append(_transaction_failure(source, destination, str(exc)))
        return result
    finally:
        if not result["ok"]:
            rolled_back, rollback_errors = _rollback_revealed_transaction_files(revealed_files)
            result["rolled_back_files"].extend(rolled_back)
            result["rollback_errors"].extend(rollback_errors)
        else:
            _delete_transaction_backups(staged_files)
        result["rollback_errors"].extend(_cleanup_transaction_temps(staged_files))


def companion_sidecars(primary: Path) -> list[Path]:
    if primary.suffix.casefold() not in MEDIA_FILE_SUFFIXES:
        return []
    try:
        items = list(primary.parent.iterdir())
    except OSError:
        return []
    prefix = primary.stem + "."
    sidecars = [
        item
        for item in items
        if item.is_file()
        and item != primary
        and item.name.startswith(prefix)
        and ".promotion-" not in item.name
    ]
    return sorted(sidecars, key=lambda item: item.name.casefold())


__all__ = [
    "companion_sidecars",
    "copy_files_transactionally",
    "copy_file_with_verification",
    "sha256_file",
    "verify_copy",
]
