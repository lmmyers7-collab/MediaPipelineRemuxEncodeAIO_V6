from __future__ import annotations

import contextlib
import hashlib
from pathlib import Path
import shutil
from typing import Any
import uuid

from app.files.constants import MEDIA_FILE_SUFFIXES

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

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(f".{destination.name}.promotion-{uuid.uuid4().hex}.tmp")
    try:
        if destination.exists():
            if not overwrite_existing:
                evidence["error"] = "Destination file already exists and overwrite is disabled."
                return evidence
            destination.unlink()
            evidence["overwritten"] = True
            evidence["overwritten_path"] = str(destination)

        shutil.copy2(source, temp_path)
        temp_verification = verify_copy(source, temp_path, verification_mode)
        evidence["temp_verification"] = temp_verification
        if not temp_verification.get("ok"):
            evidence["error"] = str(temp_verification.get("error") or "Temporary copy verification failed.")
            return evidence

        temp_path.replace(destination)
        final_verification = verify_copy(source, destination, verification_mode)
        evidence["final_verification"] = final_verification
        if not final_verification.get("ok"):
            evidence["error"] = str(final_verification.get("error") or "Final copy verification failed.")
            return evidence
        evidence["ok"] = True
        evidence["verified_at"] = utc_now_text()
        return evidence
    except Exception as exc:
        evidence["error"] = str(exc)
        return evidence
    finally:
        with contextlib.suppress(OSError):
            if temp_path.exists():
                temp_path.unlink()


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
    "copy_file_with_verification",
    "sha256_file",
    "verify_copy",
]
