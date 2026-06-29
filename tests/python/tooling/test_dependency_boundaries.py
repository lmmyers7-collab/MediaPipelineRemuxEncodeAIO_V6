from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
PHASE0_BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "dependency_boundaries" / "no_core_to_desktop_phase0_baseline.json"
PHASE0_LEDGER_PATH = REPO_ROOT / "docs" / "implementation" / "architecture-boundary-cleanup" / "EDGE_LEDGER.md"
sys.path.insert(0, str(REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev"))

import check_dependency_boundaries as dependency_check  # noqa: E402


def imported_symbol(import_text: str) -> str:
    if import_text.startswith("from "):
        return import_text.split(" import ", 1)[1]
    if import_text.startswith("import "):
        return "module import"
    return import_text


def core_to_desktop_group_keys(report: dependency_check.DependencyReport) -> set[tuple[str, str, str, tuple[str, ...]]]:
    grouped: dict[tuple[str, str, str], set[str]] = {}
    for edge in report.forbidden_core_desktop_imports:
        grouped.setdefault(
            (edge.source_module, edge.source_path, edge.target_module),
            set(),
        ).add(imported_symbol(edge.import_text))
    return {
        (source_module, source_path, target_module, tuple(sorted(symbols)))
        for (source_module, source_path, target_module), symbols in grouped.items()
    }


def phase0_baseline_group_keys() -> set[tuple[str, str, str, tuple[str, ...]]]:
    payload = json.loads(PHASE0_BASELINE_PATH.read_text(encoding="utf-8"))
    grouped: dict[tuple[str, str, str], set[str]] = {}
    for group in payload["groups"]:
        grouped.setdefault(
            (group["source_module"], group["source_path"], group["target_module"]),
            set(),
        ).update(group["symbols"])
    return {
        (source_module, source_path, target_module, tuple(sorted(symbols)))
        for (source_module, source_path, target_module), symbols in grouped.items()
    }


def phase0_ledger_rows() -> list[dict[str, str]]:
    lines = PHASE0_LEDGER_PATH.read_text(encoding="utf-8").splitlines()
    header = "| id | source module | source path:line | target module | symbols |"
    try:
        section = lines.index("## Phase 0 Edge Ledger")
        start = next(
            index
            for index, line in enumerate(lines[section:], start=section)
            if line.startswith(header)
        )
    except (StopIteration, ValueError) as exc:  # pragma: no cover - failure message from assertion is enough.
        raise AssertionError("Phase 0 edge ledger table header was not found.") from exc

    rows: list[dict[str, str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("| "):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 12:
            continue
        rows.append(
            {
                "id": cells[0],
                "source_module": cells[1],
                "source_path_line": cells[2],
                "target_module": cells[3],
                "symbols": cells[4],
                "category": cells[5],
                "final_owner": cells[6],
                "phase": cells[7],
                "compatibility_export": cells[8],
                "tests": cells[9],
                "allowlist_action": cells[10],
                "status": cells[11],
            }
        )
    return rows


def phase0_ledger_group_keys() -> set[tuple[str, str, str, tuple[str, ...]]]:
    grouped: dict[tuple[str, str, str], set[str]] = {}
    for row in phase0_ledger_rows():
        source_path, _line = row["source_path_line"].rsplit(":", 1)
        symbols = tuple(sorted(part for part in row["symbols"].split("`") if part and not part.startswith(", ")))
        grouped.setdefault(
            (row["source_module"], source_path, row["target_module"]),
            set(),
        ).update(symbols)
    return {
        (source_module, source_path, target_module, tuple(sorted(symbols)))
        for (source_module, source_path, target_module), symbols in grouped.items()
    }


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

    def test_phase0_no_new_core_to_desktop_imports_outside_frozen_baseline(self) -> None:
        report = dependency_check.analyze(REPO_ROOT)
        current_groups = core_to_desktop_group_keys(report)
        baseline_groups = phase0_baseline_group_keys()

        unexpected_groups = sorted(current_groups - baseline_groups)

        self.assertEqual(
            unexpected_groups,
            [],
            "New NO_CORE_TO_DESKTOP import groups must not appear outside the Phase 0 frozen baseline.",
        )

    def test_phase0_frozen_baseline_groups_have_ledger_rows(self) -> None:
        baseline_groups = phase0_baseline_group_keys()
        ledger_groups = phase0_ledger_group_keys()

        missing_rows = sorted(baseline_groups - ledger_groups)

        self.assertEqual(
            missing_rows,
            [],
            "Every frozen NO_CORE_TO_DESKTOP import group needs a Phase 0 ledger row.",
        )

    def test_phase0_no_core_to_desktop_allowlist_entries_have_ledger_rows(self) -> None:
        allowlist_entries, allowlist_errors = dependency_check.load_allowlist(dependency_check.DEFAULT_ALLOWLIST_PATH)
        self.assertEqual(allowlist_errors, [])
        ledger_pairs = {
            (row["source_module"], row["target_module"])
            for row in phase0_ledger_rows()
        }
        allowlist_pairs = {
            (entry.importing_module, entry.imported_module)
            for entry in allowlist_entries
            if entry.rule_id == "NO_CORE_TO_DESKTOP"
        }

        missing_rows = sorted(allowlist_pairs - ledger_pairs)

        self.assertEqual(
            missing_rows,
            [],
            "Every temporary NO_CORE_TO_DESKTOP allowlist entry needs matching Phase 0 ledger coverage.",
        )

    def test_current_repository_dependency_check_passes_with_allowlist(self) -> None:
        self.assertEqual(dependency_check.main(["--root", str(REPO_ROOT), "--max-internal-imports", "1"]), 0)


if __name__ == "__main__":
    unittest.main()
