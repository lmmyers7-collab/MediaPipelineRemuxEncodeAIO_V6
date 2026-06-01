from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import check_dependency_boundaries as dependency_check  # noqa: E402


def write_module(root: Path, relative_path: str, body: str = "") -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")


class DependencyBoundaryTests(unittest.TestCase):
    def test_collects_app_internal_import_edges(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "app/__init__.py")
            write_module(root, "app/config/__init__.py")
            write_module(root, "app/config/load.py")
            write_module(root, "app/api/__init__.py")
            write_module(root, "app/api/routes.py", "from app.config import load\n")

            report = dependency_check.analyze(root)

            self.assertEqual(len(report.app_imports), 1)
            edge = report.app_imports[0]
            self.assertEqual(edge.source_module, "app.api.routes")
            self.assertEqual(edge.target_module, "app.config.load")

    def test_detects_module_and_package_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "app/__init__.py")
            write_module(root, "app/a/__init__.py")
            write_module(root, "app/a/one.py", "from app.b import two\n")
            write_module(root, "app/b/__init__.py")
            write_module(root, "app/b/two.py", "from app.a import one\n")

            report = dependency_check.analyze(root)

            self.assertEqual(report.module_cycles, [["app.a.one", "app.b.two"]])
            self.assertEqual(report.package_cycles, [["app.a", "app.b"]])

    def test_reports_shared_and_forbidden_boundary_imports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for package in (
                "app",
                "app/api",
                "app/config",
                "app/decide",
                "app/observability",
                "app/shared",
                "app/status",
                "app/telemetry",
                "app/ui",
            ):
                write_module(root, f"{package}/__init__.py")
            write_module(root, "app/shared/utils.py", "VALUE = 1\n")
            write_module(root, "app/shared/constants.py", "VALUE = 1\n")
            write_module(root, "app/shared/protocols.py", "VALUE = 1\n")
            write_module(root, "app/decide/processing_decision.py")
            write_module(root, "app/observability/system_metrics.py")
            write_module(root, "app/status/active_jobs.py")
            write_module(root, "app/ui/preferences.py")
            write_module(
                root,
                "app/config/settings.py",
                """
                import app.shared
                from app.shared import utils
                from app.shared.constants import VALUE
                from app.shared.protocols import VALUE as PROTOCOL_VALUE
                from app.decide import processing_decision
                """,
            )
            write_module(root, "app/api/commands.py", "from app.ui import preferences\n")
            write_module(root, "app/observability/status_facade.py", "from app.status import active_jobs\n")
            write_module(root, "app/telemetry/service.py", "from app.observability import system_metrics\n")

            report = dependency_check.analyze(root)

            self.assertEqual(len(report.direct_app_shared_imports), 1)
            self.assertEqual(len(report.direct_app_shared_utils_imports), 1)
            self.assertEqual(len(report.direct_app_shared_constants_imports), 1)
            self.assertEqual(len(report.direct_app_shared_protocols_imports), 1)
            self.assertEqual(
                [(edge.source_module, edge.target_module) for edge in report.forbidden_config_imports],
                [("app.config.settings", "app.decide.processing_decision")],
            )
            self.assertEqual(len(report.forbidden_api_ui_imports), 1)
            self.assertEqual(len(report.forbidden_observability_status_imports), 1)
            self.assertEqual(len(report.forbidden_telemetry_observability_imports), 1)

    def test_main_fails_on_unallowlisted_hard_violation_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "app/__init__.py")
            write_module(root, "app/shared/__init__.py")
            write_module(root, "app/config/__init__.py", "import app.shared\n")

            self.assertEqual(dependency_check.main(["--root", str(root), "--max-internal-imports", "10"]), 1)

    def test_report_only_keeps_diagnostic_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "app/__init__.py")
            write_module(root, "app/shared/__init__.py")
            write_module(root, "app/config/__init__.py", "import app.shared\n")

            self.assertEqual(
                dependency_check.main(["--root", str(root), "--max-internal-imports", "10", "--report-only"]),
                0,
            )

    def test_allowlist_suppresses_existing_module_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "app/__init__.py")
            write_module(root, "app/a/__init__.py")
            write_module(root, "app/a/one.py", "from app.a import two\n")
            write_module(root, "app/a/two.py", "from app.a import one\n")
            allowlist = root / "allowlist.txt"
            allowlist.write_text(
                "\n".join(
                    [
                        "app.a.one | app.a.two | NO_MODULE_CYCLES | Existing test cycle | Owner: test",
                        "app.a.two | app.a.one | NO_MODULE_CYCLES | Existing test cycle | Owner: test",
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(dependency_check.main(["--root", str(root), "--allowlist", str(allowlist)]), 0)

    def test_shared_submodule_imports_remain_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "app/__init__.py")
            write_module(root, "app/shared/__init__.py")
            write_module(root, "app/shared/utils.py", "VALUE = 1\n")
            write_module(root, "app/config/__init__.py", "from app.shared import utils\n")

            self.assertEqual(
                dependency_check.main(["--root", str(root), "--allowlist", str(root / "missing.txt")]),
                0,
            )

    def test_unused_allowlist_entry_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_module(root, "app/__init__.py")
            allowlist = root / "allowlist.txt"
            allowlist.write_text(
                "app.old | app.new | NO_MODULE_CYCLES | Stale test entry | Owner: test\n",
                encoding="utf-8",
            )

            self.assertEqual(dependency_check.main(["--root", str(root), "--allowlist", str(allowlist)]), 1)

    def test_current_repository_dependency_check_passes_with_allowlist(self) -> None:
        self.assertEqual(dependency_check.main(["--root", str(REPO_ROOT), "--max-internal-imports", "1"]), 0)


if __name__ == "__main__":
    unittest.main()
