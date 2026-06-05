from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop import config_keys
from mediapipeline.core.config.library_profiles import LIBRARY_OVERRIDE_KEYS_BY_GROUP
from mediapipeline.core.config.metadata import CONFIG_FIELD_DEFINITIONS
from mediapipeline.core.config.metadata_network import NETWORK_CONFIG_DEFAULTS
from mediapipeline.contracts.config import Config


VOBSUB_LIBRARY_OVERRIDE_KEYS = {
    "ConvertVobSubToSrt",
    "DropVobSubAfterConversion",
    "VobSubExtractLanguages",
    "VobSubOcrToolPath",
    "VobSubOcrTimeoutSeconds",
    "TreatVobSubSignsSongsAsForced",
}
FRIENDLY_LABEL_KEYS = {
    "ProcessingStrategy",
    "EnforcementMode",
    "OutputSizeCheck",
    "EncoderQualityPreset",
    "EncodeTargetMode",
    "EncoderSpeedPreset",
    "Processing Strategy",
    "Enforcement Mode",
    "Output Size Check",
}
EVIDENCE_ONLY_KEYS = {
    "library_effective_settings",
    "runtime_effective_settings",
}


def _powershell_registry_keys() -> set[str]:
    module_text = (find_repo_root(Path(__file__)) / "ops" / "pipeline" / "engine" / "config" / "config_keys.ps1").read_text(encoding="utf-8")
    match = re.search(
        r"\$script:MediaPipelineConfigKeyRegistry\s*=\s*\[ordered\]@\{(?P<body>.*?)^\}",
        module_text,
        re.S | re.M,
    )
    if match is None:
        raise AssertionError("PowerShell config key registry was not found.")
    return set(re.findall(r"=\s*'([^']+)'", match.group("body")))


def _powershell_library_override_keys() -> set[str]:
    engine_paths = find_repo_root(Path(__file__)) / "ops" / "pipeline" / "engine" / "paths"
    module_text = "\n".join(
        (engine_paths / path).read_text(encoding="utf-8")
        for path in ("output_path_planning.ps1", "effective_settings.ps1")
    )
    match = re.search(
        r"function\s+Get-MediaPipelineLibraryOverrideConfigKeys\s*\{(?P<body>.*?)^\}",
        module_text,
        re.S | re.M,
    )
    if match is None:
        raise AssertionError("PowerShell library override key allowlist was not found.")
    return set(re.findall(r"'([^']+)'", match.group("body")))


def _pipeline_json_schema_keys() -> set[str]:
    schema = json.loads((find_repo_root(Path(__file__)) / "ops" / "pipeline" / "config" / "schemas" / "media_pipeline_config.schema.json").read_text(encoding="utf-8"))
    return set(schema["properties"])


def _backend_library_override_keys() -> set[str]:
    return {key for keys in LIBRARY_OVERRIDE_KEYS_BY_GROUP.values() for key in keys}


