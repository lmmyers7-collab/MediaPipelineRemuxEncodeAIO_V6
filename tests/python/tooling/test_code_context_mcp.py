from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from mediapipeline.tools.dev.code_context_service import (
    MAX_READ_LINES,
    MAX_SOURCE_BYTES,
    BundleFileRequest,
    CodeContextService,
)
from mediapipeline.tools.dev.context_records import ContextRecord, records_to_jsonl
from mediapipeline.tools.dev.context_slice import budget_tolerance, estimate_tokens
from mediapipeline.tools.dev.refresh_summaries import sha256_of

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


def record_for(path: str, source_hash: str) -> ContextRecord:
    return ContextRecord(
        path=path,
        file_type="Python",
        purpose="Provide a demonstration queue helper.",
        owner_domain="queue",
        feature_group="queue-launch",
        pipeline_stage="queue",
        token_priority="high",
        source_hash=source_hash,
        evidence_category="production",
        layer="python-domain",
        authority="backend-authority",
        risk_tier="low",
        validation_rung="targeted queue tests",
        public_symbols=("demo_symbol",),
        outbound_dependencies=("src/mediapipeline/dependency.py",),
        associated_tests=("tests/python/test_demo.py",),
        feature_groups=("queue-launch",),
        relevance_terms=("demo", "queue", "symbol"),
    )


class CodeContextServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.source = self.root / "src" / "mediapipeline" / "demo.py"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("def demo_symbol():\n    return 'needle'\n", encoding="utf-8")
        dependency = self.root / "src" / "mediapipeline" / "dependency.py"
        dependency.write_text("VALUE = 1\n", encoding="utf-8")
        test_file = self.root / "tests" / "python" / "test_demo.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("# demo test\n", encoding="utf-8")
        index = self.root / "docs" / "generated" / "PROJECT_INDEX.jsonl"
        index.parent.mkdir(parents=True)
        index.write_text(records_to_jsonl([record_for("src/mediapipeline/demo.py", sha256_of(self.source))]), encoding="utf-8")
        self.service = CodeContextService(root=self.root, index_path=index)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_context_is_bounded_and_uses_existing_catalog(self) -> None:
        result = self.service.repo_context("queue demo symbol", budget=700)
        self.assertTrue(result["ok"])
        self.assertLessEqual(result["estimated_tokens"], 700 + budget_tolerance(700))
        self.assertEqual(result["health"]["record_count"], 1)

    def test_cached_context_recomputes_returned_record_staleness(self) -> None:
        first = self.service.repo_context("queue demo symbol", budget=700)
        self.assertEqual(first["health"]["stale_paths"], [])
        self.source.write_text("def demo_symbol():\n    return 'changed'\n", encoding="utf-8")
        second = self.service.repo_context("queue demo symbol", budget=700)
        self.assertEqual(second["health"]["stale_paths"], ["src/mediapipeline/demo.py"])

    def test_normalized_context_and_lookup_queries_share_revision_aware_caches(self) -> None:
        self.service.repo_context(" Queue   Demo Symbol ", budget=700)
        self.service.repo_context("queue demo symbol", budget=700)
        self.service.code_lookup("Demo Symbol")
        self.service.code_lookup("  demo   symbol ")
        metrics = self.service._metrics_snapshot()
        self.assertEqual(metrics["cache_hits"], {"context": 1, "lookup": 1})

    def test_valid_index_change_reloads_atomically_and_invalid_change_keeps_last_snapshot(self) -> None:
        first_revision = self.service.health()["index_revision"]
        updated = record_for("src/mediapipeline/demo.py", sha256_of(self.source))
        updated = replace(updated, purpose="Provide a changed queue demonstration helper.")
        self.service.index_path.write_text(records_to_jsonl([updated]), encoding="utf-8")
        reloaded = self.service.code_lookup("src/mediapipeline/demo.py")
        self.assertNotEqual(reloaded["health"]["index_revision"], first_revision)
        self.assertEqual(reloaded["item"]["purpose"], "Provide a changed queue demonstration helper.")
        valid_revision = reloaded["health"]["index_revision"]
        self.service.index_path.write_text("{broken\n", encoding="utf-8")
        degraded = self.service.code_lookup("demo symbol")
        self.assertTrue(degraded["ok"])
        self.assertEqual(degraded["health"]["index_revision"], valid_revision)
        self.assertEqual(degraded["health"]["reload_status"], "degraded")
        self.assertTrue(degraded["health"]["reload_error"])

    def test_concurrent_catalog_calls_observe_one_complete_revision(self) -> None:
        updated = replace(
            record_for("src/mediapipeline/demo.py", sha256_of(self.source)),
            purpose="Provide a concurrent queue demonstration helper.",
        )
        self.service.index_path.write_text(records_to_jsonl([updated]), encoding="utf-8")
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: self.service.code_lookup("src/mediapipeline/demo.py"), range(24)))
        self.assertTrue(all(result["ok"] for result in results))
        self.assertEqual({result["item"]["purpose"] for result in results}, {updated.purpose})
        self.assertEqual(len({result["health"]["index_revision"] for result in results}), 1)

    def test_exact_lookup_returns_relationships(self) -> None:
        result = self.service.code_lookup("src/mediapipeline/demo.py")
        self.assertTrue(result["exact"])
        self.assertEqual(result["item"]["dependencies"], ["src/mediapipeline/dependency.py"])
        self.assertEqual(result["item"]["tests"], ["tests/python/test_demo.py"])

    def test_ranked_lookup_is_deterministic(self) -> None:
        first = self.service.code_lookup("demo symbol")
        second = self.service.code_lookup("demo symbol")
        self.assertEqual(first, second)
        self.assertEqual(first["items"][0]["path"], "src/mediapipeline/demo.py")

    def test_live_search_includes_unindexed_working_file(self) -> None:
        untracked = self.root / "src" / "mediapipeline" / "new_work.py"
        untracked.write_text("CURRENT_WORK = 'untracked-token'\n", encoding="utf-8")
        with patch("mediapipeline.tools.dev.code_context_service.shutil.which", return_value=None):
            result = self.service.code_search("untracked-token")
        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "python")
        self.assertEqual(result["items"][0]["path"], "src/mediapipeline/new_work.py")

    def test_live_search_skips_generated_and_history_by_default_but_exact_prefix_opts_in(self) -> None:
        generated = self.root / "docs" / "generated" / "RAW_LEDGER.json"
        generated.write_text('{"value":"opt-in-token"}\n', encoding="utf-8")
        archived = self.root / "docs" / "archive" / "historical.md"
        archived.parent.mkdir(parents=True)
        archived.write_text("opt-in-token\n", encoding="utf-8")
        packet = self.root / "ops" / "release" / "changes" / "complete.json"
        packet.parent.mkdir(parents=True)
        packet.write_text('{"value":"opt-in-token"}\n', encoding="utf-8")

        with patch("mediapipeline.tools.dev.code_context_service.shutil.which", return_value=None):
            default = self.service.code_search("opt-in-token")
            generated_result = self.service.code_search(
                "opt-in-token", path_prefix="docs/generated"
            )
            archived_result = self.service.code_search(
                "opt-in-token", path_prefix="docs/archive"
            )
            packet_result = self.service.code_search(
                "opt-in-token", path_prefix="ops/release/changes"
            )

        self.assertEqual(default["items"], [])
        self.assertEqual(generated_result["items"][0]["path"], "docs/generated/RAW_LEDGER.json")
        self.assertEqual(archived_result["items"][0]["path"], "docs/archive/historical.md")
        self.assertEqual(packet_result["items"][0]["path"], "ops/release/changes/complete.json")

    def test_exact_historical_symbol_remains_findable_and_reports_staleness(self) -> None:
        packet = self.root / "ops" / "release" / "changes" / "complete.json"
        packet.parent.mkdir(parents=True)
        packet.write_text('{"status":"complete"}\n', encoding="utf-8")
        historical = replace(
            record_for("ops/release/changes/complete.json", "0" * 64),
            evidence_category="change_evidence",
            layer="secondary-evidence",
            authority="secondary-evidence",
            public_symbols=("historical_exact_symbol",),
            relevance_terms=("historical", "exact", "symbol"),
        )
        active = record_for("src/mediapipeline/demo.py", sha256_of(self.source))
        self.service.index_path.write_text(
            records_to_jsonl([active, historical]),
            encoding="utf-8",
        )

        result = self.service.code_lookup("historical_exact_symbol")

        self.assertEqual(result["items"][0]["path"], historical.path)
        self.assertIn(historical.path, result["health"]["stale_paths"])

    def test_ripgrep_receives_validated_roots_and_deny_globs(self) -> None:
        secret = self.root / "src" / "mediapipeline" / ".env"
        secret.write_text("needle=secret\n", encoding="utf-8")
        completed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        with (
            patch("mediapipeline.tools.dev.code_context_service.shutil.which", return_value="rg"),
            patch("mediapipeline.tools.dev.code_context_service.subprocess.run", return_value=completed) as run,
        ):
            result = self.service.code_search("needle")
        self.assertTrue(result["ok"])
        arguments = [str(argument) for call in run.call_args_list for argument in call.args[0]]
        self.assertNotIn(str(secret), arguments)
        self.assertIn(str(self.source.parent), arguments)
        self.assertIn("!**/.env", arguments)
        self.assertIn("!docs/generated/**", arguments)

    def test_invalid_regex_is_structured(self) -> None:
        result = self.service.code_search("[", regex=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "invalid_regex")

    def test_python_search_fallback_has_a_deadline(self) -> None:
        with (
            patch("mediapipeline.tools.dev.code_context_service.shutil.which", return_value=None),
            patch("mediapipeline.tools.dev.code_context_service.time.monotonic", side_effect=[0.0, 4.0]),
        ):
            result = self.service.code_search("needle")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "search_timeout")

    def test_read_is_line_bounded_and_reports_staleness(self) -> None:
        self.source.write_text("\n".join(f"line {number}" for number in range(MAX_READ_LINES + 20)) + "\n", encoding="utf-8")
        result = self.service.code_read("src/mediapipeline/demo.py", end_line=MAX_READ_LINES + 20)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["lines"]), MAX_READ_LINES)
        self.assertTrue(result["truncated"])
        self.assertTrue(result["index_stale"])

    def test_code_bundle_is_fair_compact_bounded_and_continuable(self) -> None:
        self.source.write_text("\n".join(f"demo line {number}" for number in range(600)) + "\n", encoding="utf-8")
        dependency = self.root / "src" / "mediapipeline" / "dependency.py"
        dependency.write_text("\n".join(f"dependency line {number}" for number in range(600)) + "\n", encoding="utf-8")
        result = self.service.code_bundle(
            [
                BundleFileRequest("src/mediapipeline/demo.py"),
                BundleFileRequest("src/mediapipeline/dependency.py", start_line=11, end_line=500),
            ],
            budget=800,
        )
        self.assertTrue(result["ok"])
        self.assertLessEqual(result["estimated_tokens"], 800 + budget_tolerance(800))
        self.assertEqual(len(result["items"]), 2)
        self.assertTrue(all(item["text"] for item in result["items"]))
        self.assertTrue(all(item["truncated"] for item in result["items"]))
        self.assertEqual(result["items"][1]["start_line"], 11)
        self.assertEqual(result["items"][1]["next_start_line"], result["items"][1]["end_line"] + 1)

    def test_code_bundle_preflight_is_atomic_for_duplicates_ranges_and_binary_files(self) -> None:
        duplicate = self.service.code_bundle(
            [BundleFileRequest("src/mediapipeline/demo.py"), BundleFileRequest("src/mediapipeline/demo.py")]
        )
        self.assertEqual(duplicate["error"]["code"], "duplicate_path")
        invalid_range = self.service.code_bundle(
            [BundleFileRequest("src/mediapipeline/demo.py", start_line=3, end_line=2)]
        )
        self.assertEqual(invalid_range["error"]["code"], "invalid_range")
        binary = self.root / "src" / "mediapipeline" / "binary.py"
        binary.write_bytes(b"abc\x00def")
        rejected = self.service.code_bundle(
            [BundleFileRequest("src/mediapipeline/demo.py"), BundleFileRequest("src/mediapipeline/binary.py")]
        )
        self.assertFalse(rejected["ok"])
        self.assertNotIn("items", rejected)
        self.assertEqual(rejected["error"]["code"], "binary_file")

    def test_code_bundle_budget_edges_preserve_unicode_and_report_staleness(self) -> None:
        self.source.write_text("café 雪\nsecond line\n", encoding="utf-8")
        for budget in (800, 8000):
            result = self.service.code_bundle([BundleFileRequest("src/mediapipeline/demo.py")], budget=budget)
            self.assertTrue(result["ok"])
            self.assertIn("café 雪", result["items"][0]["text"])
            self.assertTrue(result["items"][0]["index_stale"])
            self.assertLessEqual(result["estimated_tokens"], budget + budget_tolerance(budget))
        for budget in (799, 8001):
            result = self.service.code_bundle([BundleFileRequest("src/mediapipeline/demo.py")], budget=budget)
            self.assertEqual(result["error"]["code"], "invalid_budget")

    def test_code_bundle_rejects_denied_oversized_and_too_many_files_atomically(self) -> None:
        oversized = self.root / "src" / "mediapipeline" / "oversized.py"
        oversized.write_bytes(b"x" * (MAX_SOURCE_BYTES + 1))
        for request, expected in (
            (
                [BundleFileRequest("src/mediapipeline/demo.py"), BundleFileRequest("src/mediapipeline/oversized.py")],
                "file_too_large",
            ),
            (
                [BundleFileRequest("src/mediapipeline/demo.py"), BundleFileRequest("../outside.py")],
                "path_denied",
            ),
        ):
            result = self.service.code_bundle(request)
            self.assertFalse(result["ok"])
            self.assertNotIn("items", result)
            self.assertEqual(result["error"]["code"], expected)
        too_many = [BundleFileRequest(f"src/mediapipeline/file_{number}.py") for number in range(9)]
        result = self.service.code_bundle(too_many)
        self.assertEqual(result["error"]["code"], "invalid_files")

    def test_metrics_output_contains_counters_but_no_queries_paths_or_source(self) -> None:
        self.service.code_search("needle")
        self.service.code_read("src/mediapipeline/demo.py")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.service.emit_metrics()
        emitted = stderr.getvalue()
        self.assertIn("mediapipeline_code_mcp_metrics.v1", emitted)
        self.assertNotIn("needle", emitted)
        self.assertNotIn("demo.py", emitted)
        self.assertNotIn("return 'needle'", emitted)

    def test_binary_and_secret_paths_are_denied(self) -> None:
        binary = self.root / "src" / "mediapipeline" / "binary.py"
        binary.write_bytes(b"abc\x00def")
        self.assertEqual(self.service.code_read("src/mediapipeline/binary.py")["error"]["code"], "binary_file")
        secret = self.root / "src" / "mediapipeline" / ".env"
        secret.write_text("TOKEN=secret\n", encoding="utf-8")
        self.assertEqual(self.service.code_read("src/mediapipeline/.env")["error"]["code"], "path_denied")

    def test_absolute_traversal_runtime_and_change_packets_are_denied(self) -> None:
        for path in (
            str(self.source.resolve()),
            "../outside.py",
            "LocalBase/private.py",
            "ops/release/changes/unreleased/packet.json",
        ):
            result = self.service.code_read(path)
            self.assertFalse(result["ok"], path)
            self.assertIn(result["error"]["code"], {"absolute_path", "path_denied"})

    def test_symlink_escape_is_denied_when_supported(self) -> None:
        outside = self.root.parent / f"{self.root.name}-outside.py"
        outside.write_text("SECRET = True\n", encoding="utf-8")
        link = self.root / "src" / "mediapipeline" / "linked.py"
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is unavailable")
        try:
            result = self.service.code_read("src/mediapipeline/linked.py")
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["code"], "path_escape")
        finally:
            link.unlink(missing_ok=True)
            outside.unlink(missing_ok=True)

    def test_missing_index_keeps_live_read_available(self) -> None:
        service = CodeContextService(root=self.root, index_path=self.root / "missing.jsonl")
        self.assertEqual(service.repo_context("demo")["error"]["code"], "index_unavailable")
        self.assertTrue(service.code_read("src/mediapipeline/demo.py")["ok"])


