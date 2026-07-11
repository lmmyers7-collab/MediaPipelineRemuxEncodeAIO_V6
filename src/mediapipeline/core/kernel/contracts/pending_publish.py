from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .base import ContractError, bool_field, int_field, list_field, require_mapping, require_schema_version, text_field


PENDING_PUSH_MANIFEST_SCHEMA_VERSION = "pending_push_manifest.v1"
PENDING_PUSH_RETRY_LIMIT = 3
PENDING_PUSH_MANIFEST_STATES = {
    "pending_move",
    "parked",
    "parked_recovered",
    "missing_payload",
    "retry_copy_failed",
    "retry_reveal_failed",
    "retry_sidecar_file_failed",
    "retry_sidecar_backup_failed",
    "retry_sidecar_failed",
    "complete",
    "published",
}
PENDING_PUSH_MANIFEST_DRAINABLE_STATES = {
    "parked",
    "parked_recovered",
    "missing_payload",
    "retry_copy_failed",
    "retry_reveal_failed",
    "retry_sidecar_file_failed",
    "retry_sidecar_backup_failed",
    "retry_sidecar_failed",
}
PENDING_PUSH_MANIFEST_REQUIRED_TEXT_FIELDS = (
    "pipeline_version",
    "publish_transaction_id",
    "manifest_state",
    "local_file",
    "server_out",
    "route",
    "source_identity_v2",
    "source_identity_v2_algorithm",
    "source_path",
)
PENDING_PUSH_MANIFEST_REQUIRED_ARRAY_FIELDS = (
    "sidecar_files",
    "tx3g_srt_tracks",
    "tx3g_srt_failures",
    "bdpgs_srt_failures",
    "vobsub_srt_failures",
    "tx3g_embedded_srt_tracks",
    "bdpgs_embedded_srt_tracks",
    "vobsub_embedded_srt_tracks",
)


def _required_text_field(payload: Mapping[str, Any], key: str) -> str:
    value = text_field(payload, key).strip()
    if not value:
        raise ContractError(f"{key} is required and cannot be blank")
    return value


def _required_int_field(payload: Mapping[str, Any], key: str, *, minimum: int = 0) -> int:
    if key not in payload or payload.get(key) in (None, ""):
        raise ContractError(f"{key} is required")
    value = int_field(payload, key)
    if value < minimum:
        raise ContractError(f"{key} must be >= {minimum}")
    return value


def _required_list_field(payload: Mapping[str, Any], key: str) -> list[Any]:
    if key not in payload:
        raise ContractError(f"{key} is required")
    return list_field(payload, key)


