from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from mediapipeline.core.kernel.contracts.pending_publish import PendingPushManifest


_HASH_CHUNK_SIZE = 1024 * 1024


class ContentProofError(RuntimeError):
    """Raised when a stable byte proof cannot be read from a payload."""


@dataclass(frozen=True)
class ContentProof:
    size: int
    sha256: str


def read_content_proof(path: Path) -> ContentProof:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            while chunk := handle.read(_HASH_CHUNK_SIZE):
                digest.update(chunk)
                size += len(chunk)
            after = os.fstat(handle.fileno())
        path_after = path.stat()
    except OSError as exc:
        raise ContentProofError(f"cannot read stable content proof for {path}: {exc}") from exc

    before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    path_identity = (
        path_after.st_dev,
        path_after.st_ino,
        path_after.st_size,
        path_after.st_mtime_ns,
    )
    if before_identity != after_identity or after_identity != path_identity or size != after.st_size:
        raise ContentProofError(f"payload changed while content proof was being read: {path}")
    return ContentProof(size=size, sha256=digest.hexdigest())


def verify_pending_manifest_content_proofs(manifest: PendingPushManifest) -> None:
    payload_path = Path(manifest.local_file)
    payload_proof = read_content_proof(payload_path)
    if payload_proof.size != manifest.output_size:
        raise ContentProofError(
            f"output_size does not match pending payload bytes: {payload_path}"
        )
    if payload_proof.sha256.casefold() != manifest.output_sha256.casefold():
        raise ContentProofError(
            f"output_sha256 does not match pending payload bytes: {payload_path}"
        )

    for index, sidecar in enumerate(manifest.sidecar_files):
        if not isinstance(sidecar, Mapping):
            raise ContentProofError(f"sidecar_files[{index}] is not an object")
        sidecar_path = Path(str(sidecar.get("local_file") or "").strip())
        sidecar_proof = read_content_proof(sidecar_path)
        expected_size = int(sidecar["output_size"])
        expected_hash = str(sidecar["output_sha256"])
        if sidecar_proof.size != expected_size:
            raise ContentProofError(
                f"sidecar_files[{index}] output_size does not match payload bytes: {sidecar_path}"
            )
        if sidecar_proof.sha256.casefold() != expected_hash.casefold():
            raise ContentProofError(
                f"sidecar_files[{index}] output_sha256 does not match payload bytes: {sidecar_path}"
            )
