"""Diagnostic-only runtime effective settings evidence contracts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RUNTIME_EFFECTIVE_SETTINGS_SCHEMA: Literal["runtime_effective_settings.v1"] = "runtime_effective_settings.v1"
RUNTIME_EFFECTIVE_SETTINGS_SCOPE: Literal["job"] = "job"
LIBRARY_EFFECTIVE_SETTINGS_REF: Literal["library-only"] = "library-only"

RuntimeEvidenceLayerName = Literal["global", "library", "show", "folder", "file", "source"]

RUNTIME_EVIDENCE_LAYER_ORDER: tuple[RuntimeEvidenceLayerName, ...] = (
    "global",
    "library",
    "show",
    "folder",
    "file",
    "source",
)

RUNTIME_EVIDENCE_LAYER_SOURCES: dict[RuntimeEvidenceLayerName, str] = {
    "global": "active_config",
    "library": "LibraryProfiles[*].overrides",
    "show": "ShowOverrides",
    "folder": "mediapipeline.folder.json",
    "file": "file_overrides.json",
    "source": "ffprobe/probe",
}


class RuntimeEvidenceModel(BaseModel):
    """Strict base model for diagnostic runtime evidence payloads."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RuntimeEvidenceLayer(RuntimeEvidenceModel):
    """Settings/facts supplied by one runtime layer."""

    name: RuntimeEvidenceLayerName
    source: str
    keys: dict[str, Any] = Field(default_factory=dict)
    known: bool = True
    saved_config: bool = True


class RuntimeEffectiveValue(RuntimeEvidenceModel):
    """Final diagnostic value and the layer provenance that produced it."""

    value: Any
    source_layer: RuntimeEvidenceLayerName
    overrode: list[RuntimeEvidenceLayerName] = Field(default_factory=list)


class RuntimeEffectiveSettings(RuntimeEvidenceModel):
    """Diagnostic-only final merged runtime settings evidence."""

    schema_name: Literal["runtime_effective_settings.v1"] = Field(
        default=RUNTIME_EFFECTIVE_SETTINGS_SCHEMA,
        alias="schema",
    )
    scope: Literal["job"] = RUNTIME_EFFECTIVE_SETTINGS_SCOPE
    library_effective_settings_ref: Literal["library-only"] = LIBRARY_EFFECTIVE_SETTINGS_REF
    layers: list[RuntimeEvidenceLayer] = Field(default_factory=list)
    effective_values: dict[str, RuntimeEffectiveValue] = Field(default_factory=dict)
    unsupported_keys: list[str] = Field(default_factory=list)
    ignored_keys: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def runtime_evidence_layer(
    name: RuntimeEvidenceLayerName,
    *,
    source: str | None = None,
    keys: Mapping[str, Any] | None = None,
    known: bool = True,
    saved_config: bool | None = None,
) -> RuntimeEvidenceLayer:
    """Build a single diagnostic layer without changing runtime behavior."""

    layer_source = source if source is not None else RUNTIME_EVIDENCE_LAYER_SOURCES[name]
    layer_saved_config = saved_config if saved_config is not None else name != "source"
    return RuntimeEvidenceLayer(
        name=name,
        source=layer_source,
        keys=_json_mapping(keys),
        known=known,
        saved_config=layer_saved_config,
    )


def default_runtime_evidence_layers() -> list[RuntimeEvidenceLayer]:
    """Return the canonical runtime precedence layer skeleton."""

    return [runtime_evidence_layer(name) for name in RUNTIME_EVIDENCE_LAYER_ORDER]


def normalize_runtime_evidence_layers(
    layers: Iterable[RuntimeEvidenceLayer | Mapping[str, Any]] | None = None,
) -> list[RuntimeEvidenceLayer]:
    """Normalize runtime evidence layer mappings into strict contract models."""

    if layers is None:
        return default_runtime_evidence_layers()

    normalized: list[RuntimeEvidenceLayer] = []
    for layer in layers:
        if isinstance(layer, RuntimeEvidenceLayer):
            normalized.append(layer)
            continue
        normalized.append(RuntimeEvidenceLayer.model_validate(layer))
    return normalized


def effective_values_from_layers(
    layers: Iterable[RuntimeEvidenceLayer | Mapping[str, Any]] | None = None,
) -> dict[str, RuntimeEffectiveValue]:
    """Compute diagnostic final values from ordered layers with provenance."""

    values: dict[str, RuntimeEffectiveValue] = {}
    source_history: dict[str, list[RuntimeEvidenceLayerName]] = {}
    for layer in normalize_runtime_evidence_layers(layers):
        for key, value in layer.keys.items():
            prior_layers = list(source_history.get(key, []))
            values[key] = RuntimeEffectiveValue(
                value=_json_value(value),
                source_layer=layer.name,
                overrode=prior_layers,
            )
            source_history[key] = prior_layers + [layer.name]
    return values


def build_runtime_effective_settings(
    *,
    layers: Iterable[RuntimeEvidenceLayer | Mapping[str, Any]] | None = None,
    effective_values: Mapping[str, RuntimeEffectiveValue | Mapping[str, Any]] | None = None,
    unsupported_keys: Iterable[str] | None = None,
    ignored_keys: Iterable[str] | None = None,
    warnings: Iterable[str] | None = None,
) -> RuntimeEffectiveSettings:
    """Build the diagnostic-only final runtime evidence payload."""

    normalized_layers = normalize_runtime_evidence_layers(layers)
    normalized_values = (
        _runtime_effective_values(effective_values)
        if effective_values is not None
        else effective_values_from_layers(normalized_layers)
    )
    return RuntimeEffectiveSettings(
        layers=normalized_layers,
        effective_values=normalized_values,
        unsupported_keys=_string_list(unsupported_keys),
        ignored_keys=_string_list(ignored_keys),
        warnings=_string_list(warnings),
    )


def runtime_effective_settings_payload(**kwargs: Any) -> dict[str, Any]:
    """Return a JSON-ready runtime evidence payload for diagnostics."""

    return build_runtime_effective_settings(**kwargs).model_dump(mode="json", by_alias=True)


def _runtime_effective_values(
    values: Mapping[str, RuntimeEffectiveValue | Mapping[str, Any]] | None,
) -> dict[str, RuntimeEffectiveValue]:
    normalized: dict[str, RuntimeEffectiveValue] = {}
    for key, value in (values or {}).items():
        normalized[str(key)] = (
            value if isinstance(value, RuntimeEffectiveValue) else RuntimeEffectiveValue.model_validate(value)
        )
    return normalized


def _json_mapping(values: Mapping[str, Any] | None) -> dict[str, Any]:
    return {str(key): _json_value(value) for key, value in (values or {}).items()}


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_value(item) for item in value)
    return value


def _string_list(values: Iterable[str] | None) -> list[str]:
    return [str(value) for value in (values or [])]


__all__ = [
    "LIBRARY_EFFECTIVE_SETTINGS_REF",
    "RUNTIME_EFFECTIVE_SETTINGS_SCHEMA",
    "RUNTIME_EFFECTIVE_SETTINGS_SCOPE",
    "RUNTIME_EVIDENCE_LAYER_ORDER",
    "RUNTIME_EVIDENCE_LAYER_SOURCES",
    "RuntimeEffectiveSettings",
    "RuntimeEffectiveValue",
    "RuntimeEvidenceLayer",
    "RuntimeEvidenceLayerName",
    "build_runtime_effective_settings",
    "default_runtime_evidence_layers",
    "effective_values_from_layers",
    "normalize_runtime_evidence_layers",
    "runtime_effective_settings_payload",
    "runtime_evidence_layer",
]
