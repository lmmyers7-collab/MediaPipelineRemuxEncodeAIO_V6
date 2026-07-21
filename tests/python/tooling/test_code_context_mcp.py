from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediapipeline.tools.dev.code_context_service import (
    MAX_READ_LINES,
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

    def test_ripgrep_receives_only_prevalidated_files(self) -> None:
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
        self.assertIn(str(self.source), arguments)

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
    async def test_stdio_server_exposes_four_compact_read_only_tools(self) -> None:
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
                self.assertEqual(names, ["repo_context", "code_lookup", "code_search", "code_read"])
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


class CodeContextMcpProcessTests(unittest.TestCase):
    def test_single_startup_workflow_and_bootstrap_token_ceiling(self) -> None:
        root = Path(__file__).resolve().parents[3]
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
