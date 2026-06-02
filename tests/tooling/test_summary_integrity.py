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
    def test_owner_domain_includes_app_queue_package(self) -> None:
        self.assertEqual(refresh_summaries.owner_domain_for("app/queue/strategy.py"), "queue")
        self.assertEqual(
            refresh_summaries.owner_domain_for("app/queue/policy_parts/rows.py"),
            "queue",
        )
        self.assertEqual(refresh_summaries.owner_domain_for("engine/queue/queue_plan.ps1"), "queue")
        self.assertEqual(
            refresh_summaries.owner_domain_for("app/final_library/promotion.py"),
            "final_library",
        )
        self.assertEqual(
            refresh_summaries.owner_domain_for(
                "app/final_library/promotion_parts/transfer.py"
            ),
            "final_library",
        )
        self.assertEqual(refresh_summaries.owner_domain_for("app/status/service.py"), "observability")
        self.assertEqual(refresh_summaries.owner_domain_for("app/telemetry/service.py"), "observability")
        self.assertEqual(refresh_summaries.owner_domain_for("Pipeline/Audit-MediaLibrary.ps1"), "audit")
        self.assertEqual(refresh_summaries.owner_domain_for("Pipeline/Audit-MediaLibrary/scanner.ps1"), "audit")
        self.assertEqual(
            refresh_summaries.owner_domain_for("Pipeline/Setup-MediaPipeline.ps1"),
            "scripts",
        )
        self.assertEqual(
            refresh_summaries.owner_domain_for(
                "Pipeline/Setup-MediaPipeline/Validation.ps1"
            ),
            "scripts",
        )
        self.assertEqual(
            refresh_summaries.pipeline_stage_for("Pipeline/Audit-MediaLibrary.ps1"),
            "observability",
        )
        self.assertEqual(
            refresh_summaries.pipeline_stage_for("Pipeline/Setup-MediaPipeline.ps1"),
            "setup",
        )

    def test_ass_to_srt_helper_is_indexed_as_subtitle_source(self) -> None:
        self.assertIn("Pipeline/ass_to_srt", refresh_summaries.SOURCE_ROOTS)
        self.assertIn("Pipeline/ass_to_srt.py", refresh_summaries.ROOT_SOURCE_FILES)
        self.assertTrue(refresh_summaries.in_scope_roots(Path("Pipeline/ass_to_srt.py")))
        self.assertTrue(refresh_summaries.in_scope_roots(Path("Pipeline/ass_to_srt/srt.py")))
        self.assertEqual(refresh_summaries.owner_domain_for("Pipeline/ass_to_srt.py"), "subtitles")
        self.assertEqual(
            refresh_summaries.owner_domain_for("Pipeline/ass_to_srt/styles.py"),
            "subtitles",
        )
        self.assertEqual(refresh_summaries.pipeline_stage_for("Pipeline/ass_to_srt.py"), "subtitles")
        self.assertEqual(
            refresh_summaries.pipeline_stage_for("Pipeline/ass_to_srt/ass_events.py"),
            "subtitles",
        )
        self.assertEqual(refresh_summaries.token_priority_for("Pipeline/ass_to_srt.py"), "high")
        self.assertEqual(
            refresh_summaries.token_priority_for("Pipeline/ass_to_srt/text.py"),
            "high",
        )

    def test_file_summaries_doc_lists_active_source_roots(self) -> None:
        doc = (REPO_ROOT / "Docs" / "generated" / "FILE_SUMMARIES.md").read_text(
            encoding="utf-8"
        )

        for root in refresh_summaries.SOURCE_ROOTS:
            with self.subTest(root=root):
                self.assertIn(f"`{root}/`", doc)
        self.assertNotIn("Pipeline/Modules/", doc)
        self.assertNotIn("410 summaries", doc)

    def test_generated_navigation_outputs_are_not_summary_inputs(self) -> None:
        self.assertTrue(
            refresh_summaries.is_volatile_generated_summary_source(
                "Docs/generated/PROJECT_INDEX.md"
            )
        )
        self.assertTrue(
            refresh_summaries.is_volatile_generated_summary_source(
                "Docs/generated/DEPENDENCY_GRAPH.md"
            )
        )
        self.assertFalse(
            refresh_summaries.is_volatile_generated_summary_source(
                "Docs/generated/FILE_SUMMARIES.md"
            )
        )

    def test_project_index_skips_self_referential_generated_nav_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "app" / "kept.py"
            summary = root / "summaries" / "app" / "kept.py.md"
            generated = root / "Docs" / "generated" / "PROJECT_INDEX.md"
            generated_summary = root / "summaries" / "Docs" / "generated" / "PROJECT_INDEX.md.md"
            source.parent.mkdir(parents=True)
            source.write_text("print('kept')\n", encoding="utf-8")
            summary.parent.mkdir(parents=True)
            summary.write_text(_summary_text("app/kept.py", _sha(source)), encoding="utf-8")
            generated.parent.mkdir(parents=True)
            generated.write_text("# generated\n", encoding="utf-8")
            generated_summary.parent.mkdir(parents=True)
            generated_summary.write_text(
                _summary_text("Docs/generated/PROJECT_INDEX.md", _sha(generated)),
                encoding="utf-8",
            )

            old_root = generate_project_index.REPO_ROOT
            old_summary = generate_project_index.SUMMARY_ROOT
            try:
                generate_project_index.REPO_ROOT = root
                generate_project_index.SUMMARY_ROOT = root / "summaries"

                summaries = generate_project_index.iter_summaries()
                self.assertEqual(
                    [path.relative_to(root).as_posix() for path in summaries],
                    ["summaries/app/kept.py.md"],
                )
                rendered = generate_project_index.render_index(summaries)
                self.assertIn("app/kept.py", rendered)
                self.assertNotIn("Docs/generated/PROJECT_INDEX.md", rendered)
            finally:
                generate_project_index.REPO_ROOT = old_root
                generate_project_index.SUMMARY_ROOT = old_summary

    def test_root_schema_json_files_are_explicit_summary_sources(self) -> None:
        self.assertIn("Pipeline/Audit-MediaLibrary", refresh_summaries.SOURCE_ROOTS)
        self.assertIn("Pipeline/Audit-MediaLibrary.ps1", refresh_summaries.ROOT_SOURCE_FILES)
        self.assertIn("Pipeline/Setup-MediaPipeline", refresh_summaries.SOURCE_ROOTS)
        self.assertIn("Pipeline/Setup-MediaPipeline.ps1", refresh_summaries.ROOT_SOURCE_FILES)
        self.assertTrue(
            refresh_summaries.is_source_file(REPO_ROOT / "schemas" / "stages.v1.schema.json")
        )
        self.assertTrue(
            refresh_summaries.is_source_file(
                REPO_ROOT / "scripts" / "dev" / "webview-public-contract.mjs"
            )
        )
        self.assertTrue(
            refresh_summaries.is_source_file(
                REPO_ROOT / "scripts" / "dev" / "start-local-api.bat"
            )
        )
        self.assertTrue(
            refresh_summaries.is_source_file(
                REPO_ROOT / "schemas" / "risky_file_registry.v1.schema.json"
            )
        )
        self.assertFalse(
            refresh_summaries.is_source_file(
                REPO_ROOT / "tests" / "fixtures" / "source_media" / "avi_mpeg2_480p.json"
            )
        )
        self.assertEqual(refresh_summaries.owner_domain_for("schemas/config.v1.schema.json"), "config")
        self.assertEqual(refresh_summaries.owner_domain_for("schemas/stages.v1.schema.json"), "contracts")
        self.assertEqual(
            refresh_summaries.owner_domain_for("schemas/risky_file_registry.v1.schema.json"),
            "scripts",
        )

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
