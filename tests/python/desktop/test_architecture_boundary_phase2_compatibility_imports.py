from __future__ import annotations

import sys
import unittest
from dataclasses import fields
from importlib import import_module
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))


class ArchitectureBoundaryPhase2CompatibilityImportTests(unittest.TestCase):
    def test_remaining_record_legacy_imports_resolve_to_domain_homes(self) -> None:
        cases = [
            ("AuditRecord", "mediapipeline.core.audit.contracts", ["mediapipeline.core.kernel.models", "mediapipeline.desktop.models"]),
            (
                "CompletedJobRecord",
                "mediapipeline.core.completed.contracts",
                ["mediapipeline.core.kernel.models", "mediapipeline.desktop.models"],
            ),
            (
                "ConfigPreview",
                "mediapipeline.core.config.contracts",
                [
                    "mediapipeline.core.kernel.models",
                    "mediapipeline.core.kernel.models_core",
                    "mediapipeline.desktop.models",
                    "mediapipeline.desktop.models_core",
                ],
            ),
            (
                "ConfigSaveResult",
                "mediapipeline.core.config.contracts",
                [
                    "mediapipeline.core.kernel.models",
                    "mediapipeline.core.kernel.models_core",
                    "mediapipeline.desktop.models",
                    "mediapipeline.desktop.models_core",
                ],
            ),
            (
                "FailureRecord",
                "mediapipeline.core.failures.contracts",
                ["mediapipeline.core.kernel.models", "mediapipeline.desktop.models"],
            ),
            (
                "QueueRecord",
                "mediapipeline.core.queue.contracts",
                ["mediapipeline.core.kernel.models", "mediapipeline.desktop.models"],
            ),
            (
                "Snapshot",
                "mediapipeline.core.status.contracts",
                [
                    "mediapipeline.core.kernel.models",
                    "mediapipeline.core.kernel.models_core",
                    "mediapipeline.desktop.models",
                    "mediapipeline.desktop.models_core",
                ],
            ),
            (
                "TelemetrySnapshot",
                "mediapipeline.core.telemetry.contracts",
                [
                    "mediapipeline.core.kernel.models",
                    "mediapipeline.core.kernel.models_core",
                    "mediapipeline.desktop.models",
                    "mediapipeline.desktop.models_core",
                ],
            ),
        ]

        for symbol, owner_module_name, legacy_module_names in cases:
            with self.subTest(symbol=symbol):
                owner = getattr(import_module(owner_module_name), symbol)
                for legacy_module_name in legacy_module_names:
                    self.assertIs(getattr(import_module(legacy_module_name), symbol), owner)

    def test_resolved_paths_legacy_imports_resolve_to_paths_contract_home(self) -> None:
        from mediapipeline.core.kernel.models import ResolvedPaths as KernelModelsResolvedPaths
        from mediapipeline.core.kernel.models_core import ResolvedPaths as KernelModelsCoreResolvedPaths
        from mediapipeline.core.paths.contracts import ResolvedPaths
        from mediapipeline.desktop.models import ResolvedPaths as DesktopModelsResolvedPaths
        from mediapipeline.desktop.models_core import ResolvedPaths as DesktopModelsCoreResolvedPaths

        self.assertIs(KernelModelsResolvedPaths, ResolvedPaths)
        self.assertIs(KernelModelsCoreResolvedPaths, ResolvedPaths)
        self.assertIs(DesktopModelsResolvedPaths, ResolvedPaths)
        self.assertIs(DesktopModelsCoreResolvedPaths, ResolvedPaths)

    def test_resolved_paths_field_shape_stays_compatible(self) -> None:
        from mediapipeline.core.paths.contracts import ResolvedPaths

        self.assertEqual(
            [field.name for field in fields(ResolvedPaths)],
            [
                "app_root",
                "workspace_root",
                "pipeline_path",
                "config_path",
                "audit_script_path",
                "rerun_script_path",
                "powershell_host",
                "local_base",
                "state_root",
                "runtime_state_root",
                "run_logs_root",
                "active_jobs_path",
                "run_monitor_path",
                "app_state_path",
                "source_movies",
                "source_tv",
                "log_file",
                "progress_file",
                "event_file",
                "pause_flag",
                "stop_flag",
                "stop_after_current_flag",
                "rescan_flag",
                "failed_reports_path",
                "failed_markers_path",
                "pending_push_path",
                "audit_reports_path",
                "queue_snapshot_path",
                "completed_manifest_path",
                "priority_manifest_path",
                "queue_strategy_path",
                "file_overrides_path",
                "audit_score_policy_path",
                "audit_ignore_manifest_path",
                "priority_markers",
                "config_data",
                "config_identity",
                "config_last_good_snapshot_path",
                "persistence_authority",
                "settings_store_status",
                "projection_status",
                "migration_journal",
                "legacy_extras_count",
                "psd1_drift_status",
            ],
        )

    def test_remaining_record_field_shapes_stay_compatible(self) -> None:
        expected_fields = {
            "AuditRecord": ("mediapipeline.core.audit.contracts", ["source_csv", "row"]),
            "CompletedJobRecord": ("mediapipeline.core.completed.contracts", ["sidecar_path", "payload"]),
            "ConfigPreview": (
                "mediapipeline.core.config.contracts",
                ["merged_config", "preview_text", "errors", "warnings", "preserved_keys"],
            ),
            "ConfigSaveResult": ("mediapipeline.core.config.contracts", ["output_path", "backup_path"]),
            "FailureRecord": ("mediapipeline.core.failures.contracts", ["source_json", "payload"]),
            "QueueRecord": (
                "mediapipeline.core.queue.contracts",
                [
                    "source_path",
                    "source_root",
                    "media_type",
                    "is_priority",
                    "priority_reasons",
                    "priority_rank",
                    "sort_name",
                    "display_name",
                    "relative_path",
                    "show_folder",
                    "season_folder",
                    "season_number",
                    "episode_number",
                    "source_mtime",
                    "size_gb",
                    "route_name",
                    "route_reason",
                    "matched_show_override",
                    "queue_index",
                    "queue_total",
                    "phase",
                    "global_order",
                    "manifest_priority_level",
                ],
            ),
            "Snapshot": (
                "mediapipeline.core.status.contracts",
                [
                    "resolved",
                    "current_activity",
                    "status_summary",
                    "log_tail",
                    "progress",
                    "audit_progress",
                    "latest_failure_report",
                    "latest_failure_json",
                    "latest_audit_csv",
                    "latest_priority_csv",
                    "pipeline_events",
                    "last_error",
                ],
            ),
            "TelemetrySnapshot": (
                "mediapipeline.core.telemetry.contracts",
                [
                    "collected_at",
                    "cpu_percent",
                    "cpu_utility_percent",
                    "memory_percent",
                    "memory_used_gb",
                    "memory_total_gb",
                    "gpu_percent",
                    "gpu_encoder_percent",
                    "gpu_name",
                    "gpu_temperature_c",
                    "gpu_memory_percent",
                    "gpu_memory_used_gb",
                    "gpu_memory_total_gb",
                    "gpu_index",
                    "gpu_count",
                    "gpu_rows",
                    "source",
                    "error",
                ],
            ),
        }

        for symbol, (module_name, expected) in expected_fields.items():
            with self.subTest(symbol=symbol):
                self.assertEqual([field.name for field in fields(getattr(import_module(module_name), symbol))], expected)


if __name__ == "__main__":
    unittest.main()
