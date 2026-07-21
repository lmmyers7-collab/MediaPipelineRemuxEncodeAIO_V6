from __future__ import annotations

from collections.abc import Mapping
import hashlib
from pathlib import Path
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths


QUEUE_INPUT_FINGERPRINT_SCHEMA_VERSION = "queue_input_fingerprint.v1"

_COMPONENT_PATH_ATTRIBUTES = (
    ("config", "config_path"),
    ("priority_manifest", "priority_manifest_path"),
    ("queue_strategy", "queue_strategy_path"),
    ("file_overrides", "file_overrides_path"),
)


def _component_evidence(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"status": "missing", "sha256": "missing"}
    try:
        if not path.is_file():
            return {"status": "missing", "sha256": "missing"}
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        return {
            "status": "unavailable",
            "sha256": "unavailable",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"status": "current", "sha256": digest}


def queue_input_fingerprint(resolved: ResolvedPaths) -> dict[str, Any]:
    components: dict[str, dict[str, Any]] = {}
    for name, attribute in _COMPONENT_PATH_ATTRIBUTES:
        value = getattr(resolved, attribute, None)
        components[name] = _component_evidence(Path(value) if value is not None else None)
    ordered_lines = [f"schema={QUEUE_INPUT_FINGERPRINT_SCHEMA_VERSION}"]
    for name, _attribute in _COMPONENT_PATH_ATTRIBUTES:
        component = components[name]
        ordered_lines.append(f"{name}={component['sha256']}")
    digest = hashlib.sha256(("\n".join(ordered_lines) + "\n").encode("utf-8")).hexdigest()
    unavailable = [name for name, value in components.items() if value.get("status") == "unavailable"]
    return {
        "schema_version": QUEUE_INPUT_FINGERPRINT_SCHEMA_VERSION,
        "status": "unavailable" if unavailable else "current",
        "fingerprint": digest,
        "components": components,
        "unavailable_components": unavailable,
    }


def queue_input_consistency(
    resolved: ResolvedPaths,
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    current = queue_input_fingerprint(resolved)
    snapshot_fingerprint = str(snapshot.get("queue_input_fingerprint") or "").strip()
    snapshot_components = snapshot.get("queue_input_components")
    snapshot_components = snapshot_components if isinstance(snapshot_components, Mapping) else {}
    changed_inputs: list[str] = []
    component_evidence_complete = True
    for name, _attribute in _COMPONENT_PATH_ATTRIBUTES:
        snapshot_component = snapshot_components.get(name)
        if not isinstance(snapshot_component, Mapping) or not str(snapshot_component.get("sha256") or ""):
            component_evidence_complete = False
            changed_inputs.append(name)
            continue
        current_component = current["components"].get(name) or {}
        if str(snapshot_component.get("sha256") or "") != str(current_component.get("sha256") or ""):
            changed_inputs.append(name)
    if current["status"] == "unavailable" or not snapshot_fingerprint or not component_evidence_complete:
        status = "unavailable"
    elif snapshot_fingerprint != current["fingerprint"]:
        status = "changed"
    else:
        status = "current"
    return {
        "schema_version": "desktop_queue_input_consistency.v1",
        "status": status,
        "snapshot_fingerprint": snapshot_fingerprint,
        "current_fingerprint": current["fingerprint"],
        "changed_inputs": changed_inputs,
        "unavailable_inputs": list(current["unavailable_components"]),
        "launch_blocked": status != "current",
    }


__all__ = [
    "QUEUE_INPUT_FINGERPRINT_SCHEMA_VERSION",
    "queue_input_consistency",
    "queue_input_fingerprint",
]
