"""Network runtime-state facade adapter."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, UTC
import hashlib
import ipaddress
import logging
from pathlib import Path
import re
import socket
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from mediapipeline.core.config.library_profiles import effective_library_profiles_from_config
from mediapipeline.core.kernel.config_keys import (
    KEY_WORKER_ENCODER_MAP,
    KEY_WORKER_HONOR_COORDINATOR_POLICY,
)
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.network.join import (
    NETWORK_JOIN_BLOB_RESULT_SCHEMA_VERSION,
    NETWORK_JOIN_IMPORT_RESULT_SCHEMA_VERSION,
    encode_network_join_blob,
    worker_join_patch_from_blob,
)
from mediapipeline.core.network.auth import generate_token
from mediapipeline.core.network.library_roots import library_roots_from_config
from mediapipeline.core.network.path_map import parse_source_path_map
from mediapipeline.core.network.registry import InFlightRegistry
from mediapipeline.core.network.url_policy import redact_network_secret_text, redact_url
from mediapipeline.core.network.url_policy import validate_coordinator_url
from mediapipeline.core.network.worker_state import load_worker_state
from mediapipeline.core.processes.pipeline_policy import configured_network_role
from mediapipeline.core.paths.contracts import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_workspaces import NetworkWorkersDto


_log = logging.getLogger(__name__)
NETWORK_TEST_CONNECTION_SCHEMA_VERSION = "desktop_network_worker_test_connection.v1"
NETWORK_COORDINATOR_DISCOVERY_SCHEMA_VERSION = "desktop_network_coordinator_discovery.v1"


from mediapipeline.core.network.facade_contract import (
    NETWORK_COORDINATOR_DISCOVERY_SCHEMA_VERSION,
    NETWORK_TEST_CONNECTION_SCHEMA_VERSION,
)
from mediapipeline.core.network.facade_connectivity import *  # noqa: F403

def _token_posture(resolved: ResolvedPaths) -> dict[str, Any]:
    config = resolved.config_data or {}

    def token_row(value: Any, *, allow_generate: bool) -> dict[str, Any]:
        present = bool(str(value or "").strip())
        if present:
            status = "present"
            display = "present, hidden"
        elif allow_generate:
            status = "blank"
            display = "blank; coordinator can generate one on start"
        else:
            status = "missing"
            display = "missing; must match the coordinator token"
        return {
            "status": status,
            "display": display,
            "hidden": True,
            "auto_generate_if_blank": allow_generate,
        }

    return {
        "schema_version": "desktop_network_token_posture.v1",
        "coordinator": token_row(config.get("CoordinatorAuthToken"), allow_generate=True),
        "worker": token_row(config.get("WorkerAuthToken"), allow_generate=False),
        "summary_lines": [
            f"Coordinator token: {token_row(config.get('CoordinatorAuthToken'), allow_generate=True)['display']}.",
            f"Worker token: {token_row(config.get('WorkerAuthToken'), allow_generate=False)['display']}.",
            "Token values are hidden; workers must use the same shared token as the coordinator.",
        ],
        "read_only": True,
    }


def _fingerprint_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def _path_map_fingerprint(mappings: list[tuple[str, str]]) -> str:
    if not mappings:
        return ""
    material = "\n".join(f"{source}\0{target}" for source, target in mappings)
    return _fingerprint_text(material)


def _path_map_descriptor(raw: Any) -> dict[str, Any]:
    mappings = parse_source_path_map(str(raw or "").strip())
    fingerprint = _path_map_fingerprint(mappings)
    return {
        "manual_path_map_entries": len(mappings),
        "manual_path_map_fingerprint": fingerprint,
        "auto_path_map_entries": 0,
        "auto_path_map_fingerprint": "",
        "auto_path_map_active": False,
        "effective_path_map_entries": len(mappings),
        "effective_path_map_fingerprint": fingerprint,
        "path_map_entries": len(mappings),
        "path_map_fingerprint": fingerprint,
    }


def _config_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _worker_encoder_map_descriptor(raw: Any) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {
            "worker_encoder_map_entries": 0,
            "worker_encoder_map_fingerprint": "",
            "worker_encoder_map_valid": True,
        }
    try:
        import json

        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("WorkerEncoderMap must be a JSON object.")
        normalized = {
            str(key or "").strip().casefold(): str(value or "").strip().casefold()
            for key, value in parsed.items()
            if str(key or "").strip() and str(value or "").strip()
        }
        material = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        return {
            "worker_encoder_map_entries": len(normalized),
            "worker_encoder_map_fingerprint": _fingerprint_text(material),
            "worker_encoder_map_valid": True,
        }
    except Exception:
        return {
            "worker_encoder_map_entries": 0,
            "worker_encoder_map_fingerprint": _fingerprint_text(text),
            "worker_encoder_map_valid": False,
        }


def _worker_url_compare_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return f"valid:{validate_coordinator_url(text).casefold()}"
    except ValueError:
        return f"invalid:{redact_url(text).casefold()}"


def _worker_runtime_descriptor(owner: object) -> tuple[dict[str, Any] | None, str]:
    runtime = getattr(owner, "_network_dispatcher_runtime", None)
    if not isinstance(runtime, dict):
        return None, ""
    entry = runtime.get("worker")
    if not isinstance(entry, dict):
        return None, ""
    dispatcher = entry.get("dispatcher")
    if dispatcher is None:
        return None, ""
    try:
        descriptor_func = getattr(dispatcher, "runtime_descriptor", None)
        if callable(descriptor_func):
            raw_descriptor = dict(descriptor_func() or {})
        else:
            effective_mappings = list(getattr(dispatcher, "_source_path_map", []) or [])
            manual_source = getattr(dispatcher, "_manual_source_path_map", None)
            manual_mappings = list(manual_source if manual_source is not None else effective_mappings)
            auto_mappings = list(getattr(dispatcher, "_auto_source_path_map", []) or [])
            raw_descriptor = {
                "coordinator_url": str(getattr(dispatcher, "coordinator_url", "") or ""),
                "token_fingerprint": _fingerprint_text(getattr(dispatcher, "_auth_token", "")),
                "manual_path_map_entries": len(manual_mappings),
                "manual_path_map_fingerprint": _path_map_fingerprint(manual_mappings),
                "auto_path_map_entries": len(auto_mappings),
                "auto_path_map_fingerprint": _path_map_fingerprint(auto_mappings),
                "auto_path_map_active": bool(auto_mappings),
                "effective_path_map_entries": len(effective_mappings),
                "effective_path_map_fingerprint": _path_map_fingerprint(effective_mappings),
                "path_map_entries": len(effective_mappings),
                "path_map_fingerprint": _path_map_fingerprint(effective_mappings),
            }
    except Exception as exc:
        return None, redact_network_secret_text(exc)

    def descriptor_int(name: str, fallback: Any = 0) -> int:
        try:
            return max(0, int(raw_descriptor.get(name, fallback) or 0))
        except (TypeError, ValueError):
            return 0

    path_map_entries = descriptor_int("path_map_entries")
    manual_path_map_entries = descriptor_int("manual_path_map_entries", path_map_entries)
    auto_path_map_entries = descriptor_int("auto_path_map_entries")
    effective_path_map_entries = descriptor_int("effective_path_map_entries", path_map_entries)
    try:
        worker_encoder_map_entries = int(raw_descriptor.get("worker_encoder_map_entries") or 0)
    except (TypeError, ValueError):
        worker_encoder_map_entries = 0
    manual_path_map_fingerprint = raw_descriptor.get("manual_path_map_fingerprint")
    if manual_path_map_fingerprint is None:
        manual_path_map_fingerprint = raw_descriptor.get("path_map_fingerprint")
    effective_path_map_fingerprint = raw_descriptor.get("effective_path_map_fingerprint")
    if effective_path_map_fingerprint is None:
        effective_path_map_fingerprint = raw_descriptor.get("path_map_fingerprint")
    return {
        "coordinator_url": redact_url(raw_descriptor.get("coordinator_url")),
        "token_fingerprint": str(raw_descriptor.get("token_fingerprint") or ""),
        "manual_path_map_entries": manual_path_map_entries,
        "manual_path_map_fingerprint": str(manual_path_map_fingerprint or ""),
        "auto_path_map_entries": auto_path_map_entries,
        "auto_path_map_fingerprint": str(raw_descriptor.get("auto_path_map_fingerprint") or ""),
        "auto_path_map_active": bool(raw_descriptor.get("auto_path_map_active")) or auto_path_map_entries > 0,
        "effective_path_map_entries": effective_path_map_entries,
        "effective_path_map_fingerprint": str(effective_path_map_fingerprint or ""),
        "path_map_entries": max(0, path_map_entries),
        "path_map_fingerprint": str(raw_descriptor.get("path_map_fingerprint") or ""),
        "honor_coordinator_policy": bool(raw_descriptor.get("honor_coordinator_policy")),
        "worker_encoder_map_entries": max(0, worker_encoder_map_entries),
        "worker_encoder_map_fingerprint": str(raw_descriptor.get("worker_encoder_map_fingerprint") or ""),
        "worker_encoder_map_valid": raw_descriptor.get("worker_encoder_map_valid") is not False,
    }, ""


def _field_label(field: str) -> str:
    return {
        "coordinator_url": "Coordinator URL",
        "worker_auth_token": "Worker auth token fingerprint",
        "source_path_map": "Worker source path map",
        "coordinator_policy_flag": "Worker coordinator-policy flag",
        "worker_encoder_map": "Worker encoder map",
        "coordinator_policy_disabled": "Coordinator policy disabled",
        "worker_encoder_map_invalid": "Worker encoder map invalid",
        "worker_encoder_map_empty": "Worker encoder map empty",
    }.get(field, field.replace("_", " "))


def _worker_policy_divergence(saved: dict[str, Any]) -> dict[str, Any]:
    fields: list[str] = []
    if not bool(saved.get("honor_coordinator_policy")):
        fields.append("coordinator_policy_disabled")
    if saved.get("worker_encoder_map_valid") is False:
        fields.append("worker_encoder_map_invalid")
    elif bool(saved.get("honor_coordinator_policy")) and int(saved.get("worker_encoder_map_entries") or 0) == 0:
        fields.append("worker_encoder_map_empty")

    labels = [_field_label(field) for field in fields]
    if fields:
        summary_lines = [
            f"Coordinator policy authority: review ({', '.join(labels)}).",
            "Worker may use local media-policy behavior or CPU fallback until the worker policy settings are saved and validated.",
        ]
        status = "review"
    else:
        summary_lines = [
            "Coordinator policy authority: ready.",
            "Worker is configured to honor coordinator claims and has a valid encoder map descriptor.",
        ]
        status = "ready"
    return {
        "schema_version": "desktop_network_worker_policy_divergence.v1",
        "status": status,
        "fields": fields,
        "field_labels": labels,
        "summary_lines": summary_lines,
        "read_only": True,
    }


def _worker_running_vs_saved(owner: object, resolved: ResolvedPaths) -> dict[str, Any]:
    config = resolved.config_data or {}
    saved_map = _path_map_descriptor(config.get("WorkerSourcePathMap"))
    saved_encoder_map = _worker_encoder_map_descriptor(config.get(KEY_WORKER_ENCODER_MAP))
    saved = {
        "coordinator_url": redact_url(config.get("WorkerCoordinatorUrl")),
        "token_fingerprint": _fingerprint_text(config.get("WorkerAuthToken")),
        "honor_coordinator_policy": _config_bool(config.get(KEY_WORKER_HONOR_COORDINATOR_POLICY)),
        **saved_map,
        **saved_encoder_map,
    }
    policy_divergence = _worker_policy_divergence(saved)
    running, error = _worker_runtime_descriptor(owner)
    if error:
        return {
            "schema_version": "desktop_network_worker_running_vs_saved.v1",
            "status": "unknown",
            "running": {},
            "saved": saved,
            "drift_fields": [],
            "policy_divergence": policy_divergence,
            "summary_lines": [
                "Worker settings drift: unavailable.",
                f"Reason: {error}",
                *policy_divergence["summary_lines"],
            ],
            "read_only": True,
        }
    if running is None:
        return {
            "schema_version": "desktop_network_worker_running_vs_saved.v1",
            "status": "not_running",
            "running": {},
            "saved": saved,
            "drift_fields": [],
            "policy_divergence": policy_divergence,
            "summary_lines": [
                "Worker settings drift: not running.",
                "Saved worker settings will be used the next time worker polling starts.",
                *policy_divergence["summary_lines"],
            ],
            "read_only": True,
        }

    drift_fields: list[str] = []
    if _worker_url_compare_key(running.get("coordinator_url")) != _worker_url_compare_key(config.get("WorkerCoordinatorUrl")):
        drift_fields.append("coordinator_url")
    if str(running.get("token_fingerprint") or "") != str(saved.get("token_fingerprint") or ""):
        drift_fields.append("worker_auth_token")
    if (
        int(running.get("manual_path_map_entries") or 0) != int(saved.get("manual_path_map_entries") or 0)
        or str(running.get("manual_path_map_fingerprint") or "") != str(saved.get("manual_path_map_fingerprint") or "")
    ):
        drift_fields.append("source_path_map")
    if bool(running.get("honor_coordinator_policy")) != bool(saved.get("honor_coordinator_policy")):
        drift_fields.append("coordinator_policy_flag")
    if (
        int(running.get("worker_encoder_map_entries") or 0) != int(saved.get("worker_encoder_map_entries") or 0)
        or str(running.get("worker_encoder_map_fingerprint") or "") != str(saved.get("worker_encoder_map_fingerprint") or "")
        or bool(running.get("worker_encoder_map_valid")) != bool(saved.get("worker_encoder_map_valid"))
    ):
        drift_fields.append("worker_encoder_map")

    auto_map_active = bool(running.get("auto_path_map_active")) or int(running.get("auto_path_map_entries") or 0) > 0
    if drift_fields:
        labels = ", ".join(_field_label(field) for field in drift_fields)
        summary_lines = [
            f"Worker settings drift: running worker differs from saved config ({labels}).",
            "Restart worker polling from Network Lifecycle to reconnect with saved settings.",
            *policy_divergence["summary_lines"],
        ]
        status = "drift"
        source_path_map_status = "drift" if "source_path_map" in drift_fields else "match"
    else:
        path_map_line = (
            "Worker settings drift: none (auto-derived library path map active)."
            if auto_map_active
            else "Worker settings drift: none."
        )
        summary_lines = [
            path_map_line,
            "Running worker URL, auth-token fingerprint, manual source path map, coordinator-policy flag, and encoder map match saved config.",
            *policy_divergence["summary_lines"],
        ]
        status = "match"
        source_path_map_status = "auto-map-active" if auto_map_active else "match"
    return {
        "schema_version": "desktop_network_worker_running_vs_saved.v1",
        "status": status,
        "running": running,
        "saved": saved,
        "drift_fields": drift_fields,
        "drift_field_labels": [_field_label(field) for field in drift_fields],
        "source_path_map_status": source_path_map_status,
        "policy_divergence": policy_divergence,
        "summary_lines": summary_lines,
        "read_only": True,
    }



__all__ = [
    "_token_posture",
    "_fingerprint_text",
    "_path_map_fingerprint",
    "_path_map_descriptor",
    "_config_bool",
    "_worker_encoder_map_descriptor",
    "_worker_url_compare_key",
    "_worker_runtime_descriptor",
    "_field_label",
    "_worker_policy_divergence",
    "_worker_running_vs_saved",
]
