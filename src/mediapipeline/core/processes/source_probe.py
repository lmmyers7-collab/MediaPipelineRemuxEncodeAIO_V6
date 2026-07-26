"""Killable filesystem probes for source availability and identity checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


SOURCE_PROBE_DEFAULT_TIMEOUT_SECONDS = 2.0
SOURCE_PROBE_DEFAULT_SAMPLE_BYTES = 1024 * 1024
SOURCE_PROBE_DEFAULT_MAX_BYTES = 1024 * 1024


def source_content_hash_timeout_seconds(size_bytes: int) -> float:
    """Return a bounded, size-aware deadline for a full content hash.

    The lower bound covers process startup and small remote files.  The
    throughput allowance is deliberately conservative for a busy UNC share,
    while the upper bound prevents an unreachable read from hanging forever.
    """

    size = max(0, int(size_bytes))
    return min(6 * 60 * 60.0, max(30.0, 15.0 + (size / (8 * 1024 * 1024))))


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _digest_sample(path: Path, *, sample_bytes: int) -> str:
    file_size = path.stat().st_size
    bounded_sample = max(1, int(sample_bytes))
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        digest.update(stream.read(min(max(0, file_size), bounded_sample)))
        if file_size > bounded_sample:
            stream.seek(max(0, file_size - bounded_sample))
            digest.update(stream.read(bounded_sample))
    return digest.hexdigest()


def probe_in_process(
    operation: str,
    path: Path,
    *,
    sample_bytes: int,
    max_bytes: int = SOURCE_PROBE_DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    if operation == "stat":
        result = path.stat()
        kind = "file" if stat.S_ISREG(result.st_mode) else "directory" if stat.S_ISDIR(result.st_mode) else "other"
        return {
            "ok": True,
            "kind": kind,
            "size": max(0, int(result.st_size)),
            "mtime": float(result.st_mtime),
        }
    if operation == "sha256":
        return {"ok": True, "digest": _digest_file(path)}
    if operation == "sample_sha256":
        return {"ok": True, "digest": _digest_sample(path, sample_bytes=sample_bytes)}
    if operation == "read_json":
        bounded_max = max(1, int(max_bytes))
        with path.open("rb") as stream:
            raw = stream.read(bounded_max + 1)
        if len(raw) > bounded_max:
            raise ValueError(f"JSON probe exceeds {bounded_max} bytes")
        text = raw.decode("utf-8-sig")
        payload = json.loads(text)
        return {"ok": True, "payload": payload, "size": len(raw)}
    raise ValueError(f"unsupported source probe operation: {operation}")


def run_source_probe(
    operation: str,
    path: Path,
    *,
    timeout_seconds: float = SOURCE_PROBE_DEFAULT_TIMEOUT_SECONDS,
    sample_bytes: int = SOURCE_PROBE_DEFAULT_SAMPLE_BYTES,
    max_bytes: int = SOURCE_PROBE_DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    timeout = max(0.01, float(timeout_seconds))
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    command = [
        sys.executable,
        "-m",
        "mediapipeline.core.processes.source_probe",
        "--operation",
        operation,
        "--path",
        str(path),
        "--sample-bytes",
        str(max(1, int(sample_bytes))),
        "--max-bytes",
        str(max(1, int(max_bytes))),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"{operation} source probe exceeded {timeout:g} seconds") from exc
    if completed.returncode != 0:
        raise OSError(f"source probe exited with {completed.returncode}")
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise OSError("source probe returned invalid JSON") from exc
    if not isinstance(payload, Mapping):
        raise OSError("source probe returned a non-object response")
    if payload.get("ok") is not True:
        error_type = str(payload.get("error_type") or "OSError")
        error = str(payload.get("error") or "source probe failed")
        if error_type == "FileNotFoundError":
            raise FileNotFoundError(error)
        if error_type == "PermissionError":
            raise PermissionError(error)
        if error_type in {"JSONDecodeError", "UnicodeDecodeError", "ValueError"}:
            raise ValueError(error)
        raise OSError(error)
    return dict(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--operation",
        choices=("stat", "sha256", "sample_sha256", "read_json"),
        required=True,
    )
    parser.add_argument("--path", required=True)
    parser.add_argument("--sample-bytes", type=int, default=SOURCE_PROBE_DEFAULT_SAMPLE_BYTES)
    parser.add_argument("--max-bytes", type=int, default=SOURCE_PROBE_DEFAULT_MAX_BYTES)
    args = parser.parse_args()
    try:
        payload = probe_in_process(
            args.operation,
            Path(args.path),
            sample_bytes=args.sample_bytes,
            max_bytes=args.max_bytes,
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
