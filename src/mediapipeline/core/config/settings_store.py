"""Versioned JSON authority for desktop settings persistence."""

from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping

from pydantic import ValidationError

from mediapipeline.contracts.config import CONFIG_SCHEMA_VERSION, Config
from mediapipeline.contracts.config_coercion import _normalize_config_term_list
from mediapipeline.contracts.config_defaults import _is_exact_legacy_packaged_rename_movie_remove_terms
from mediapipeline.core.config.file_io import atomic_write_text
from mediapipeline.core.config.load import load_psd1_mapping
from mediapipeline.core.config.validation import canonical_config_key_spelling_errors
from mediapipeline.core.kernel.config_key_aliases import CONFIG_KEY_ALIASES
from mediapipeline.core.kernel.config_key_order import ALL_CONFIG_KEYS
from mediapipeline.core.kernel.config_locations import (
    SETTINGS_PROJECTION_NAME,
    SETTINGS_STORE_NAME,
    user_settings_projection_path,
    user_settings_store_path,
)
from mediapipeline.core.config.contracts import ConfigSaveResult
from mediapipeline.core.paths.contracts import ResolvedPaths


SETTINGS_STORE_SCHEMA_VERSION = "desktop_settings_store.v1"
SETTINGS_PROJECTION_SCHEMA_VERSION = "desktop_settings_projection.v1"
SETTINGS_IMPORT_PREVIEW_SCHEMA_VERSION = "desktop_settings_import_psd1_preview.v1"
SETTINGS_IMPORT_RESULT_SCHEMA_VERSION = "desktop_settings_import_psd1_result.v1"
SETTINGS_LAST_GOOD_DIR_NAME = "ConfigSnapshots"
LOCALBASE_CONFIG_MIRROR_DIR = Path("State") / "Config"

Psd1Loader = Callable[[Path, str | None], Mapping[str, Any]]


class SettingsStoreError(RuntimeError):
    """Raised when the JSON settings authority cannot be trusted."""


