from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


refresh_summaries = _load_module(
    "refresh_summaries_for_tests",
    REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev" / "refresh_summaries.py",
)
generate_project_index = _load_module(
    "generate_project_index_for_tests",
    REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev" / "generate_project_index.py",
)
generate_feature_file_map = _load_module(
    "generate_feature_file_map_for_tests",
    REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev" / "generate_feature_file_map.py",
)


def _sha(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


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
    def test_owner_domain_includes_core_queue_package(self) -> None:
        self.assertEqual(refresh_summaries.owner_domain_for("src/mediapipeline/core/queue/strategy.py"), "queue")
        self.assertEqual(
            refresh_summaries.owner_domain_for("src/mediapipeline/core/queue/policy_parts/rows.py"),
            "queue",
        )
        self.assertEqual(refresh_summaries.owner_domain_for("ops/pipeline/engine/queue/queue_plan.ps1"), "queue")
        self.assertEqual(
            refresh_summaries.owner_domain_for("src/mediapipeline/core/final_library/promotion.py"),
            "final_library",
        )
        self.assertEqual(
            refresh_summaries.owner_domain_for(
                "src/mediapipeline/core/final_library/promotion_parts/transfer.py"
            ),
            "final_library",
        )
        self.assertEqual(refresh_summaries.owner_domain_for("src/mediapipeline/core/status/service.py"), "observability")
        self.assertEqual(refresh_summaries.owner_domain_for("src/mediapipeline/core/telemetry/service.py"), "observability")
        self.assertEqual(refresh_summaries.owner_domain_for("ops/pipeline/entrypoints/Audit-MediaLibrary.ps1"), "audit")
        self.assertEqual(refresh_summaries.owner_domain_for("ops/pipeline/entrypoints/Audit-MediaLibrary/scanner.ps1"), "audit")
        self.assertEqual(
            refresh_summaries.owner_domain_for("ops/pipeline/config/setup.ps1"),
            "scripts",
        )
        self.assertEqual(
            refresh_summaries.owner_domain_for(
                "ops/pipeline/config/setup/Validation.ps1"
            ),
            "scripts",
        )
        self.assertEqual(
            refresh_summaries.pipeline_stage_for("ops/pipeline/entrypoints/Audit-MediaLibrary.ps1"),
            "observability",
        )
        self.assertEqual(
            refresh_summaries.pipeline_stage_for("ops/pipeline/config/setup.ps1"),
            "setup",
        )

    def test_owner_domain_covers_current_core_domains(self) -> None:
        cases = {
            "src/mediapipeline/core/kernel/config_key_groups.py": "kernel",
            "src/mediapipeline/core/maintenance/change_ledger.py": "maintenance",
            "src/mediapipeline/core/folder_policy/service.py": "folder_policy",
            "src/mediapipeline/core/paths/service.py": "paths",
            "src/mediapipeline/core/schedule/facade.py": "schedule",
            "src/mediapipeline/core/files/open_policy.py": "files",
            "src/mediapipeline/core/shared/protocols.py": "shared",
            "src/mediapipeline/core/sample_validation/facade.py": "sample_validation",
            "src/mediapipeline/core/validation/contracts.py": "validation",
            "src/mediapipeline/core/metrics/service.py": "metrics",
            "src/mediapipeline/desktop/application/sample_validation/evidence.py": "sample_validation",
            "src/mediapipeline/desktop/watch/scanner.py": "watch",
            "ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1": "process",
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(refresh_summaries.owner_domain_for(path), expected)

    def test_ass_to_srt_helper_is_indexed_as_subtitle_source(self) -> None:
        self.assertIn("src/mediapipeline/pipeline", refresh_summaries.SOURCE_ROOTS)
        self.assertIn("src/mediapipeline/pipeline/ass_to_srt_cli.py", refresh_summaries.ROOT_SOURCE_FILES)
        self.assertTrue(refresh_summaries.in_scope_roots(Path("src/mediapipeline/pipeline/ass_to_srt_cli.py")))
        self.assertTrue(refresh_summaries.in_scope_roots(Path("src/mediapipeline/pipeline/ass_to_srt/srt.py")))
        self.assertEqual(refresh_summaries.owner_domain_for("src/mediapipeline/pipeline/ass_to_srt_cli.py"), "subtitles")
        self.assertEqual(
            refresh_summaries.owner_domain_for("src/mediapipeline/pipeline/ass_to_srt/styles.py"),
            "subtitles",
        )
        self.assertEqual(refresh_summaries.pipeline_stage_for("src/mediapipeline/pipeline/ass_to_srt_cli.py"), "subtitles")
        self.assertEqual(
            refresh_summaries.pipeline_stage_for("src/mediapipeline/pipeline/ass_to_srt/ass_events.py"),
            "subtitles",
        )
        self.assertEqual(refresh_summaries.token_priority_for("src/mediapipeline/pipeline/ass_to_srt_cli.py"), "high")
        self.assertEqual(
            refresh_summaries.token_priority_for("src/mediapipeline/pipeline/ass_to_srt/text.py"),
            "high",
        )

    def test_file_summaries_doc_lists_active_source_roots(self) -> None:
        doc = (REPO_ROOT / "docs" / "generated" / "FILE_SUMMARIES.md").read_text(
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
                "docs/generated/PROJECT_INDEX.md"
            )
        )
        self.assertTrue(
            refresh_summaries.is_volatile_generated_summary_source(
                "docs/generated/DEPENDENCY_GRAPH.md"
            )
        )
        self.assertTrue(
            refresh_summaries.is_volatile_generated_summary_source(
                "docs/generated/FEATURE_FILE_MAP.md"
            )
        )
        self.assertFalse(
            refresh_summaries.is_volatile_generated_summary_source(
                "docs/generated/FILE_SUMMARIES.md"
            )
        )

    def test_docs_path_casing_is_canonicalized_for_summaries(self) -> None:
        self.assertEqual(
            refresh_summaries.canonical_repo_relative_posix("Docs/ARCHIVED_MD_INDEX.md"),
            "docs/ARCHIVED_MD_INDEX.md",
        )
        self.assertTrue(
            refresh_summaries.is_volatile_generated_summary_source(
                "Docs/generated/PROJECT_INDEX.md"
            )
        )
        summary_path = refresh_summaries.summary_path_for_source(
            Path("Docs/generated/FILE_SUMMARIES.md"),
            ".md",
        )
        self.assertEqual(
            summary_path.relative_to(refresh_summaries.SUMMARY_ROOT).as_posix(),
            "docs/generated/FILE_SUMMARIES.md.md",
        )

    def test_summary_hash_is_stable_across_text_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lf_source = root / "lf.py"
            crlf_source = root / "crlf.py"
            lf_source.write_bytes(b"print('one')\nprint('two')\n")
            crlf_source.write_bytes(b"print('one')\r\nprint('two')\r\n")

            self.assertEqual(
                refresh_summaries.sha256_of(lf_source),
                refresh_summaries.sha256_of(crlf_source),
            )

    def test_generated_context_writers_force_lf_output(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        generator_paths = (
            repo_root / "src/mediapipeline/tools/dev/refresh_summaries.py",
            repo_root / "src/mediapipeline/tools/dev/generate_project_index.py",
            repo_root / "src/mediapipeline/tools/dev/generate_feature_file_map.py",
            repo_root / "src/mediapipeline/tools/dev/generate_pipeline_map.py",
        )
        for generator_path in generator_paths:
            with self.subTest(generator=generator_path.name):
                source = generator_path.read_text(encoding="utf-8")
                self.assertIn('newline="\\n"', source)

    def test_project_index_path_order_is_case_stable(self) -> None:
        paths = [Path("zeta.md"), Path("Beta.md"), Path("alpha.md")]
        ordered = sorted(paths, key=generate_project_index.canonical_path_sort_key)

        self.assertEqual([path.name for path in ordered], ["alpha.md", "Beta.md", "zeta.md"])

    def test_existing_nonstandard_extension_summary_can_be_refreshed_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / ".github" / "workflows" / "ci.yml"
            summary = root / "docs" / "generated" / "summaries" / ".github" / "workflows" / "ci.yml.md"
            source.parent.mkdir(parents=True)
            source.write_text("name: ci\n", encoding="utf-8")
            summary.parent.mkdir(parents=True)
            summary.write_text(_summary_text(".github/workflows/ci.yml"), encoding="utf-8")

            old_root = refresh_summaries.REPO_ROOT
            old_summary = refresh_summaries.SUMMARY_ROOT
            old_roots = refresh_summaries.SOURCE_ROOTS
            old_root_files = refresh_summaries.ROOT_SOURCE_FILES
            try:
                refresh_summaries.REPO_ROOT = root
                refresh_summaries.SUMMARY_ROOT = root / "docs" / "generated" / "summaries"
                refresh_summaries.SOURCE_ROOTS = ["src/mediapipeline/core"]
                refresh_summaries.ROOT_SOURCE_FILES = set()
                args = type(
                    "Args",
                    (),
                    {"paths": [".github/workflows/ci.yml"], "changed": False, "staged": False},
                )()

                self.assertEqual(refresh_summaries.collect_sources(args), [source])
                self.assertEqual(refresh_summaries.cmd_generate([source]), 0)
                self.assertEqual(refresh_summaries.existing_summary_sha(summary), _sha(source))
            finally:
                refresh_summaries.REPO_ROOT = old_root
                refresh_summaries.SUMMARY_ROOT = old_summary
                refresh_summaries.SOURCE_ROOTS = old_roots
                refresh_summaries.ROOT_SOURCE_FILES = old_root_files

    def test_project_index_skips_self_referential_generated_nav_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "mediapipeline" / "core" / "kept.py"
            summary = root / "docs" / "generated" / "summaries" / "src" / "mediapipeline" / "core" / "kept.py.md"
            generated = root / "docs" / "generated" / "PROJECT_INDEX.md"
            generated_summary = root / "docs" / "generated" / "summaries" / "docs" / "generated" / "PROJECT_INDEX.md.md"
            source.parent.mkdir(parents=True)
            source.write_text("print('kept')\n", encoding="utf-8")
            summary.parent.mkdir(parents=True)
            summary.write_text(_summary_text("src/mediapipeline/core/kept.py", _sha(source)), encoding="utf-8")
            generated.parent.mkdir(parents=True, exist_ok=True)
            generated.write_text("# generated\n", encoding="utf-8")
            generated_summary.parent.mkdir(parents=True)
            generated_summary.write_text(
                _summary_text("docs/generated/PROJECT_INDEX.md", _sha(generated)),
                encoding="utf-8",
            )

            old_root = generate_project_index.REPO_ROOT
            old_summary = generate_project_index.SUMMARY_ROOT
            try:
                generate_project_index.REPO_ROOT = root
                generate_project_index.SUMMARY_ROOT = root / "docs" / "generated" / "summaries"

                summaries = generate_project_index.iter_summaries()
                self.assertEqual(
                    [path.relative_to(root).as_posix() for path in summaries],
                    ["docs/generated/summaries/src/mediapipeline/core/kept.py.md"],
                )
                rendered = generate_project_index.render_index(summaries)
                self.assertIn("src/mediapipeline/core/kept.py", rendered)
                self.assertNotIn("docs/generated/PROJECT_INDEX.md", rendered)
            finally:
                generate_project_index.REPO_ROOT = old_root
                generate_project_index.SUMMARY_ROOT = old_summary

    @unittest.skipIf(
        (REPO_ROOT / "release_manifest.json").is_file(),
        "Historical change-packet summary sources are intentionally omitted from release packages.",
    )
    def test_root_schema_json_files_are_explicit_summary_sources(self) -> None:
        self.assertIn("ops/pipeline/entrypoints", refresh_summaries.SOURCE_ROOTS)
        self.assertIn("ops/pipeline/entrypoints/Audit-MediaLibrary.ps1", refresh_summaries.ROOT_SOURCE_FILES)
        self.assertIn("ops/pipeline/config", refresh_summaries.SOURCE_ROOTS)
        self.assertIn("ops/pipeline/config/MediaPipeline_config_template.psd1", refresh_summaries.ROOT_SOURCE_FILES)
        change_packet_path = Path("ops/release/changes/unreleased/MP-CHANGE-2026-0604-040.json")
        self.assertTrue(refresh_summaries.is_source_file(REPO_ROOT / change_packet_path))
        self.assertFalse(refresh_summaries.in_scope_roots(change_packet_path))
        args = type("Args", (), {"paths": [change_packet_path.as_posix()], "changed": False, "staged": False})()
        self.assertEqual(refresh_summaries.collect_sources(args), [REPO_ROOT / change_packet_path])
        self.assertTrue(
            refresh_summaries.is_source_file(REPO_ROOT / "src" / "mediapipeline" / "contracts" / "schemas" / "stages.v1.schema.json")
        )
        self.assertTrue(
            refresh_summaries.is_source_file(
                REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev" / "webview-public-contract.mjs"
            )
        )
        self.assertTrue(
            refresh_summaries.is_source_file(
                REPO_ROOT / "ops" / "scripts" / "dev" / "start-local-api.bat"
            )
        )
        self.assertTrue(
            refresh_summaries.is_source_file(
                REPO_ROOT / "src" / "mediapipeline" / "contracts" / "schemas" / "risky_file_registry.v1.schema.json"
            )
        )
        self.assertFalse(
            refresh_summaries.is_source_file(
                REPO_ROOT / "tests" / "fixtures" / "source_media" / "avi_mpeg2_480p.json"
            )
        )
        backup_path = Path("ops/pipeline/config/backups/MediaPipeline_config_chatgpt.backup_20260604_120000_000000.psd1")
        self.assertFalse(refresh_summaries.in_scope_roots(backup_path))
        self.assertFalse(refresh_summaries.is_source_file(REPO_ROOT / backup_path))
        self.assertEqual(refresh_summaries.owner_domain_for("src/mediapipeline/contracts/schemas/config.v1.schema.json"), "config")
        self.assertEqual(refresh_summaries.owner_domain_for("src/mediapipeline/contracts/schemas/stages.v1.schema.json"), "contracts")
        self.assertEqual(
            refresh_summaries.owner_domain_for("src/mediapipeline/contracts/schemas/risky_file_registry.v1.schema.json"),
            "scripts",
        )

    def test_refresh_check_flags_orphan_summary_only_on_full_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "mediapipeline" / "core" / "kept.py"
            orphan = root / "docs" / "generated" / "summaries" / "src" / "mediapipeline" / "core" / "deleted.py.md"
            summary = root / "docs" / "generated" / "summaries" / "src" / "mediapipeline" / "core" / "kept.py.md"
            source.parent.mkdir(parents=True)
            source.write_text("print('kept')\n", encoding="utf-8")
            summary.parent.mkdir(parents=True)
            summary.write_text(_summary_text("src/mediapipeline/core/kept.py", _sha(source)), encoding="utf-8")
            orphan.write_text(_summary_text("src/mediapipeline/core/deleted.py"), encoding="utf-8")

            old_root = refresh_summaries.REPO_ROOT
            old_summary = refresh_summaries.SUMMARY_ROOT
            old_roots = refresh_summaries.SOURCE_ROOTS
            old_root_files = refresh_summaries.ROOT_SOURCE_FILES
            try:
                refresh_summaries.REPO_ROOT = root
                refresh_summaries.SUMMARY_ROOT = root / "docs" / "generated" / "summaries"
                refresh_summaries.SOURCE_ROOTS = ["src/mediapipeline/core"]
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
            source = root / "src" / "mediapipeline" / "core" / "kept.py"
            orphan = root / "docs" / "generated" / "summaries" / "src" / "mediapipeline" / "core" / "deleted.py.md"
            source.parent.mkdir(parents=True)
            source.write_text("print('kept')\n", encoding="utf-8")
            orphan.parent.mkdir(parents=True)
            orphan.write_text(_summary_text("src/mediapipeline/core/deleted.py"), encoding="utf-8")

            old_root = refresh_summaries.REPO_ROOT
            old_summary = refresh_summaries.SUMMARY_ROOT
            try:
                refresh_summaries.REPO_ROOT = root
                refresh_summaries.SUMMARY_ROOT = root / "docs" / "generated" / "summaries"

                self.assertEqual(refresh_summaries.prune_orphan_summaries([source]), 1)
                self.assertFalse(orphan.exists())
            finally:
                refresh_summaries.REPO_ROOT = old_root
                refresh_summaries.SUMMARY_ROOT = old_summary

    def test_project_index_refuses_orphan_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = root / "docs" / "generated" / "summaries" / "src" / "mediapipeline" / "core" / "deleted.py.md"
            summary.parent.mkdir(parents=True)
            summary.write_text(_summary_text("src/mediapipeline/core/deleted.py"), encoding="utf-8")

            old_root = generate_project_index.REPO_ROOT
            old_summary = generate_project_index.SUMMARY_ROOT
            try:
                generate_project_index.REPO_ROOT = root
                generate_project_index.SUMMARY_ROOT = root / "docs" / "generated" / "summaries"

                findings = generate_project_index.orphan_summary_findings([summary])
                self.assertEqual([finding.reason_code for finding in findings], ["SOURCE_FILE_MISSING"])
                self.assertIn(
                    "ops/scripts/dev/run-python-tool.py mediapipeline.tools.dev.refresh_summaries --all --prune-orphans",
                    generate_project_index.render_orphan_summary_findings(findings),
                )
            finally:
                generate_project_index.REPO_ROOT = old_root
                generate_project_index.SUMMARY_ROOT = old_summary

    def test_feature_file_map_detects_missing_and_legacy_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            kept = root / "src" / "mediapipeline" / "core" / "queue" / "service.py"
            kept.parent.mkdir(parents=True)
            kept.write_text("print('kept')\n", encoding="utf-8")

            text = "\n".join(
                [
                    "`src/mediapipeline/core/queue/service.py`",
                    "`src/mediapipeline/core/queue/missing.py`",
                    "`app/api/commands.py`",
                ]
            )

            findings = generate_feature_file_map.path_reference_findings(text, root)
            self.assertEqual(
                [(finding.path, finding.reason_code) for finding in findings],
                [
                    ("src/mediapipeline/core/queue/missing.py", "REFERENCED_PATH_MISSING"),
                    ("app/api/commands.py", "LEGACY_ROOT_REFERENCE"),
                ],
            )

    def test_feature_file_map_renders_current_project_index_paths(self) -> None:
        text = "\n".join(
            [
                "| File | Domain | Priority | Stage | Purpose |",
                "|---|---|---|---|---|",
                "| `src/mediapipeline/core/queue/service.py` | queue | high | queue | Queue service. |",
                "| `ops/pipeline/engine/queue/queue_plan.ps1` | queue | high | queue | Queue plan. |",
                "| `apps/desktop/webview/static/assets/app.js` | ui | medium | n/a | WebView app. |",
            ]
        )

        entries = generate_feature_file_map.parse_project_index(text)
        rendered = generate_feature_file_map.render_feature_map(entries)

        self.assertIn("Queue, source scanning, and launch planning", rendered)
        self.assertIn("src/mediapipeline/core/queue/service.py", rendered)
        self.assertIn("ops/pipeline/engine/queue/queue_plan.ps1", rendered)
        self.assertIn("apps/desktop/webview/static/assets/app.js", rendered)
        self.assertNotIn("`app/", rendered)


if __name__ == "__main__":
    unittest.main()
