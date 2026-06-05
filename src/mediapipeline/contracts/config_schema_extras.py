"""JSON Schema extra builders for the configuration contract."""

from __future__ import annotations

from typing import Any

def _override_group_schema(keys: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {key: {} for key in keys},
    }

def _library_profiles_schema_extra(override_keys_by_group: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    media_keys = (
        *override_keys_by_group["video"],
        *override_keys_by_group["subtitles"],
        *override_keys_by_group["audio"],
    )
    override_group_properties = {
        group: _override_group_schema(keys)
        for group, keys in override_keys_by_group.items()
    }
    return {
        "items": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "enabled": {"type": "boolean"},
                "designation": {"type": "string", "enum": ["movie", "tv", "auto", "mixed", "custom"]},
                "source_path": {"type": "string"},
                "output_path": {"type": "string"},
                "promotion_enabled": {"type": "boolean"},
                "promotion_destination": {"type": "string"},
                "overrides": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": override_group_properties,
                },
                "editor_overrides": _override_group_schema(override_keys_by_group["editor"]),
                "media_overrides": _override_group_schema(media_keys),
                "default_tracking": {"type": "object", "additionalProperties": True},
            },
        }
    }

def _final_library_promotion_rules_schema_extra() -> dict[str, Any]:
    return {
        "items": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "id": {"type": "string"},
                "label": {"type": "string"},
                "enabled": {"type": "boolean"},
                "source_root": {"type": "string"},
                "output_root": {"type": "string"},
                "destination_root": {"type": "string"},
                "library_id": {"type": "string"},
                "designation": {"type": "string"},
            },
        }
    }

def _converter_disabled_blocks_drop_schema(convert_key: str, drop_key: str) -> dict[str, Any]:
    return {
        "if": {
            "anyOf": [
                {"not": {"required": [convert_key]}},
                {
                    "required": [convert_key],
                    "properties": {convert_key: {"const": False}},
                },
            ]
        },
        "then": {
            "not": {
                "required": [drop_key],
                "properties": {drop_key: {"const": True}},
            }
        },
    }

def _converter_enabled_blocks_blank_path_schema(convert_key: str, path_key: str) -> dict[str, Any]:
    return {
        "if": {
            "required": [convert_key],
            "properties": {convert_key: {"const": True}},
        },
        "then": {
            "not": {
                "required": [path_key],
                "properties": {path_key: {"type": "string", "pattern": r"^\s*$"}},
            }
        },
    }

def _subtitle_cross_field_schema_extra() -> dict[str, Any]:
    return {
        "allOf": [
            {
                "if": {
                    "required": ["ConvertTx3gToSrt"],
                    "properties": {"ConvertTx3gToSrt": {"const": False}},
                },
                "then": {
                    "not": {
                        "anyOf": [
                            {
                                "required": ["DropTx3gAfterConversion"],
                                "properties": {"DropTx3gAfterConversion": {"const": True}},
                            },
                            {
                                "required": ["CreateExternalTx3gSrtSidecars"],
                                "properties": {"CreateExternalTx3gSrtSidecars": {"const": True}},
                            },
                        ]
                    }
                },
            },
            _converter_disabled_blocks_drop_schema("ConvertBdpgsToSrt", "DropBdpgsAfterConversion"),
            _converter_enabled_blocks_blank_path_schema("ConvertBdpgsToSrt", "BdpgsOcrToolPath"),
            _converter_disabled_blocks_drop_schema("ConvertVobSubToSrt", "DropVobSubAfterConversion"),
            _converter_enabled_blocks_blank_path_schema("ConvertVobSubToSrt", "VobSubOcrToolPath"),
        ]
    }