@dataclass(frozen=True)
class SettingsMigrationResult:
    settings: dict[str, Any]
    legacy_extras: dict[str, Any] = field(default_factory=dict)
    migrations_applied: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def utc_now_text() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _json_text(data: Mapping[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def settings_store_path_for_config(config_path: Path) -> Path:
    return user_settings_store_path() or config_path.parent / SETTINGS_STORE_NAME


def settings_projection_path_for_config(config_path: Path) -> Path:
    return user_settings_projection_path() or settings_store_path_for_config(config_path).with_name(SETTINGS_PROJECTION_NAME)


def settings_store_last_good_path(store_path: Path) -> Path:
    return store_path.parent / SETTINGS_LAST_GOOD_DIR_NAME / SETTINGS_STORE_NAME


def settings_projection_last_good_path(projection_path: Path) -> Path:
    return projection_path.parent / SETTINGS_LAST_GOOD_DIR_NAME / SETTINGS_PROJECTION_NAME


def _localbase_store_mirror_path(settings: Mapping[str, Any]) -> Path | None:
    raw = str(settings.get("LocalBase") or "").strip()
    if not raw:
        return None
    return Path(raw) / LOCALBASE_CONFIG_MIRROR_DIR / SETTINGS_STORE_NAME


def _localbase_projection_mirror_path(settings: Mapping[str, Any]) -> Path | None:
    raw = str(settings.get("LocalBase") or "").strip()
    if not raw:
        return None
    return Path(raw) / LOCALBASE_CONFIG_MIRROR_DIR / SETTINGS_PROJECTION_NAME


def _contract_error_messages(exc: ValidationError) -> list[str]:
    messages: list[str] = []
    for item in exc.errors():
        loc = item.get("loc") if isinstance(item, dict) else None
        message = str(item.get("msg") or "Config contract validation failed.") if isinstance(item, dict) else str(item)
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        if loc:
            messages.append(f"{'.'.join(str(part) for part in loc)}: {message}")
        else:
            messages.append(message)
    return messages


_CANONICAL_BY_CASEFOLD = {str(key).casefold(): str(key) for key in ALL_CONFIG_KEYS}
_ALIASES_BY_CASEFOLD = {str(alias).casefold(): (str(alias), str(target)) for alias, target in CONFIG_KEY_ALIASES.items()}


def migrate_imported_settings_mapping(raw: Mapping[str, Any]) -> SettingsMigrationResult:
    """Split imported PSD1 values into canonical settings and inert extras."""

    settings_input: dict[str, Any] = {}
    legacy_extras: dict[str, Any] = {}
    migrations_applied: list[str] = []
    errors: list[str] = []
    seen_source: dict[str, str] = {}

    for raw_key, raw_value in dict(raw or {}).items():
        key = str(raw_key or "").strip()
        if not key:
            errors.append("Config contains a blank settings key.")
            continue
        value = _json_safe(raw_value)
        canonical = ""
        alias_source = ""
        if key in ALL_CONFIG_KEYS:
            canonical = key
        else:
            casefold = key.casefold()
            case_match = _CANONICAL_BY_CASEFOLD.get(casefold)
            if case_match:
                errors.append(f"Invalid settings key: {key!r}; use canonical key {case_match}.")
                canonical = case_match
            else:
                alias_entry = _ALIASES_BY_CASEFOLD.get(casefold)
                if alias_entry:
                    alias_source, canonical = alias_entry
                    migrations_applied.append(f"alias:{alias_source}->{canonical}")

        if canonical:
            previous = seen_source.get(canonical)
            if previous is not None and previous != key:
                errors.append(
                    f"Config contains duplicate keys for {canonical}: {previous!r} and {key!r}; use only canonical key {canonical}."
                )
                continue
            seen_source[canonical] = key
            if key == canonical or alias_source:
                settings_input[canonical] = value
            continue
        legacy_extras[key] = value

    if errors:
        return SettingsMigrationResult(
            settings=dict(settings_input),
            legacy_extras=legacy_extras,
            migrations_applied=sorted(set(migrations_applied)),
            errors=sorted(set(errors)),
        )

    raw_movie_remove_terms = _normalize_config_term_list(settings_input.get("RenameMovieRemoveTerms"))
    if _is_exact_legacy_packaged_rename_movie_remove_terms(raw_movie_remove_terms):
        migrations_applied.append("normalize:RenameMovieRemoveTerms:legacy-packaged-default")

    try:
        model = Config.model_validate(settings_input)
    except ValidationError as exc:
        return SettingsMigrationResult(
            settings=dict(settings_input),
            legacy_extras=legacy_extras,
            migrations_applied=sorted(set(migrations_applied)),
            errors=_contract_error_messages(exc),
        )

    full_settings = {
        key: value
        for key, value in model.model_dump(mode="json").items()
        if key in ALL_CONFIG_KEYS
    }
    duplicate_errors = canonical_config_key_spelling_errors(full_settings)
    return SettingsMigrationResult(
        settings=full_settings,
        legacy_extras=legacy_extras,
        migrations_applied=sorted(set(migrations_applied)),
        errors=duplicate_errors,
    )


def _store_envelope(
    *,
    settings: Mapping[str, Any],
    legacy_extras: Mapping[str, Any],
    migrations_applied: list[str],
    source_psd1_path: Path,
    source_psd1_sha256: str,
) -> dict[str, Any]:
    config_schema_version = settings.get("ConfigSchemaVersion") or CONFIG_SCHEMA_VERSION
    return {
        "schema_version": SETTINGS_STORE_SCHEMA_VERSION,
        "config_schema_version": config_schema_version,
        "settings": dict(settings),
        "legacy_extras": dict(legacy_extras),
        "migrations_applied": list(migrations_applied),
        "source_psd1_path": str(source_psd1_path),
        "source_psd1_sha256": source_psd1_sha256,
        "updated_at_utc": utc_now_text(),
    }


def _projection_values(envelope: Mapping[str, Any]) -> dict[str, Any]:
    values = dict(envelope.get("settings") if isinstance(envelope.get("settings"), dict) else {})
    extras = envelope.get("legacy_extras")
    if isinstance(extras, dict):
        values.update(extras)
    return values


def _read_store_envelope(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SettingsStoreError(f"Settings JSON store is invalid: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SettingsStoreError(f"Settings JSON store must contain an object: {path}")
    if raw.get("schema_version") != SETTINGS_STORE_SCHEMA_VERSION:
        raise SettingsStoreError(f"Settings JSON store schema is unsupported: {raw.get('schema_version')!r}")
    if not isinstance(raw.get("settings"), dict):
        raise SettingsStoreError("Settings JSON store is missing a settings object.")
    if not isinstance(raw.get("legacy_extras"), dict):
        raw["legacy_extras"] = {}
    if not isinstance(raw.get("migrations_applied"), list):
        raw["migrations_applied"] = []
    return dict(raw)


def _restore_last_good_store(store_path: Path) -> dict[str, Any]:
    last_good = settings_store_last_good_path(store_path)
    if not last_good.is_file():
        raise SettingsStoreError(
            f"Settings JSON store is invalid and no verified last-good JSON exists: {store_path}"
        )
    restored = _read_store_envelope(last_good)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(last_good, store_path)
    return restored


def _store_metadata(
    *,
    authority: str,
    status: str,
    store_path: Path,
    projection_path: Path,
    migration_journal: list[str],
    legacy_extras_count: int,
    psd1_drift_status: str,
    projection_status: str,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    status_state = "blocked" if errors else "ready" if status in {"loaded", "imported", "saved", "restored"} else "warning"
    return {
        "persistence_authority": authority,
        "settings_store_status": {
            "schema_version": "desktop_settings_store_status.v1",
            "status": status,
            "status_state": status_state,
            "store_path": str(store_path),
            "exists": store_path.is_file(),
            "errors": list(errors or []),
            "warnings": list(warnings or []),
        },
        "projection_status": {
            "schema_version": "desktop_settings_projection_status.v1",
            "status": projection_status,
            "projection_path": str(projection_path),
            "exists": projection_path.is_file(),
        },
        "migration_journal": list(migration_journal),
        "legacy_extras_count": int(legacy_extras_count),
        "psd1_drift_status": psd1_drift_status,
    }


def _set_service_metadata(service: object, config_path: Path, metadata: Mapping[str, Any]) -> None:
    try:
        current = getattr(service, "_settings_store_metadata_by_config", None)
        if not isinstance(current, dict):
            current = {}
            service._settings_store_metadata_by_config = current
        current[str(config_path)] = dict(metadata)
    except Exception:
        return


def settings_store_metadata_for_service(service: object, config_path: Path) -> dict[str, Any]:
    current = getattr(service, "_settings_store_metadata_by_config", None)
    if isinstance(current, dict):
        metadata = current.get(str(config_path))
        if isinstance(metadata, dict):
            return dict(metadata)
    store_path = settings_store_path_for_config(config_path)
    projection_path = settings_projection_path_for_config(config_path)
    return _store_metadata(
        authority="json_store",
        status="unavailable",
        store_path=store_path,
        projection_path=projection_path,
        migration_journal=[],
        legacy_extras_count=0,
        psd1_drift_status="unknown",
        projection_status="unknown",
        warnings=["Settings store metadata is not available for this resolved config."],
    )


def _psd1_loader_default(path: Path, powershell_host: str | None) -> Mapping[str, Any]:
    result = load_psd1_mapping(path, powershell_host)
    if not result.ok:
        raise SettingsStoreError(result.error or f"Config PSD1 import failed: {path}")
    return result.data


def _projection_manifest(
    *,
    envelope: Mapping[str, Any],
    store_path: Path,
    store_text: str,
    config_path: Path,
    psd1_text: str,
) -> dict[str, Any]:
    settings = envelope.get("settings") if isinstance(envelope.get("settings"), dict) else {}
    legacy_extras = envelope.get("legacy_extras") if isinstance(envelope.get("legacy_extras"), dict) else {}
    return {
        "schema_version": SETTINGS_PROJECTION_SCHEMA_VERSION,
        "settings_store_path": str(store_path),
        "settings_store_sha256": _sha256_text(store_text),
        "psd1_path": str(config_path),
        "psd1_sha256": _sha256_text(psd1_text),
        "generated_at_utc": utc_now_text(),
        "config_schema_version": envelope.get("config_schema_version"),
        "known_key_count": len(settings),
        "legacy_extras_count": len(legacy_extras),
    }


def _validate_projection_round_trip(
    psd1_text: str,
    projection_values: Mapping[str, Any],
    powershell_host: str | None,
    *,
    psd1_loader: Psd1Loader | None = None,
) -> None:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="mediapipeline-settings-projection-") as tmp_dir:
        candidate = Path(tmp_dir) / "candidate.psd1"
        candidate.write_text(psd1_text, encoding="utf-8", newline="")
        loaded = dict((psd1_loader or _psd1_loader_default)(candidate, powershell_host))
    expected = _json_safe(dict(projection_values))
    actual = _json_safe(loaded)
    mismatches = [key for key in sorted(expected) if not _roundtrip_value_equal(expected.get(key), actual.get(key))]
    missing = [key for key in sorted(expected) if key not in actual]
    extra = [key for key in sorted(actual) if key not in expected]
    if mismatches or missing or extra:
        detail = []
        if mismatches:
            detail.append(f"value mismatch: {', '.join(mismatches[:12])}")
        if missing:
            detail.append(f"missing after reload: {', '.join(missing[:12])}")
        if extra:
            detail.append(f"unexpected after reload: {', '.join(extra[:12])}")
        raise SettingsStoreError("Settings PSD1 projection did not round-trip through PowerShell import: " + "; ".join(detail))


def _roundtrip_value_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, int | float) and isinstance(right, int | float):
        return abs(float(left) - float(right)) <= 0.0001
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _roundtrip_value_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=False)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            return False
        return all(_roundtrip_value_equal(left[key], right[key]) for key in left)
    return left == right


def _backup_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes() if path.exists() else None
    except OSError:
        return None


def _restore_bytes(path: Path, data: bytes | None) -> None:
    if data is None:
        with contextlib.suppress(OSError):
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_last_good_snapshots(envelope: Mapping[str, Any], projection: Mapping[str, Any], store_path: Path, projection_path: Path) -> None:
    store_text = _json_text(envelope)
    projection_text = _json_text(projection)
    atomic_write_text(settings_store_last_good_path(store_path), store_text)
    atomic_write_text(settings_projection_last_good_path(projection_path), projection_text)
    settings = envelope.get("settings") if isinstance(envelope.get("settings"), dict) else {}
    local_store = _localbase_store_mirror_path(settings)
    local_projection = _localbase_projection_mirror_path(settings)
    if local_store is not None:
        with contextlib.suppress(OSError):
            atomic_write_text(local_store, store_text)
    if local_projection is not None:
        with contextlib.suppress(OSError):
            atomic_write_text(local_projection, projection_text)


def _promote_envelope_and_projection(
    service: object,
    resolved: ResolvedPaths,
    envelope: Mapping[str, Any],
    *,
    create_backup: bool,
    psd1_loader: Psd1Loader | None = None,
) -> ConfigSaveResult:
    store_path = settings_store_path_for_config(resolved.config_path)
    projection_path = settings_projection_path_for_config(resolved.config_path)
    store_text = _json_text(envelope)
    projection_values = _projection_values(envelope)
    serializer = getattr(service, "serialize_psd1_document", None)
    if not callable(serializer):
        raise SettingsStoreError("Settings PSD1 serializer is not available.")
    psd1_text = str(serializer(projection_values))

    validator = getattr(service, "validate_config_document_for_save", None)
    if callable(validator):
        validation_errors, _validation_warnings = validator(
            psd1_text,
            config_values=dict(projection_values),
            powershell_host=resolved.powershell_host,
        )
        if validation_errors:
            raise SettingsStoreError("Settings PSD1 projection failed validation: " + "; ".join(validation_errors))
    _validate_projection_round_trip(
        psd1_text,
        projection_values,
        resolved.powershell_host,
        psd1_loader=psd1_loader,
    )

    projection = _projection_manifest(
        envelope=envelope,
        store_path=store_path,
        store_text=store_text,
        config_path=resolved.config_path,
        psd1_text=psd1_text,
    )
    projection_text = _json_text(projection)
    backups = {
        store_path: _backup_bytes(store_path),
        resolved.config_path: _backup_bytes(resolved.config_path),
        projection_path: _backup_bytes(projection_path),
    }
    try:
        atomic_write_text(store_path, store_text)
        saver = getattr(service, "save_config_document", None)
        if callable(saver):
            result = saver(
                resolved.config_path,
                psd1_text,
                create_backup,
                config_values=dict(projection_values),
                powershell_host=resolved.powershell_host,
            )
        else:
            atomic_write_text(resolved.config_path, psd1_text)
            result = ConfigSaveResult(output_path=resolved.config_path, backup_path=None)
        atomic_write_text(projection_path, projection_text)
        _write_last_good_snapshots(envelope, projection, store_path, projection_path)
        return result
    except Exception:
        for path, data in backups.items():
            _restore_bytes(path, data)
        raise


def _source_psd1_sha256(config_path: Path) -> str:
    if not config_path.is_file():
        return ""
    try:
        return _file_sha256(config_path)
    except OSError:
        return ""


def _load_existing_store_or_restore(store_path: Path) -> tuple[dict[str, Any], str, list[str]]:
    warnings: list[str] = []
    try:
        return _read_store_envelope(store_path), "loaded", warnings
    except SettingsStoreError as exc:
        restored = _restore_last_good_store(store_path)
        warnings.append(str(exc))
        warnings.append(f"Restored settings JSON authority from {settings_store_last_good_path(store_path)}.")
        return restored, "restored", warnings


def load_settings_authority_for_service(
    service: object,
    config_path: Path,
    powershell_host: str | None,
    *,
    psd1_loader: Psd1Loader | None = None,
) -> dict[str, Any]:
    store_path = settings_store_path_for_config(config_path)
    projection_path = settings_projection_path_for_config(config_path)
    resolved = ResolvedPaths(
        app_root=getattr(service, "app_root", config_path.parent),
        workspace_root=getattr(service, "workspace_root", config_path.parent),
        pipeline_path=config_path.parent / "MediaPipeline.ps1",
        config_path=config_path,
        audit_script_path=config_path.parent / "Audit-MediaLibrary.ps1",
        rerun_script_path=config_path.parent / "Invoke-RerunCsv.ps1",
        powershell_host=powershell_host,
    )

    if store_path.is_file():
        envelope, status, warnings = _load_existing_store_or_restore(store_path)
        before_hash = _source_psd1_sha256(config_path)
        result = _promote_envelope_and_projection(
            service,
            resolved,
            envelope,
            create_backup=config_path.exists(),
            psd1_loader=psd1_loader,
        )
        _ = result
        after_hash = _source_psd1_sha256(config_path)
        psd1_drift_status = "in_sync" if before_hash == after_hash else "drifted_regenerated"
        metadata = _store_metadata(
            authority="json_store",
            status=status,
            store_path=store_path,
            projection_path=projection_path,
            migration_journal=[str(item) for item in envelope.get("migrations_applied", [])],
            legacy_extras_count=len(envelope.get("legacy_extras") or {}),
            psd1_drift_status=psd1_drift_status,
            projection_status="regenerated",
            warnings=warnings,
        )
        _set_service_metadata(service, config_path, metadata)
        return dict(envelope.get("settings") or {})

    if not config_path.exists():
        metadata = _store_metadata(
            authority="json_store",
            status="missing",
            store_path=store_path,
            projection_path=projection_path,
            migration_journal=[],
            legacy_extras_count=0,
            psd1_drift_status="missing",
            projection_status="missing",
            errors=[f"No settings JSON store or PSD1 config exists: {store_path}; {config_path}"],
        )
        _set_service_metadata(service, config_path, metadata)
        return {}

    raw = dict((psd1_loader or _psd1_loader_default)(config_path, powershell_host))
    migrated = migrate_imported_settings_mapping(raw)
    if migrated.errors:
        metadata = _store_metadata(
            authority="json_store",
            status="import_blocked",
            store_path=store_path,
            projection_path=projection_path,
            migration_journal=migrated.migrations_applied,
            legacy_extras_count=len(migrated.legacy_extras),
            psd1_drift_status="not_imported",
            projection_status="blocked",
            errors=migrated.errors,
            warnings=migrated.warnings,
        )
        _set_service_metadata(service, config_path, metadata)
        raise SettingsStoreError("Settings PSD1 import blocked: " + "; ".join(migrated.errors))
    envelope = _store_envelope(
        settings=migrated.settings,
        legacy_extras=migrated.legacy_extras,
        migrations_applied=["imported_psd1_to_json_store", *migrated.migrations_applied],
        source_psd1_path=config_path,
        source_psd1_sha256=_source_psd1_sha256(config_path),
    )
    _promote_envelope_and_projection(
        service,
        resolved,
        envelope,
        create_backup=config_path.exists(),
        psd1_loader=psd1_loader,
    )
    metadata = _store_metadata(
        authority="json_store",
        status="imported",
        store_path=store_path,
        projection_path=projection_path,
        migration_journal=list(envelope["migrations_applied"]),
        legacy_extras_count=len(migrated.legacy_extras),
        psd1_drift_status="imported_from_psd1",
        projection_status="generated",
    )
    _set_service_metadata(service, config_path, metadata)
    return dict(migrated.settings)


def save_settings_authority_for_service(
    service: object,
    resolved: ResolvedPaths,
    candidate_settings: Mapping[str, Any],
    *,
    psd1_loader: Psd1Loader | None = None,
) -> ConfigSaveResult:
    store_path = settings_store_path_for_config(resolved.config_path)
    projection_path = settings_projection_path_for_config(resolved.config_path)
    current_legacy: dict[str, Any] = {}
    current_migrations: list[str] = []
    if store_path.is_file():
        current = _read_store_envelope(store_path)
        current_legacy = dict(current.get("legacy_extras") or {})
        current_migrations = [str(item) for item in current.get("migrations_applied") or []]

    migrated = migrate_imported_settings_mapping(candidate_settings)
    if migrated.errors:
        raise SettingsStoreError("Settings candidate failed JSON authority validation: " + "; ".join(migrated.errors))
    legacy_extras = {**current_legacy, **migrated.legacy_extras}
    migrations = sorted({*current_migrations, *migrated.migrations_applied})
    envelope = _store_envelope(
        settings=migrated.settings,
        legacy_extras=legacy_extras,
        migrations_applied=migrations,
        source_psd1_path=resolved.config_path,
        source_psd1_sha256=_source_psd1_sha256(resolved.config_path),
    )
    result = _promote_envelope_and_projection(
        service,
        resolved,
        envelope,
        create_backup=True,
        psd1_loader=psd1_loader,
    )
    metadata = _store_metadata(
        authority="json_store",
        status="saved",
        store_path=store_path,
        projection_path=projection_path,
        migration_journal=migrations,
        legacy_extras_count=len(legacy_extras),
        psd1_drift_status="saved_projection",
        projection_status="generated",
    )
    _set_service_metadata(service, resolved.config_path, metadata)
    return result


def import_psd1_settings_preview_for_service(
    service: object,
    resolved: ResolvedPaths,
    *,
    psd1_loader: Psd1Loader | None = None,
) -> dict[str, Any]:
    _ = service
    raw = dict((psd1_loader or _psd1_loader_default)(resolved.config_path, resolved.powershell_host))
    migrated = migrate_imported_settings_mapping(raw)
    return {
        "schema_version": SETTINGS_IMPORT_PREVIEW_SCHEMA_VERSION,
        "source_psd1_path": str(resolved.config_path),
        "settings": dict(migrated.settings),
        "legacy_extras": dict(migrated.legacy_extras),
        "legacy_extras_count": len(migrated.legacy_extras),
        "migrations_applied": list(migrated.migrations_applied),
        "errors": list(migrated.errors),
        "warnings": list(migrated.warnings),
        "can_import": migrated.ok,
        "writes_config": False,
        "writes_store": False,
    }


def import_psd1_settings_for_service(
    service: object,
    resolved: ResolvedPaths,
    *,
    psd1_loader: Psd1Loader | None = None,
) -> dict[str, Any]:
    preview = import_psd1_settings_preview_for_service(service, resolved, psd1_loader=psd1_loader)
    if preview["errors"]:
        raise SettingsStoreError("Settings PSD1 import blocked: " + "; ".join(preview["errors"]))
    imported_values = {**dict(preview["settings"]), **dict(preview["legacy_extras"])}
    result = save_settings_authority_for_service(
        service,
        resolved,
        imported_values,
        psd1_loader=psd1_loader,
    )
    return {
        "schema_version": SETTINGS_IMPORT_RESULT_SCHEMA_VERSION,
        "source_psd1_path": str(resolved.config_path),
        "settings_store_path": str(settings_store_path_for_config(resolved.config_path)),
        "projection_path": str(settings_projection_path_for_config(resolved.config_path)),
        "config_path": str(result.output_path),
        "backup_path": str(result.backup_path or ""),
        "legacy_extras_count": int(preview["legacy_extras_count"]),
        "migrations_applied": list(preview["migrations_applied"]),
        "writes_config": True,
        "writes_store": True,
    }


__all__ = [
    "SETTINGS_IMPORT_PREVIEW_SCHEMA_VERSION",
    "SETTINGS_IMPORT_RESULT_SCHEMA_VERSION",
    "SETTINGS_PROJECTION_SCHEMA_VERSION",
    "SETTINGS_STORE_SCHEMA_VERSION",
    "SettingsMigrationResult",
    "SettingsStoreError",
    "import_psd1_settings_for_service",
    "import_psd1_settings_preview_for_service",
    "load_settings_authority_for_service",
    "migrate_imported_settings_mapping",
    "save_settings_authority_for_service",
    "settings_projection_path_for_config",
    "settings_store_metadata_for_service",
    "settings_store_path_for_config",
]