@dataclass(frozen=True)
class PendingPushManifest:
    schema_version: str
    parked_at: str
    product_version: str
    pipeline_version: str
    publish_transaction_id: str
    manifest_state: str
    local_file: str
    original_local_file: str
    parked_file: str
    server_out: str
    route: str
    route_reason_code: str
    route_reason: str
    media_type: str
    source_identity: str
    source_identity_v2: str
    source_identity_v2_algorithm: str
    source_path: str
    source_size: int
    source_mtime_utc: str
    output_size: int
    publish_mode: str
    output_sha256: str = ""
    output_hash_algorithm: str = ""
    drain_attempt_id: str = ""
    drain_attempt_started_at: str = ""
    drain_attempt_completed_at: str = ""
    drain_attempt_status: str = ""
    drain_attempt_error: str = ""
    replacement_existing_final: bool = False
    replacement_prior_final_size: int = 0
    replacement_prior_final_sha256: str = ""
    replacement_transaction_id: str = ""
    sidecar_files: list[Any] = field(default_factory=list)
    tx3g_srt_tracks: list[Any] = field(default_factory=list)
    tx3g_srt_failures: list[Any] = field(default_factory=list)
    bdpgs_srt_failures: list[Any] = field(default_factory=list)
    vobsub_srt_failures: list[Any] = field(default_factory=list)
    tx3g_embedded_srt_tracks: list[Any] = field(default_factory=list)
    bdpgs_embedded_srt_tracks: list[Any] = field(default_factory=list)
    vobsub_embedded_srt_tracks: list[Any] = field(default_factory=list)
    tx3g_srt_conversion_enabled: bool = False
    tx3g_external_srt_sidecars_enabled: bool = False
    drop_tx3g_after_conversion: bool = False
    bdpgs_srt_conversion_enabled: bool = False
    drop_bdpgs_after_conversion: bool = False
    vobsub_srt_conversion_enabled: bool = False
    drop_vobsub_after_conversion: bool = False
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | Any) -> PendingPushManifest:
        data = require_mapping(payload, "pending push manifest")
        schema_version = require_schema_version(data, PENDING_PUSH_MANIFEST_SCHEMA_VERSION)
        for field_name in PENDING_PUSH_MANIFEST_REQUIRED_TEXT_FIELDS:
            _required_text_field(data, field_name)
        manifest_state = _required_text_field(data, "manifest_state")
        if manifest_state not in PENDING_PUSH_MANIFEST_STATES:
            raise ContractError(f"manifest_state must be a known pending-publish state; got {manifest_state}")
        for field_name in PENDING_PUSH_MANIFEST_REQUIRED_ARRAY_FIELDS:
            _required_list_field(data, field_name)
        output_size = _required_int_field(data, "output_size")
        output_sha256 = text_field(data, "output_sha256").strip()
        output_hash_algorithm = text_field(data, "output_hash_algorithm").strip()
        if output_sha256:
            if len(output_sha256) != 64 or any(char not in "0123456789abcdefABCDEF" for char in output_sha256):
                raise ContractError("output_sha256 must be a 64-character hexadecimal SHA-256 value")
            if output_hash_algorithm != "SHA256":
                raise ContractError("output_hash_algorithm must be SHA256 when output_sha256 is present")
        elif output_hash_algorithm:
            raise ContractError("output_hash_algorithm requires output_sha256")
        return cls(
            schema_version=schema_version,
            parked_at=text_field(data, "parked_at"),
            product_version=text_field(data, "product_version"),
            pipeline_version=_required_text_field(data, "pipeline_version"),
            publish_transaction_id=_required_text_field(data, "publish_transaction_id"),
            manifest_state=manifest_state,
            local_file=_required_text_field(data, "local_file"),
            original_local_file=text_field(data, "original_local_file"),
            parked_file=text_field(data, "parked_file"),
            server_out=_required_text_field(data, "server_out"),
            route=_required_text_field(data, "route"),
            route_reason_code=text_field(data, "route_reason_code"),
            route_reason=text_field(data, "route_reason"),
            media_type=text_field(data, "media_type"),
            source_identity=text_field(data, "source_identity"),
            source_identity_v2=_required_text_field(data, "source_identity_v2"),
            source_identity_v2_algorithm=_required_text_field(data, "source_identity_v2_algorithm"),
            source_path=_required_text_field(data, "source_path"),
            source_size=int_field(data, "source_size"),
            source_mtime_utc=text_field(data, "source_mtime_utc"),
            output_size=output_size,
            publish_mode=text_field(data, "publish_mode"),
            output_sha256=output_sha256,
            output_hash_algorithm=output_hash_algorithm,
            drain_attempt_id=text_field(data, "drain_attempt_id"),
            drain_attempt_started_at=text_field(data, "drain_attempt_started_at"),
            drain_attempt_completed_at=text_field(data, "drain_attempt_completed_at"),
            drain_attempt_status=text_field(data, "drain_attempt_status"),
            drain_attempt_error=text_field(data, "drain_attempt_error"),
            replacement_existing_final=bool_field(data, "replacement_existing_final"),
            replacement_prior_final_size=max(0, int_field(data, "replacement_prior_final_size")),
            replacement_prior_final_sha256=text_field(data, "replacement_prior_final_sha256").strip(),
            replacement_transaction_id=text_field(data, "replacement_transaction_id"),
            sidecar_files=_required_list_field(data, "sidecar_files"),
            tx3g_srt_tracks=_required_list_field(data, "tx3g_srt_tracks"),
            tx3g_srt_failures=_required_list_field(data, "tx3g_srt_failures"),
            bdpgs_srt_failures=_required_list_field(data, "bdpgs_srt_failures"),
            vobsub_srt_failures=_required_list_field(data, "vobsub_srt_failures"),
            tx3g_embedded_srt_tracks=_required_list_field(data, "tx3g_embedded_srt_tracks"),
            bdpgs_embedded_srt_tracks=_required_list_field(data, "bdpgs_embedded_srt_tracks"),
            vobsub_embedded_srt_tracks=_required_list_field(data, "vobsub_embedded_srt_tracks"),
            tx3g_srt_conversion_enabled=bool_field(data, "tx3g_srt_conversion_enabled"),
            tx3g_external_srt_sidecars_enabled=bool_field(data, "tx3g_external_srt_sidecars_enabled"),
            drop_tx3g_after_conversion=bool_field(data, "drop_tx3g_after_conversion"),
            bdpgs_srt_conversion_enabled=bool_field(data, "bdpgs_srt_conversion_enabled"),
            drop_bdpgs_after_conversion=bool_field(data, "drop_bdpgs_after_conversion"),
            vobsub_srt_conversion_enabled=bool_field(data, "vobsub_srt_conversion_enabled"),
            drop_vobsub_after_conversion=bool_field(data, "drop_vobsub_after_conversion"),
            raw=data,
        )
