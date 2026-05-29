from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import check_legacy_removal_readiness as readiness  # noqa: E402


class LegacyRemovalReadinessTests(unittest.TestCase):
    def test_family_file_matching_is_family_specific(self) -> None:
        paths = [
            "DesktopApp/mediapipeline_desktop_app/config_schema.py",
            "DesktopApp/mediapipeline_desktop_app/config_schema_network.py",
            "DesktopApp/mediapipeline_desktop_app/api/command_payloads_settings.py",
            "DesktopApp/mediapipeline_desktop_app/service_status.py",
        ]

        self.assertEqual(
            readiness.family_files(
                readiness.LEGACY_FAMILIES["config_schema"],
                paths,
                file_exists=lambda path: True,
            ),
            (
                "DesktopApp/mediapipeline_desktop_app/config_schema.py",
                "DesktopApp/mediapipeline_desktop_app/config_schema_network.py",
            ),
        )

    def test_external_references_exclude_family_owned_files(self) -> None:
        paths = [
            "DesktopApp/mediapipeline_desktop_app/config_schema.py",
            "DesktopApp/tests/test_config_keys.py",
            "Docs/archive/historical.md",
            "Docs/architecture/CONFIG.md",
        ]
        text_by_path = {
            "DesktopApp/mediapipeline_desktop_app/config_schema.py": "CONFIG_FIELD_DEFINITIONS = ()",
            "DesktopApp/tests/test_config_keys.py": "from mediapipeline_desktop_app.config_schema import CONFIG_FIELD_DEFINITIONS",
            "Docs/archive/historical.md": "config_schema",
            "Docs/architecture/CONFIG.md": "config_schema*.py",
        }

        status = readiness.collect_family_statuses(
            ["config_schema"],
            known_paths=paths,
            read_text=lambda path: text_by_path.get(path, ""),
            file_exists=lambda path: True,
        )[0]

        self.assertEqual(status.files, ("DesktopApp/mediapipeline_desktop_app/config_schema.py",))
        self.assertEqual(
            [(ref.path, ref.category) for ref in status.references],
            [
                ("DesktopApp/tests/test_config_keys.py", "tests"),
                ("Docs/architecture/CONFIG.md", "docs"),
            ],
        )

    def test_python_facade_references_are_exact_legacy_paths(self) -> None:
        paths = [
            "DesktopApp/tests/test_application_facade_queue.py",
            "Docs/architecture/MODULE_MAP.md",
            "ruff.toml",
        ]
        text_by_path = {
            "DesktopApp/tests/test_application_facade_queue.py": "from DesktopApp.tests.test_application_facade import FakeService",
            "Docs/architecture/MODULE_MAP.md": "Legacy path was application/facade_queue.py before app/queue/facade.py.",
            "ruff.toml": "facade_sample_validation_policy was removed",
        }

        status = readiness.collect_family_statuses(
            ["python_facades"],
            known_paths=paths,
            read_text=lambda path: text_by_path.get(path, ""),
            file_exists=lambda path: False,
        )[0]

        self.assertEqual(
            [(ref.path, ref.category, ref.term) for ref in status.references],
            [("Docs/architecture/MODULE_MAP.md", "docs", "application/facade_")],
        )

    def test_python_service_references_ignore_service_named_tests(self) -> None:
        paths = [
            "DesktopApp/tests/test_service_status.py",
            "Docs/testing/TEST_COVERAGE_MATRIX.md",
            "Docs/architecture/MODULE_MAP.md",
        ]
        text_by_path = {
            "DesktopApp/tests/test_service_status.py": "from app.status.service import StatusService",
            "Docs/testing/TEST_COVERAGE_MATRIX.md": "Run test_service_status.py for status coverage.",
            "Docs/architecture/MODULE_MAP.md": "Legacy path was DesktopApp/mediapipeline_desktop_app/service_status.py.",
        }

        status = readiness.collect_family_statuses(
            ["python_services"],
            known_paths=paths,
            read_text=lambda path: text_by_path.get(path, ""),
            file_exists=lambda path: False,
        )[0]

        self.assertEqual(
            [(ref.path, ref.category, ref.term) for ref in status.references],
            [
                (
                    "Docs/architecture/MODULE_MAP.md",
                    "docs",
                    "DesktopApp/mediapipeline_desktop_app/service_",
                )
            ],
        )

    def test_strict_failures_only_include_blocked_families(self) -> None:
        ready = readiness.FamilyStatus("ready", "ready family", (), ())
        blocked = readiness.FamilyStatus(
            "blocked",
            "blocked family",
            ("legacy.py",),
            (),
        )

        self.assertEqual(readiness.strict_failures([ready, blocked]), [blocked])

    def test_pipeline_module_report_classifies_shims(self) -> None:
        paths = [
            "Pipeline/Modules/Routing.ps1",
            "Pipeline/Modules/Audio.ps1",
        ]
        text_by_path = {
            "Pipeline/Modules/Routing.ps1": "Compatibility shim\n. engine\\decide\\routing.ps1",
            "Pipeline/Modules/Audio.ps1": "function Build-AudioArgs {}",
        }

        status = readiness.collect_family_statuses(
            ["pipeline_modules"],
            known_paths=paths,
            read_text=lambda path: text_by_path.get(path, ""),
            file_exists=lambda path: True,
        )[0]

        self.assertEqual(
            status.file_kind_counts,
            (("compatibility_shim", 1), ("implementation", 1)),
        )
        self.assertIn(
            "File kinds: compatibility_shim=1, implementation=1",
            readiness.render_report([status]),
        )

    def test_report_includes_counts_categories_and_examples(self) -> None:
        status = readiness.FamilyStatus(
            "config_schema",
            "Config shims",
            ("DesktopApp/mediapipeline_desktop_app/config_schema.py",),
            (
                readiness.ReferenceMatch(
                    "DesktopApp/tests/test_config_keys.py",
                    "tests",
                    "config_schema",
                ),
            ),
        )

        report = readiness.render_report([status])

        self.assertIn("config_schema: blocked; 1 file(s), 1 external reference(s) [tests=1]", report)
        self.assertIn("DesktopApp/mediapipeline_desktop_app/config_schema.py", report)
        self.assertIn("DesktopApp/tests/test_config_keys.py", report)


if __name__ == "__main__":
    unittest.main()