@unittest.skipUnless(MCP_AVAILABLE, "official MCP SDK is not installed in this interpreter")
class CodeContextMcpProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_server_exposes_five_compact_read_only_tools(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        runner = repo_root / "ops" / "scripts" / "dev" / "run-python-tool.py"
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(runner), "mediapipeline.tools.dev.code_context_mcp"],
            cwd=str(repo_root),
        )
        async with stdio_client(params) as streams:
            read_stream, write_stream = streams[0], streams[1]
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                listed = await session.list_tools()
                names = [tool.name for tool in listed.tools]
                self.assertEqual(names, ["repo_context", "code_lookup", "code_search", "code_read", "code_bundle"])
                schema_text = json.dumps([tool.model_dump(mode="json") for tool in listed.tools], sort_keys=True)
                self.assertLessEqual(estimate_tokens(schema_text), 1200)
                for tool in listed.tools:
                    self.assertTrue(tool.annotations.readOnlyHint)
                    self.assertFalse(tool.annotations.destructiveHint)
                result = await session.call_tool(
                    "code_read",
                    arguments={"path": "src/mediapipeline/tools/dev/code_context_mcp.py", "start_line": 1, "end_line": 8},
                )
                self.assertFalse(result.isError)
                self.assertTrue(result.structuredContent["ok"])
                bundled = await session.call_tool(
                    "code_bundle",
                    arguments={
                        "files": [
                            {
                                "path": "src/mediapipeline/tools/dev/code_context_mcp.py",
                                "start_line": 1,
                                "end_line": 8,
                            }
                        ],
                        "budget": 800,
                    },
                )
                self.assertFalse(bundled.isError)
                self.assertTrue(bundled.structuredContent["ok"])


