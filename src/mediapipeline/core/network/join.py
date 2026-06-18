"""Secret-safe network coordinator join blob helpers."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterable, Mapping
from typing import Any

from mediapipeline.core.network.url_policy import validate_coordinator_url
from mediapipeline.desktop.network.library_roots import (
    auto_source_path_map_from_libraries,
    library_roots_from_config,
    merge_manual_and_auto_path_maps,
)
from mediapipeline.desktop.network.path_map import parse_source_path_map


NETWORK_JOIN_BLOB_SCHEMA_VERSION = "desktop_network_join_blob.v1"
NETWORK_JOIN_BLOB_RESULT_SCHEMA_VERSION = "desktop_network_join_blob_result.v1"
NETWORK_JOIN_IMPORT_RESULT_SCHEMA_VERSION = "desktop_network_join_import_result.v1"
NETWORK_JOIN_MIN_TOKEN_LENGTH = 16
NETWORK_JOIN_BLOB_MAX_ENCODED_CHARS = 64 * 1024
NETWORK_JOIN_BLOB_MAX_DECODED_BYTES = 32 * 1024
NETWORK_JOIN_BLOB_MAX_LIBRARY_ROWS = 128
NETWORK_JOIN_BLOB_MAX_FIELD_CHARS = 4096
NETWORK_JOIN_BLOB_MAX_SHORT_FIELD_CHARS = 256


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bounded_text(value: Any, field_name: str, *, limit: int = NETWORK_JOIN_BLOB_MAX_FIELD_CHARS) -> str:
    text = _text(value)
    if len(text) > limit:
        raise ValueError(f"join_blob field {field_name} is too long.")
    return text


def _validate_join_token(value: Any) -> str:
    token = _bounded_text(value, "token")
    if len(token) < NETWORK_JOIN_MIN_TOKEN_LENGTH:
        raise ValueError(
            "Network join token is missing or too short; use a coordinator token "
            f"with at least {NETWORK_JOIN_MIN_TOKEN_LENGTH} characters."
        )
    return token


def _safe_library_rows(rows: Iterable[Mapping[str, Any]] | None) -> list[dict[str, str]]:
    safe: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows or []):
        if index >= NETWORK_JOIN_BLOB_MAX_LIBRARY_ROWS:
            raise ValueError("join_blob libraries has too many rows.")
        if not isinstance(row, Mapping):
            continue
        field_prefix = f"libraries[{index}]"
        library_id = _bounded_text(
            row.get("library_id") or row.get("id"),
            f"{field_prefix}.library_id",
            limit=NETWORK_JOIN_BLOB_MAX_SHORT_FIELD_CHARS,
        )
        source_root = _bounded_text(row.get("source_root") or row.get("source_path"), f"{field_prefix}.source_root")
        if not library_id or not source_root:
            continue
        key = library_id.casefold()
        if key in seen:
            continue
        seen.add(key)
        safe.append(
            {
                "library_id": library_id,
                "name": _bounded_text(
                    row.get("name"),
                    f"{field_prefix}.name",
                    limit=NETWORK_JOIN_BLOB_MAX_SHORT_FIELD_CHARS,
                ) or library_id,
                "designation": _bounded_text(
                    row.get("designation"),
                    f"{field_prefix}.designation",
                    limit=NETWORK_JOIN_BLOB_MAX_SHORT_FIELD_CHARS,
                ) or "auto",
                "source_root": source_root,
                "output_root": _bounded_text(row.get("output_root") or row.get("output_path"), f"{field_prefix}.output_root"),
            }
        )
    return safe


def _base64url_json(payload: Mapping[str, Any]) -> str:
    material = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(material) > NETWORK_JOIN_BLOB_MAX_DECODED_BYTES:
        raise ValueError("join_blob decoded payload is too large.")
    encoded = base64.urlsafe_b64encode(material).decode("ascii").rstrip("=")
    if len(encoded) > NETWORK_JOIN_BLOB_MAX_ENCODED_CHARS:
        raise ValueError("join_blob encoded payload is too large.")
    return encoded


def _decode_base64url_json(blob: Any) -> dict[str, Any]:
    text = "".join(_text(blob).split())
    if text.casefold().startswith("mediapipeline-join:"):
        text = text.split(":", 1)[1].strip()
    if not text:
        raise ValueError("join_blob is required.")
    if len(text) > NETWORK_JOIN_BLOB_MAX_ENCODED_CHARS:
        raise ValueError("join_blob encoded payload is too large.")
    padding = "=" * (-len(text) % 4)
    try:
        raw = base64.b64decode((text + padding).encode("ascii"), altchars=b"-_", validate=True)
    except Exception as exc:
        raise ValueError("join_blob must be a base64url encoded JSON object.") from exc
    if len(raw) > NETWORK_JOIN_BLOB_MAX_DECODED_BYTES:
        raise ValueError("join_blob decoded payload is too large.")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("join_blob must be a base64url encoded JSON object.") from exc
    if not isinstance(payload, dict):
        raise ValueError("join_blob decoded to a non-object payload.")
    return payload


def encode_network_join_blob(
    *,
    coordinator_url: Any,
    token: Any,
    libraries: Iterable[Mapping[str, Any]] | None,
    created_at_utc: str,
) -> tuple[str, dict[str, Any]]:
    """Return ``(blob, payload)`` for a coordinator setup transfer."""
    normalized_url = validate_coordinator_url(_bounded_text(coordinator_url, "coordinator_url"))
    normalized_token = _validate_join_token(token)
    safe_libraries = _safe_library_rows(libraries)
    payload: dict[str, Any] = {
        "schema_version": NETWORK_JOIN_BLOB_SCHEMA_VERSION,
        "coordinator_url": normalized_url,
        "token": normalized_token,
        "libraries": safe_libraries,
        "library_count": len(safe_libraries),
        "created_at_utc": _bounded_text(
            created_at_utc,
            "created_at_utc",
            limit=NETWORK_JOIN_BLOB_MAX_SHORT_FIELD_CHARS,
        ),
    }
    return _base64url_json(payload), payload


def decode_network_join_blob(blob: Any) -> dict[str, Any]:
    """Decode and validate a coordinator setup transfer blob."""
    payload = _decode_base64url_json(blob)
    schema_version = _text(payload.get("schema_version"))
    if schema_version != NETWORK_JOIN_BLOB_SCHEMA_VERSION:
        raise ValueError(
            f"join_blob schema_version must be {NETWORK_JOIN_BLOB_SCHEMA_VERSION}."
        )
    coordinator_url = validate_coordinator_url(_bounded_text(payload.get("coordinator_url"), "coordinator_url"))
    token = _validate_join_token(payload.get("token"))
    libraries = payload.get("libraries", [])
    if not isinstance(libraries, list):
        raise ValueError("join_blob libraries must be a JSON array.")
    if len(libraries) > NETWORK_JOIN_BLOB_MAX_LIBRARY_ROWS:
        raise ValueError("join_blob libraries has too many rows.")
    safe_libraries = _safe_library_rows(
        row for row in libraries if isinstance(row, Mapping)
    )
    return {
        "schema_version": schema_version,
        "coordinator_url": coordinator_url,
        "token": token,
        "libraries": safe_libraries,
        "library_count": len(safe_libraries),
        "created_at_utc": _bounded_text(
            payload.get("created_at_utc"),
            "created_at_utc",
            limit=NETWORK_JOIN_BLOB_MAX_SHORT_FIELD_CHARS,
        ),
    }


def worker_join_patch_from_blob(
    blob: Any,
    worker_config: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build worker settings changes plus redacted setup evidence."""
    payload = decode_network_join_blob(blob)
    config = dict(worker_config or {})
    manual_mappings = parse_source_path_map(_text(config.get("WorkerSourcePathMap")))
    auto_mappings = auto_source_path_map_from_libraries(payload["libraries"], config)
    effective_mappings = merge_manual_and_auto_path_maps(manual_mappings, auto_mappings)

    changes: dict[str, Any] = {
        "NetworkRole": "worker",
        "WorkerCoordinatorUrl": payload["coordinator_url"],
        "WorkerAuthToken": payload["token"],
    }
    if effective_mappings:
        changes["WorkerSourcePathMap"] = json.dumps(
            {source: target for source, target in effective_mappings},
            ensure_ascii=False,
        )

    worker_libraries = library_roots_from_config(config)
    evidence = {
        "schema_version": "desktop_network_join_import_plan.v1",
        "library_count": int(payload["library_count"]),
        "matched_library_count": len(auto_mappings),
        "worker_library_count": len(worker_libraries),
        "manual_path_map_entries": len(manual_mappings),
        "auto_path_map_entries": len(auto_mappings),
        "effective_path_map_entries": len(effective_mappings),
        "path_map_seeded": bool(effective_mappings),
        "changed_keys": sorted(changes),
    }
    return payload, changes, evidence


__all__ = [
    "NETWORK_JOIN_BLOB_RESULT_SCHEMA_VERSION",
    "NETWORK_JOIN_BLOB_SCHEMA_VERSION",
    "NETWORK_JOIN_BLOB_MAX_DECODED_BYTES",
    "NETWORK_JOIN_BLOB_MAX_ENCODED_CHARS",
    "NETWORK_JOIN_BLOB_MAX_FIELD_CHARS",
    "NETWORK_JOIN_BLOB_MAX_LIBRARY_ROWS",
    "NETWORK_JOIN_IMPORT_RESULT_SCHEMA_VERSION",
    "decode_network_join_blob",
    "encode_network_join_blob",
    "worker_join_patch_from_blob",
]
