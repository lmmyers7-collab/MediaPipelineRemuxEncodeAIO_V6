from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev"))

import check_legacy_removal_readiness as readiness  # noqa: E402


class LegacyRemovalReadinessTests(unittest.TestCase):
    def test_family_file_matching_is_family_specific(self) -> None:
        paths = [
            "src/mediapipeline/desktop/config_schema.py",
            "src/mediapipeline/desktop/config_schema_network.py",
            "src/mediapipeline/desktop/api/command_payloads_settings.py",
            "src/mediapipeline/desktop/service_status.py",
        ]

        self.assertEqual(
            readiness.family_files(
                readiness.LEGACY_FAMILIES["config_schema"],
                paths,
                file_exists=lambda path: True,
            ),
            (
                "src/mediapipeline/desktop/config_schema.py",
                "src/mediapipeline/desktop/config_schema_network.py",
            ),
        )

    def test_external_references_exclude_family_owned_files(self) -> None:
        paths = [
            "src/mediapipeline/desktop/config_schema.py",
            "tests/python/desktop/test_config_keys.py",
            "docs/archive/historical.md",
            "docs/architecture/CONFIG.md",
        ]
        text_by_path = {
            "src/mediapipeline/desktop/config_schema.py": "CONFIG_FIELD_DEFINITIONS = ()",
            "tests/python/desktop/test_config_keys.py": "from mediapipeline.desktop.config_schema import CONFIG_FIELD_DEFINITIONS",
            "docs/archive/historical.md": "config_schema",
            "docs/architecture/CONFIG.md": "config_schema*.py",
        }

        status = readiness.collect_family_statuses(
            ["config_schema"],
            known_paths=paths,
            read_text=lambda path: text_by_path.get(path, ""),
            file_exists=lambda path: True,
        )[0]

        self.assertEqual(status.files, ("src/mediapipeline/desktop/config_schema.py",))
        self.assertEqual(
            [(ref.path, ref.category) for ref in status.references],
            [
                ("docs/architecture/CONFIG.md", "docs"),
                ("tests/python/desktop/test_config_keys.py", "tests"),
            ],
        )

    def test_python_facade_references_are_exact_legacy_paths(self) -> None:
        paths = [
            "tests/python/desktop/test_application_facade_queue.py",
            "docs/architecture/MODULE_MAP.md",
            "ruff.toml",
        ]
        text_by_path = {
            "tests/python/desktop/test_application_facade_queue.py": "from tests.python.desktop.test_application_facade import FakeService",
            "docs/architecture/MODULE_MAP.md": "Legacy path was application/facade_queue.py before app/queue/facade.py.",
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
            [("docs/architecture/MODULE_MAP.md", "docs", "application/facade_")],
        )

    def test_python_service_references_ignore_service_named_tests(self) -> None:
        paths = [
            "tests/python/desktop/test_service_status.py",
            "docs/testing/TEST_COVERAGE_MATRIX.md",
            "docs/architecture/MODULE_MAP.md",
        ]
        text_by_path = {
            "tests/python/desktop/test_service_status.py": "from mediapipeline.core.status.service import StatusService",
            "docs/testing/TEST_COVERAGE_MATRIX.md": "Run test_service_status.py for status coverage.",
            "docs/architecture/MODULE_MAP.md": "Legacy path was src/mediapipeline/desktop/service_status.py.",
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
                    "docs/architecture/MODULE_MAP.md",
                    "docs",
                    "src/mediapipeline/desktop/service_",
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
            "Pipeline/Modules/Routing.ps1": "Compatibility shim\n. ops\pipeline\engine\\decide\\routing.ps1",
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
            ("src/mediapipeline/desktop/config_schema.py",),
            (
                readiness.ReferenceMatch(
                    "tests/python/desktop/test_config_keys.py",
                    "tests",
                    "config_schema",
                ),
            ),
        )

        report = readiness.render_report([status])

        self.assertIn("config_schema: blocked; 1 file(s), 1 external reference(s) [tests=1]", report)
        self.assertIn("src/mediapipeline/desktop/config_schema.py", report)
        self.assertIn("tests/python/desktop/test_config_keys.py", report)


if __name__ == "__main__":
    unittest.main()