class ConfigKeyRegistryTests(unittest.TestCase):
    def test_python_settings_schema_keys_are_registered(self) -> None:
        schema_keys = tuple(str(field["key"]) for field in CONFIG_FIELD_DEFINITIONS)

        missing = sorted(set(schema_keys) - config_keys.ALL_CONFIG_KEYS)

        self.assertEqual(missing, [])
        self.assertEqual(tuple(config_keys.PYTHON_SCHEMA_CONFIG_KEYS), schema_keys)

    def test_network_defaults_are_registered(self) -> None:
        self.assertEqual(tuple(config_keys.NETWORK_CONFIG_KEYS), tuple(NETWORK_CONFIG_DEFAULTS))
        self.assertLessEqual(set(config_keys.NETWORK_CONFIG_KEYS), config_keys.ALL_CONFIG_KEYS)

    def test_pipeline_config_order_matches_powershell_schema_order(self) -> None:
        engine_config = find_repo_root(Path(__file__)) / "ops" / "pipeline" / "engine" / "config"
        module_text = "\n".join(
            (engine_config / path).read_text(encoding="utf-8")
            for path in ("config_schema.ps1", "schema_keys.ps1")
        )
        match = re.search(
            r"function Get-MediaPipelineConfigOrderedKeys \{\s*return @\((?P<body>.*?)\)\s*\}",
            module_text,
            re.S,
        )
        self.assertIsNotNone(match)
        ps_order = tuple(re.findall(r"'([^']+)'", match.group("body") if match else ""))

        self.assertEqual(tuple(config_keys.CONFIG_KEY_ORDER), ps_order)
        self.assertEqual(config_keys.KEY_CONFIG_SCHEMA_VERSION, ps_order[0])

    def test_cross_surface_config_key_sets_reject_python_powershell_schema_drift(self) -> None:
        powershell_keys = _powershell_registry_keys()
        json_schema_keys = _pipeline_json_schema_keys()

        self.assertEqual(powershell_keys, config_keys.ALL_CONFIG_KEYS)
        self.assertEqual(set(Config.model_fields), config_keys.ALL_CONFIG_KEYS)
        self.assertEqual(json_schema_keys, set(config_keys.CONFIG_KEY_ORDER))
        self.assertEqual(json_schema_keys & set(config_keys.NETWORK_CONFIG_KEYS), set())
        self.assertEqual((FRIENDLY_LABEL_KEYS | EVIDENCE_ONLY_KEYS) & powershell_keys, set())
        self.assertEqual((FRIENDLY_LABEL_KEYS | EVIDENCE_ONLY_KEYS) & set(Config.model_fields), set())
        self.assertEqual((FRIENDLY_LABEL_KEYS | EVIDENCE_ONLY_KEYS) & json_schema_keys, set())

    def test_cross_surface_library_override_allowlist_rejects_python_powershell_drift(self) -> None:
        powershell_overrides = _powershell_library_override_keys()
        backend_overrides = _backend_library_override_keys()
        metadata_keys = {str(field["key"]) for field in CONFIG_FIELD_DEFINITIONS}
        global_or_evidence_keys = {
            config_keys.KEY_CONFIG_SCHEMA_VERSION,
            config_keys.KEY_SOURCE_MOVIES,
            config_keys.KEY_SOURCE_TV,
            config_keys.KEY_OUTSOURCE,
            config_keys.KEY_LIBRARY_PROFILES,
            config_keys.KEY_LOCAL_BASE,
            config_keys.KEY_FINAL_LIBRARY_PROMOTION_RULES,
        } | EVIDENCE_ONLY_KEYS | FRIENDLY_LABEL_KEYS

        self.assertEqual(powershell_overrides, backend_overrides)
        self.assertLessEqual(backend_overrides, metadata_keys)
        self.assertLessEqual(backend_overrides, config_keys.ALL_CONFIG_KEYS)
        self.assertLessEqual(VOBSUB_LIBRARY_OVERRIDE_KEYS, backend_overrides)
        self.assertEqual(global_or_evidence_keys & powershell_overrides, set())

    def test_known_source_safety_keys_have_named_constants(self) -> None:
        for key in (
            config_keys.KEY_SOURCE_MOVIES,
            config_keys.KEY_SOURCE_TV,
            config_keys.KEY_OUTSOURCE,
            config_keys.KEY_LOCAL_BASE,
            config_keys.KEY_DEFERRED_PUBLISH,
            config_keys.KEY_SKIP_STABILITY_CHECK,
            config_keys.KEY_ENABLE_INTEGRITY_CHECK,
            config_keys.KEY_ALLOW_SYSTEM_TOOLS,
            config_keys.KEY_REPROCESS_ALL,
        ):
            self.assertIn(key, config_keys.ALL_CONFIG_KEYS)

    def test_network_runtime_config_lookups_use_named_constants(self) -> None:
        network_keys = (
            config_keys.KEY_NETWORK_ROLE,
            config_keys.KEY_COORDINATOR_PORT,
            config_keys.KEY_COORDINATOR_BIND_ADDRESS,
            config_keys.KEY_COORDINATOR_HEARTBEAT_TIMEOUT_MINS,
            config_keys.KEY_COORDINATOR_AUTH_TOKEN,
            config_keys.KEY_WORKER_COORDINATOR_URL,
            config_keys.KEY_WORKER_NAME,
            config_keys.KEY_WORKER_AUTH_TOKEN,
            config_keys.KEY_WORKER_POLL_INTERVAL_SECS,
            config_keys.KEY_WORKER_SOURCE_PATH_MAP,
            config_keys.KEY_WORKER_CONFIG_OVERRIDES,
        )
        encode_override_keys = (
            config_keys.KEY_VIDEO_CODEC,
            config_keys.KEY_VIDEO_PRESET,
            config_keys.KEY_VIDEO_QUALITY,
            config_keys.KEY_OUTPUT_CONTAINER,
            config_keys.KEY_ENCODE_TUNING_PRESET,
            config_keys.KEY_ENCODE_LADDER,
            config_keys.KEY_EXTRA_VIDEO_FLAGS,
            config_keys.KEY_FALLBACK_CPU_QUALITY,
            config_keys.KEY_ROUTING_PROFILE,
            config_keys.KEY_ROUTE_THRESHOLD_MODE,
            config_keys.KEY_MOVIE_ROUTE_MAX_VIDEO_BITRATE_MBPS,
            config_keys.KEY_TV_ROUTE_MAX_VIDEO_BITRATE_MBPS,
            config_keys.KEY_ALLOW_H264_REMUX_IF_PLEX_COMPATIBLE,
            config_keys.KEY_H264_REMUX_MAX_BITRATE_MBPS,
            config_keys.KEY_H264_REMUX_MAX_HEIGHT,
            config_keys.KEY_SIZE_GUARD_MODE,
            config_keys.KEY_MAX_ENCODE_GROWTH_PERCENT,
            config_keys.KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT,
        )
        paths = (
            "mediapipeline.desktop/network/__init__.py",
            "mediapipeline.desktop/network/coordinator.py",
            "mediapipeline.desktop/network/coordinator_policy.py",
            "mediapipeline.desktop/network/encode_config_snapshot.py",
            "mediapipeline.desktop/network/worker.py",
            "mediapipeline.desktop/controllers/network_controller.py",
        )
        source_root = find_repo_root(Path(__file__)) / "src"
        pattern = re.compile(
            r"\.get\(\s*['\"](" + "|".join(re.escape(key) for key in network_keys + encode_override_keys) + r")['\"]"
        )

        violations: list[str] = []
        for relative_path in paths:
            path = source_root / relative_path
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for match in pattern.finditer(text):
                violations.append(f"{relative_path}: raw config lookup for {match.group(1)}")

        self.assertEqual(violations, [])

    def test_settings_policy_config_lookups_use_named_constants(self) -> None:
        settings_policy_keys = (
            config_keys.KEY_ALLOW_NO_AUDIO,
            config_keys.KEY_ALLOW_SYSTEM_TOOLS,
            config_keys.KEY_AUDIO_DOWNMIX_MODE,
            config_keys.KEY_AUDIO_MAX_CHANNELS,
            config_keys.KEY_AUDIO_PASSTHROUGH_PROFILE,
            config_keys.KEY_AUDIO_TRANSCODE_BITRATE,
            config_keys.KEY_AUDIO_TRANSCODE_CODEC,
            config_keys.KEY_BDPGS_EXTRACT_LANGUAGES,
            config_keys.KEY_BDPGS_OCR_TESSDATA_PATH,
            config_keys.KEY_BDPGS_OCR_TOOL_PATH,
            config_keys.KEY_CLEANUP_REMOTE_STAGING,
            config_keys.KEY_COMPATIBILITY_ENCODE_GROWTH_PERCENT,
            config_keys.KEY_COMPATIBLE_AUDIO_CODECS,
            config_keys.KEY_CONVERT_BDPGS_TO_SRT,
            config_keys.KEY_CONVERT_TX3G_TO_SRT,
            config_keys.KEY_CPU_ENCODE_PRESET,
            config_keys.KEY_CPU_ENCODE_PROCESS_PRIORITY,
            config_keys.KEY_CREATE_EXTERNAL_TX3G_SRT_SIDECARS,
            config_keys.KEY_DEFERRED_PUBLISH,
            config_keys.KEY_DROP_ASS_AFTER_CONVERSION,
            config_keys.KEY_DROP_BDPGS_AFTER_CONVERSION,
            config_keys.KEY_DROP_TX3G_AFTER_CONVERSION,
            config_keys.KEY_ENABLE_INTEGRITY_CHECK,
            config_keys.KEY_ENCODE_LADDER,
            config_keys.KEY_ENCODE_TUNING_PRESET,
            config_keys.KEY_EXTRA_VIDEO_FLAGS,
            config_keys.KEY_FILE_LOG_LEVEL,
            config_keys.KEY_KEEP_SIGNS_AND_SONGS,
            config_keys.KEY_MAX_ENCODE_GROWTH_PERCENT,
            config_keys.KEY_MIN_FREE_SPACE_GB,
            config_keys.KEY_OUTPUT_CONTAINER,
            config_keys.KEY_OUTPUT_SIZE_MULTIPLIER,
            config_keys.KEY_OUTSOURCE,
            config_keys.KEY_OUTSOURCE_MIN_FREE_SPACE_GB,
            config_keys.KEY_PREFERRED_DEFAULT_AUDIO_LANGUAGES,
            config_keys.KEY_PRIORITY_MARKERS,
            config_keys.KEY_PROCESSED_INDEX_REFRESH_SECONDS,
            config_keys.KEY_REMUX_SAFE_VIDEO_CODECS,
            config_keys.KEY_REMOVE_KARAOKE,
            config_keys.KEY_ROBOCOPY_FLAGS,
            config_keys.KEY_ROBOCOPY_TIMEOUT_SECONDS,
            config_keys.KEY_ROUTE_THRESHOLD_MODE,
            config_keys.KEY_ROUTING_PROFILE,
            config_keys.KEY_SIZE_GUARD_MODE,
            config_keys.KEY_SKIP_STABILITY_CHECK,
            config_keys.KEY_SOURCE_SCAN_INTERVAL_SECONDS,
            config_keys.KEY_STRIP_FORMATTING,
            config_keys.KEY_SUB_KEEP_LANGUAGES,
            config_keys.KEY_TRANSIENT_FAILURE_RETRY_LIMIT,
            config_keys.KEY_TX3G_EXTRACT_LANGUAGES,
            config_keys.KEY_VALID_EXTENSIONS,
            config_keys.KEY_VIDEO_CODEC,
        )
        paths = (
            "mediapipeline/core/config/settings_policy.py",
            "mediapipeline/core/processes/audit_policy.py",
            "mediapipeline/core/paths/layout.py",
            "mediapipeline/desktop/application/settings_risk_policy.py",
            "mediapipeline/desktop/application/sample_validation/policy_alignment.py",
            "mediapipeline/desktop/application/sample_validation/readiness.py",
            "mediapipeline/desktop/application/sample_validation/record.py",
        )
        source_root = find_repo_root(Path(__file__)) / "src"
        pattern = re.compile(
            r"(?:\.get\(\s*|\[\s*|_(?:bool|text|number|list)_value\(\s*config,\s*|_config_bool\(\s*config,\s*)"
            r"['\"](" + "|".join(re.escape(key) for key in settings_policy_keys) + r")['\"]"
        )

        violations: list[str] = []
        for relative_path in paths:
            path = source_root / relative_path
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for match in pattern.finditer(text):
                violations.append(f"{relative_path}: raw config lookup for {match.group(1)}")

        self.assertEqual(violations, [])

    def test_desktop_package_registered_config_lookups_use_named_constants(self) -> None:
        source_root = find_repo_root(Path(__file__)) / "src" / "mediapipeline" / "desktop"
        pattern = re.compile(
            r"(?:"
            r"(?:config|config_data|values|after_config)\.get\(\s*"
            r"|values\[\s*"
            r"|_(?:bool|text|number|list)_value\(\s*config,\s*"
            r"|_config_bool\(\s*config,\s*"
            r")['\"]("
            + "|".join(re.escape(key) for key in sorted(config_keys.ALL_CONFIG_KEYS, key=len, reverse=True))
            + r")['\"]"
        )

        violations: list[str] = []
        for path in source_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for match in pattern.finditer(text):
                violations.append(f"{path.relative_to(source_root.parent)}: raw config lookup for {match.group(1)}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
