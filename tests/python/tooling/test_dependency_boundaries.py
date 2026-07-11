from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
CURRENT_STATUS_PATH = REPO_ROOT / "docs" / "OPEN_WORK_CHECKLIST.md"
sys.path.insert(0, str(REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev"))

import check_dependency_boundaries as dependency_check  # noqa: E402


def write_module(root: Path, relative_path: str, body: str = "") -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")


class DependencyBoundaryTests(unittest.TestCase):
    def test_collects_app_internal_import_edges(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "src/mediapipeline/core/__init__.py")
            write_module(root, "src/mediapipeline/core/config/__init__.py")
            write_module(root, "src/mediapipeline/core/config/load.py")
            write_module(root, "src/mediapipeline/core/api/__init__.py")
            write_module(root, "src/mediapipeline/core/api/routes.py", "from mediapipeline.core.config import load\n")

            report = dependency_check.analyze(root)

            self.assertEqual(len(report.app_imports), 1)
            edge = report.app_imports[0]
            self.assertEqual(edge.source_module, "mediapipeline.core.api.routes")
            self.assertEqual(edge.target_module, "mediapipeline.core.config.load")

    def test_detects_module_and_package_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "src/mediapipeline/core/__init__.py")
            write_module(root, "src/mediapipeline/core/a/__init__.py")
            write_module(root, "src/mediapipeline/core/a/one.py", "from mediapipeline.core.b import two\n")
            write_module(root, "src/mediapipeline/core/b/__init__.py")
            write_module(root, "src/mediapipeline/core/b/two.py", "from mediapipeline.core.a import one\n")

            report = dependency_check.analyze(root)

            self.assertEqual(report.module_cycles, [["mediapipeline.core.a.one", "mediapipeline.core.b.two"]])
            self.assertEqual(report.package_cycles, [["mediapipeline.core.a", "mediapipeline.core.b"]])

    def test_reports_shared_and_forbidden_boundary_imports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for package in (
                "src/mediapipeline/core",
                "src/mediapipeline/core/api",
                "src/mediapipeline/core/config",
                "src/mediapipeline/core/decide",
                "src/mediapipeline/core/observability",
                "src/mediapipeline/core/shared",
                "src/mediapipeline/core/status",
                "src/mediapipeline/core/telemetry",
                "src/mediapipeline/core/ui",
            ):
                write_module(root, f"{package}/__init__.py")
            write_module(root, "src/mediapipeline/core/shared/utils.py", "VALUE = 1\n")
            write_module(root, "src/mediapipeline/core/shared/constants.py", "VALUE = 1\n")
            write_module(root, "src/mediapipeline/core/shared/protocols.py", "VALUE = 1\n")
            write_module(root, "src/mediapipeline/core/decide/processing_decision.py")
            write_module(root, "src/mediapipeline/core/observability/system_metrics.py")
            write_module(root, "src/mediapipeline/core/status/active_jobs.py")
            write_module(root, "src/mediapipeline/core/ui/preferences.py")
            write_module(
                root,
                "src/mediapipeline/core/config/settings.py",
                """
                import mediapipeline.core.shared
                from mediapipeline.core.shared import utils
                from mediapipeline.core.shared.constants import VALUE
                from mediapipeline.core.shared.protocols import VALUE as PROTOCOL_VALUE
                from mediapipeline.core.decide import processing_decision
                """,
            )
            write_module(root, "src/mediapipeline/core/api/commands.py", "from mediapipeline.core.ui import preferences\n")
            write_module(root, "src/mediapipeline/core/observability/status_facade.py", "from mediapipeline.core.status import active_jobs\n")
            write_module(root, "src/mediapipeline/core/telemetry/service.py", "from mediapipeline.core.observability import system_metrics\n")

            report = dependency_check.analyze(root)

            self.assertEqual(len(report.direct_app_shared_imports), 1)
            self.assertEqual(len(report.direct_app_shared_utils_imports), 1)
            self.assertEqual(len(report.direct_app_shared_constants_imports), 1)
            self.assertEqual(len(report.direct_app_shared_protocols_imports), 1)
            self.assertEqual(
                [(edge.source_module, edge.target_module) for edge in report.forbidden_config_imports],
                [("mediapipeline.core.config.settings", "mediapipeline.core.decide.processing_decision")],
            )
            self.assertEqual(len(report.forbidden_api_ui_imports), 1)
            self.assertEqual(len(report.forbidden_observability_status_imports), 1)
            self.assertEqual(len(report.forbidden_telemetry_observability_imports), 1)

    def test_core_to_desktop_imports_are_hard_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "src/mediapipeline/core/__init__.py")
            write_module(root, "src/mediapipeline/core/config/__init__.py")
            write_module(
                root,
                "src/mediapipeline/core/config/settings.py",
                """
                from mediapipeline.desktop import models
                from mediapipeline.desktop.config_keys import KEY_OUTSOURCE
                """,
            )

            report = dependency_check.analyze(root)
            self.assertEqual(
                [(edge.source_module, edge.target_module) for edge in report.forbidden_core_desktop_imports],
                [
                    ("mediapipeline.core.config.settings", "mediapipeline.desktop.models"),
                    ("mediapipeline.core.config.settings", "mediapipeline.desktop.config_keys"),
                ],
            )
            self.assertEqual(dependency_check.main(["--root", str(root), "--max-internal-imports", "10"]), 1)

    def test_main_fails_on_unallowlisted_hard_violation_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "src/mediapipeline/core/__init__.py")
            write_module(root, "src/mediapipeline/core/shared/__init__.py")
            write_module(root, "src/mediapipeline/core/config/__init__.py", "import mediapipeline.core.shared\n")

            self.assertEqual(dependency_check.main(["--root", str(root), "--max-internal-imports", "10"]), 1)

    def test_report_only_keeps_diagnostic_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "src/mediapipeline/core/__init__.py")
            write_module(root, "src/mediapipeline/core/shared/__init__.py")
            write_module(root, "src/mediapipeline/core/config/__init__.py", "import mediapipeline.core.shared\n")

            self.assertEqual(
                dependency_check.main(["--root", str(root), "--max-internal-imports", "10", "--report-only"]),
                0,
            )

    def test_allowlist_suppresses_existing_module_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "src/mediapipeline/core/__init__.py")
            write_module(root, "src/mediapipeline/core/a/__init__.py")
            write_module(root, "src/mediapipeline/core/a/one.py", "from mediapipeline.core.a import two\n")
            write_module(root, "src/mediapipeline/core/a/two.py", "from mediapipeline.core.a import one\n")
            allowlist = root / "allowlist.txt"
            allowlist.write_text(
                "\n".join(
                    [
                        "mediapipeline.core.a.one | mediapipeline.core.a.two | NO_MODULE_CYCLES | Existing test cycle | Owner: test",
                        "mediapipeline.core.a.two | mediapipeline.core.a.one | NO_MODULE_CYCLES | Existing test cycle | Owner: test",
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(dependency_check.main(["--root", str(root), "--allowlist", str(allowlist)]), 0)

    def test_shared_submodule_imports_remain_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "src/mediapipeline/core/__init__.py")
            write_module(root, "src/mediapipeline/core/shared/__init__.py")
            write_module(root, "src/mediapipeline/core/shared/utils.py", "VALUE = 1\n")
            write_module(root, "src/mediapipeline/core/config/__init__.py", "from mediapipeline.core.shared import utils\n")

            self.assertEqual(
                dependency_check.main(["--root", str(root), "--allowlist", str(root / "missing.txt")]),
                0,
            )

    def test_unused_allowlist_entry_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "src/mediapipeline/core/__init__.py")
            allowlist = root / "allowlist.txt"
            allowlist.write_text(
                "mediapipeline.core.old | mediapipeline.core.new | NO_MODULE_CYCLES | Stale test entry | Owner: test\n",
                encoding="utf-8",
            )

            self.assertEqual(dependency_check.main(["--root", str(root), "--allowlist", str(allowlist)]), 1)

    def test_no_core_to_desktop_imports_remain_in_repository(self) -> None:
        report = dependency_check.analyze(REPO_ROOT)

        self.assertEqual(
            report.forbidden_core_desktop_imports,
            [],
            "NO_CORE_TO_DESKTOP is a permanent rule; core modules must not import desktop modules.",
        )

    def test_no_core_to_desktop_allowlist_entries_are_allowed(self) -> None:
        allowlist_entries, allowlist_errors = dependency_check.load_allowlist(dependency_check.DEFAULT_ALLOWLIST_PATH)
        no_core_to_desktop_entries = [
            entry
            for entry in allowlist_entries
            if entry.rule_id == "NO_CORE_TO_DESKTOP"
        ]

        self.assertEqual(
            allowlist_errors,
            [],
            "The dependency-boundary allowlist must not contain permanently enforced rule entries.",
        )
        self.assertEqual(no_core_to_desktop_entries, [])

    def test_core_to_desktop_allowlist_entry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "src/mediapipeline/core/__init__.py")
            allowlist = root / "allowlist.txt"
            allowlist.write_text(
                "mediapipeline.core.config.settings | mediapipeline.desktop.models | NO_CORE_TO_DESKTOP | Legacy test entry | Owner: test\n",
                encoding="utf-8",
            )

            _entries, errors = dependency_check.load_allowlist(allowlist)

            self.assertEqual(len(errors), 1)
            self.assertIn("permanently enforced", errors[0].detail)
            self.assertEqual(dependency_check.main(["--root", str(root), "--allowlist", str(allowlist)]), 1)

    def test_current_boundary_status_documents_core_to_desktop_closure(self) -> None:
        text = CURRENT_STATUS_PATH.read_text(encoding="utf-8")

        self.assertIn("#23 architecture guardrail baseline cleanup", text)
        self.assertIn("all ledger rows are migrated", text)

    def test_current_repository_dependency_check_passes_with_allowlist(self) -> None:
        self.assertEqual(dependency_check.main(["--root", str(REPO_ROOT), "--max-internal-imports", "1"]), 0)


if __name__ == "__main__":
    unittest.main()
