from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


refresh_summaries = _load_module(
    "refresh_summaries_for_tests",
    REPO_ROOT / "scripts" / "dev" / "refresh_summaries.py",
)
generate_project_index = _load_module(
    "generate_project_index_for_tests",
    REPO_ROOT / "scripts" / "dev" / "generate_project_index.py",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _summary_text(file_path: str, sha256: str = "0" * 64) -> str:
    return "\n".join(
        [
            "---",
            f"file: {file_path}",
            "pipeline_stage: scripts",
            "token_priority: medium",
            "owner_domain: scripts",
            "sha256: " + sha256,
            "---",
            f"# `{file_path}`",
            "",
            "**Purpose:** test summary.",
            "",
        ]
    )


class SummaryIntegrityTests(unittest.TestCase):
    def test_refresh_check_flags_orphan_summary_only_on_full_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "app" / "kept.py"
            orphan = root / "summaries" / "app" / "deleted.py.md"
            summary = root / "summaries" / "app" / "kept.py.md"
            source.parent.mkdir(parents=True)
            source.write_text("print('kept')\n", encoding="utf-8")
            summary.parent.mkdir(parents=True)
            summary.write_text(_summary_text("app/kept.py", _sha(source)), encoding="utf-8")
            orphan.write_text(_summary_text("app/deleted.py"), encoding="utf-8")

            old_root = refresh_summaries.REPO_ROOT
            old_summary = refresh_summaries.SUMMARY_ROOT
            old_roots = refresh_summaries.SOURCE_ROOTS
            old_root_files = refresh_summaries.ROOT_SOURCE_FILES
            try:
                refresh_summaries.REPO_ROOT = root
                refresh_summaries.SUMMARY_ROOT = root / "summaries"
                refresh_summaries.SOURCE_ROOTS = ["app"]
                refresh_summaries.ROOT_SOURCE_FILES = set()

                self.assertEqual(refresh_summaries.cmd_check([source], check_orphans=False), 0)
                self.assertEqual(refresh_summaries.cmd_check([source], check_orphans=True), 1)
                findings = refresh_summaries.orphan_summaries([source])
                self.assertEqual([finding.reason_code for finding in findings], ["SOURCE_FILE_MISSING"])
            finally:
                refresh_summaries.REPO_ROOT = old_root
                refresh_summaries.SUMMARY_ROOT = old_summary
                refresh_summaries.SOURCE_ROOTS = old_roots
                refresh_summaries.ROOT_SOURCE_FILES = old_root_files

    def test_prune_orphans_removes_only_summary_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "app" / "kept.py"
            orphan = root / "summaries" / "app" / "deleted.py.md"
            source.parent.mkdir(parents=True)
            source.write_text("print('kept')\n", encoding="utf-8")
            orphan.parent.mkdir(parents=True)
            orphan.write_text(_summary_text("app/deleted.py"), encoding="utf-8")

            old_root = refresh_summaries.REPO_ROOT
            old_summary = refresh_summaries.SUMMARY_ROOT
            try:
                refresh_summaries.REPO_ROOT = root
                refresh_summaries.SUMMARY_ROOT = root / "summaries"

                self.assertEqual(refresh_summaries.prune_orphan_summaries([source]), 1)
                self.assertFalse(orphan.exists())
            finally:
                refresh_summaries.REPO_ROOT = old_root
                refresh_summaries.SUMMARY_ROOT = old_summary

    def test_project_index_refuses_orphan_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = root / "summaries" / "app" / "deleted.py.md"
            summary.parent.mkdir(parents=True)
            summary.write_text(_summary_text("app/deleted.py"), encoding="utf-8")

            old_root = generate_project_index.REPO_ROOT
            old_summary = generate_project_index.SUMMARY_ROOT
            try:
                generate_project_index.REPO_ROOT = root
                generate_project_index.SUMMARY_ROOT = root / "summaries"

                findings = generate_project_index.orphan_summary_findings([summary])
                self.assertEqual([finding.reason_code for finding in findings], ["SOURCE_FILE_MISSING"])
                self.assertIn("refresh_summaries.py --all --prune-orphans", generate_project_index.render_orphan_summary_findings(findings))
            finally:
                generate_project_index.REPO_ROOT = old_root
                generate_project_index.SUMMARY_ROOT = old_summary


if __name__ == "__main__":
    unittest.main()
