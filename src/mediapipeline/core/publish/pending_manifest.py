from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.desktop.contracts import ContractError, PENDING_PUSH_MANIFEST_STATES, PendingPushManifest
from mediapipeline.core.publish.pending_manifest_rows import (
    invalid_contract_pending_manifest_row,
    pending_output_size,
    pending_payload_error_text,
    pending_sidecar_status,
    readable_pending_manifest_row,
    unreadable_pending_manifest_row,
)
from mediapipeline.core.publish.file_io import read_json_file
from mediapipeline.core.publish.pending_paths import path_from_manifest, path_from_texts


def pending_manifest_row(manifest_path: Path) -> dict[str, Any]:
    try:
        manifest = read_json_file(manifest_path, retries=2)
        if not isinstance(manifest, dict):
            raise ValueError("Manifest JSON root is not an object.")
    except Exception as exc:
        return unreadable_pending_manifest_row(manifest_path, exc)

    contract: PendingPushManifest | None = None
    schema_version = str(manifest.get("schema_version") or "").strip()
    if schema_version:
        try:
            contract = PendingPushManifest.from_mapping(manifest)
        except ContractError as exc:
            return invalid_contract_pending_manifest_row(manifest_path, manifest, schema_version=schema_version, exc=exc)

    local_path = path_from_texts(contract.local_file, contract.parked_file) if contract else path_from_manifest(manifest, "local_file", "parked_file")
    server_path = path_from_texts(contract.server_out) if contract else path_from_manifest(manifest, "server_out")
    source_path = path_from_texts(contract.source_path) if contract else path_from_manifest(manifest, "source_path")
    sidecars = contract.sidecar_files if contract else manifest.get("sidecar_files")
    sidecar_paths, missing_sidecars = pending_sidecar_status(sidecars)

    local_exists = bool(local_path and local_path.exists())
    output_size = pending_output_size(manifest, local_path)
    parked_at = contract.parked_at if contract else str(manifest.get("parked_at") or "").strip()
    state = contract.manifest_state if contract else str(manifest.get("manifest_state") or "").strip()
    return readable_pending_manifest_row(
        manifest_path=manifest_path,
        parked_at=parked_at,
        publish_mode=contract.publish_mode if contract else str(manifest.get("publish_mode") or "").strip(),
        route=contract.route if contract else str(manifest.get("route") or "").strip(),
        state=state,
        local_path=local_path,
        local_exists=local_exists,
        server_path=server_path,
        source_path=source_path,
        output_size=output_size,
        sidecar_paths=sidecar_paths,
        missing_sidecars=missing_sidecars,
        schema_version=schema_version,
        error_text=pending_payload_error_text(
            local_path,
            local_exists,
            missing_sidecars,
            server_path=server_path,
            state=state,
            known_states=PENDING_PUSH_MANIFEST_STATES,
            require_destination=True,
            require_state=True,
        ),
    )