class CodeContextMcpProcessTests(unittest.TestCase):
    def test_single_startup_workflow_and_bootstrap_token_ceiling(self) -> None:
        root = Path(__file__).resolve().parents[3]
        if not (root / ".claude" / "CLAUDE.md").is_file():
            self.skipTest("source assistant guidance is unavailable in the release package")
        agents = (root / "AGENTS.md").read_text(encoding="utf-8")
        claude = (root / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
        guide = (root / "docs" / "generated" / "FILE_SUMMARIES.md").read_text(encoding="utf-8")
        self.assertIn("mediapipeline-code", agents)
        self.assertIn("context_slice --task", agents)
        self.assertNotIn("Start a session with:", agents)
        self.assertNotIn("Read **PROJECT_INDEX.md**", claude)
        self.assertIn("authoritative operating contract", claude)
        self.assertIn("## Local code-context MCP", guide)
        bootstrap_tokens = estimate_tokens(agents) + estimate_tokens(claude) + 1200 + 2000
        self.assertLessEqual(bootstrap_tokens, 8000)
        self.assertLessEqual(bootstrap_tokens, int(9967 * 0.85))

    def test_bootstrap_preview_is_non_mutating_and_resolves_clients(self) -> None:
        root = Path(__file__).resolve().parents[3]
        pwsh = root / "ops" / "pipeline" / "runtime" / "PowerShell-7.6.0-win-x64" / "pwsh.exe"
        if not pwsh.is_file():
            self.skipTest("bundled PowerShell is unavailable")
        script = root / "ops" / "scripts" / "dev" / "setup-code-context-mcp.ps1"
        completed = subprocess.run(
            [str(pwsh), "-NoProfile", "-File", str(script)],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["action"], "preview")
        self.assertEqual(payload["server_name"], "mediapipeline-code")
        self.assertTrue(payload["codex_cli"])
        self.assertTrue(payload["claude_cli"])

    def test_dependency_is_isolated_from_production_project_dependencies(self) -> None:
        root = Path(__file__).resolve().parents[3]
        mcp_requirements = (root / "requirements" / "mcp.txt").read_text(encoding="utf-8")
        dev_requirements = (root / "requirements" / "dev.txt").read_text(encoding="utf-8")
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("mcp>=1.27,<2", mcp_requirements)
        self.assertIn("-r mcp.txt", dev_requirements)
        self.assertNotIn('"mcp', pyproject)


if __name__ == "__main__":
    unittest.main()
