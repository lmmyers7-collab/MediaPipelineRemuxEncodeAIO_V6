from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mediapipeline.tools.dev.repository_audit_ledger import (
    LINE_REVIEW_CATEGORIES,
    SCHEMA_VERSION,
    atomic_write_text_set,
    audit_owned_untracked_paths,
    baseline_markdown,
    build_rows,
    canonical_path,
    check_outputs,
    classification_for,
    current_content_findings,
    evidence_ledger_findings,
    error_record_findings,
    fallback_risk_tier,
    finding_record_findings,
    finding_root_cause_fingerprint,
    git_blob_map,
    independent_review_completion_findings,
    jsonl_text,
    load_review_fragments,
    merge_error_ledgers,
    merge_finding_ledgers,
    merge_review_ledgers,
    prepare_error_records,
    prepare_finding_records,
    review_fragment_findings,
    resolved_repository_path,
    resolved_regular_worktree_path,
    second_review_attestation_findings,
    sha256_file,
    strict_repository_relative_path,
    validation_findings,
    verification_obligations_for,
    write_outputs,
    worker_for,
)


def coverage_row(
    *,
    path: str = "src/a.py",
    category: str = "first-party executable source",
    status: str = "line_reviewed_no_findings",
    risk_tier: str = "low",
) -> dict[str, object]:
    flags = {
        "generated": category == "generated artifact",
        "vendor": category == "vendored/third-party source",
        "archive": category == "historical archived evidence",
        "binary": category == "binary/media/font/image/archive",
        "runtime": category == "bundled runtime/tool",
        "evidence_snapshot": False,
    }
    obligations = verification_obligations_for(category, flags)
    return {
        "schema_version": SCHEMA_VERSION,
        "path": path,
        "is_tracked": True,
        "git_mode": "100644",
        "git_blob_hash": "blob",
        "content_sha256": "sha",
        "content_source": "worktree",
        "file_size_bytes": 1,
        "file_category": category,
        "owner_domain": "test",
        "architectural_layer": "tests",
        "language_or_type": "Python",
        **flags,
        "total_lines": 1,
        "source_lines": 1,
        "line_count_method": "physical and nonblank text lines",
        "assigned_worker": "worker",
        "review_status": status,
        "review_depth": "line_by_line",
        "reviewed_symbols_or_sections": ["all"],
        "responsibility_summary": "Exercises one audit-ledger behavior.",
        "incoming_dependencies": [],
        "outgoing_dependencies": [],
        "api_routes": [],
        "commands": [],
        "invoked_tools": [],
        "state_files": [],
        "config_keys": [],
        "process_boundaries": [],
        "artifacts": [],
        "relevant_tests": [],
        "finding_ids": [],
        "error_ids": [],
        "prior_audit_coverage": "no applicable prior finding",
        "evidence_commands": ["line-numbered source read"],
        "reviewer": "reviewer",
        "reviewer_notes": "Current content and obligations were reviewed.",
        "second_review_status": "complete" if risk_tier == "high" else "not_required",
        "risk_tier": risk_tier,
        "project_index_present": True,
        "project_index_hash_matches": True,
        "project_index_reconciliation": "hash_matched",
        "verification_obligations": obligations,
        "verified_obligations": obligations,
    }


def finding_record(*, finding_id: str = "AUDIT-FIND-TEST-001") -> dict[str, object]:
    return {
        "id": finding_id,
        "severity": "P2",
        "confidence": "high",
        "category": "tooling",
        "title": "Example",
        "locations": [{"path": "src/a.py", "start_line": 1, "end_line": 1, "symbol": "a"}],
        "observed_behavior": "observed",
        "expected_invariant": "expected",
        "root_cause": "cause",
        "failure_scenario": "scenario",
        "evidence": ["evidence"],
        "affected_flows": ["audit"],
        "existing_safeguards": "none",
        "safeguard_gap": "gap",
        "tests_present": [],
        "tests_missing": ["test"],
        "recommended_remediation": "fix",
        "remediation_risk": "low",
        "validation_rung": "tooling",
        "related_finding_ids": [],
        "prior_audit_relationship": "new",
        "disposition": "confirmed",
    }


def second_review_attestation(
    row: dict[str, object],
    *,
    first_reviewer: str = "/root/first_reviewer",
    reviewer: str = "/root/second_reviewer",
    finding_ids: list[str] | None = None,
) -> dict[str, object]:
    finding_ids = finding_ids or []
    return {
        "path": row["path"],
        "content_sha256": row["content_sha256"],
        "assigned_worker": row["assigned_worker"],
        "review_status": row["review_status"],
        "review_depth": "independent_line_by_line",
        "reviewed_symbols_or_sections": ["all"],
        "first_reviewer": first_reviewer,
        "reviewer": reviewer,
        "independence_basis": "Distinct canonical agent identity and fresh source read.",
        "finding_ids": finding_ids,
        "finding_dispositions": {finding_id: "confirmed" for finding_id in finding_ids},
        "error_ids": [],
        "evidence_commands": ["independent line-numbered source read"],
        "reviewer_notes": "Current hash and stated findings were independently reviewed.",
        "second_review_status": "complete",
    }


class RepositoryAuditLedgerTests(unittest.TestCase):
    def test_canonical_path_normalizes_windows_separators(self) -> None:
        self.assertEqual(canonical_path(r".\src\mediapipeline\core\queue\service.py"), "src/mediapipeline/core/queue/service.py")

    def test_git_blob_map_rejects_ambiguous_index_stages(self) -> None:
        with mock.patch(
            "mediapipeline.tools.dev.repository_audit_ledger.run_git",
            return_value=b"100644 deadbeef 1\tsrc/a.py\0",
        ):
            with self.assertRaisesRegex(ValueError, "unresolved Git index stages: src/a.py"):
                git_blob_map(root=Path("unused"))
        with mock.patch(
            "mediapipeline.tools.dev.repository_audit_ledger.run_git",
            return_value=b"100644 deadbeef 0\tsrc/a.py\x00100644 feedface 0\tsrc/a.py\x00",
        ):
            with self.assertRaisesRegex(ValueError, "duplicate stage-0 Git index entry: src/a.py"):
                git_blob_map(root=Path("unused"))
        with mock.patch(
            "mediapipeline.tools.dev.repository_audit_ledger.run_git",
            return_value=b"100644 deadbeef 0\tsrc/A.py\x00100644 feedface 0\tsrc/a.py\x00",
        ):
            with self.assertRaisesRegex(ValueError, "ambiguous Windows Git path identity: src/A.py, src/a.py"):
                git_blob_map(root=Path("unused"))

    def test_classification_precedence_preserves_archive_runtime_and_generated_boundaries(self) -> None:
        archive, archive_flags = classification_for("docs/archive/old.md", text=True, binary=False)
        runtime, runtime_flags = classification_for("apps/desktop/runtime/Python/python.exe", text=False, binary=True)
        generated, generated_flags = classification_for("docs/generated/PROJECT_INDEX.md", text=True, binary=False)
        self.assertEqual(archive, "historical archived evidence")
        self.assertTrue(archive_flags["archive"])
        self.assertEqual(runtime, "bundled runtime/tool")
        self.assertTrue(runtime_flags["runtime"])
        self.assertTrue(runtime_flags["binary"])
        self.assertEqual(generated, "generated artifact")
        self.assertTrue(generated_flags["generated"])

    def test_first_party_code_tests_and_workflows_are_reviewable(self) -> None:
        source, _ = classification_for("src/mediapipeline/core/queue/service.py", text=True, binary=False)
        test, _ = classification_for("tests/python/core/test_queue.py", text=True, binary=False)
        workflow, _ = classification_for(".github/workflows/deep-audit.yml", text=True, binary=False)
        self.assertEqual(source, "first-party executable source")
        self.assertEqual(test, "first-party test or fixture")
        self.assertEqual(workflow, "behavior-defining configuration/schema/workflow")
        self.assertTrue({source, test, workflow}.issubset(LINE_REVIEW_CATEGORIES))

    def test_requirements_and_ignore_files_are_behavior_configuration(self) -> None:
        requirements, _ = classification_for("requirements/dev.txt", text=True, binary=False)
        gitignore, _ = classification_for(".gitignore", text=True, binary=False)
        artifact, flags = classification_for("artifacts/report.json", text=True, binary=False)
        self.assertEqual(requirements, "behavior-defining configuration/schema/workflow")
        self.assertEqual(gitignore, "behavior-defining configuration/schema/workflow")
        self.assertEqual(artifact, "generated artifact")
        self.assertTrue(flags["generated"])

    def test_unindexed_high_risk_paths_are_still_high_risk(self) -> None:
        self.assertEqual(fallback_risk_tier("ops/pipeline/engine/publish/drain.ps1", "first-party executable source"), "high")
        self.assertEqual(fallback_risk_tier("ops/pipeline/engine/storage/move.ps1", "first-party executable source"), "high")
        self.assertEqual(
            fallback_risk_tier(
                "src/mediapipeline/contracts/schemas/run_monitor.v1.schema.json",
                "generated artifact",
            ),
            "high",
        )
        self.assertEqual(fallback_risk_tier("docs/archive/old.md", "historical archived evidence"), "low")

    def test_malformed_risky_file_registry_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "registry.json"
            registry.write_text(json.dumps({"schema_version": "wrong", "entries": []}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid risky-file registry"):
                fallback_risk_tier(
                    "ops/pipeline/engine/storage/move.ps1",
                    "first-party executable source",
                    registry_path=registry,
                )

    def test_worker_assignment_separates_high_level_domains(self) -> None:
        self.assertEqual(worker_for("src/mediapipeline/core/publish/pending_service.py", "first-party executable source"), "worker-04-publish-completed-rename")
        self.assertEqual(worker_for("apps/desktop/tauri/src-tauri/src/lib.rs", "first-party executable source"), "worker-09-tauri-shell")
        self.assertEqual(worker_for("ops/pipeline/runtime/ffmpeg.exe", "bundled runtime/tool"), "worker-13-runtime-vendor-binary")

    def test_validation_rejects_missing_duplicate_and_false_terminal_claims(self) -> None:
        incompatible = coverage_row(status="generated_verified", risk_tier="high")
        incompatible["second_review_status"] = "pending"
        pending = coverage_row(status="pending")
        rows = [incompatible, pending]
        findings = validation_findings(rows, expected_paths={"src/a.py", "src/b.py"}, require_complete=True)
        joined = "\n".join(findings)
        self.assertIn("incompatible terminal status", joined)
        self.assertIn("independent second review", joined)
        self.assertIn("duplicate coverage path", joined)
        self.assertIn("missing coverage path: src/b.py", joined)
        self.assertIn("review is not achieved (pending)", joined)

    def test_blocked_rows_never_satisfy_achieved_completion(self) -> None:
        row = coverage_row(status="blocked_with_reason")
        findings = validation_findings([row], expected_paths={"src/a.py"}, require_complete=True)
        self.assertIn("review is blocked and does not satisfy achieved completion", "\n".join(findings))

    def test_every_category_has_one_compatible_achieved_status(self) -> None:
        cases = {
            "first-party executable source": "line_reviewed_no_findings",
            "first-party test or fixture": "line_reviewed_no_findings",
            "behavior-defining configuration/schema/workflow": "line_reviewed_no_findings",
            "active documentation": "line_reviewed_no_findings",
            "generated artifact": "generated_verified",
            "vendored/third-party source": "vendor_verified",
            "bundled runtime/tool": "vendor_verified",
            "binary/media/font/image/archive": "binary_inventoried",
            "historical archived evidence": "archive_inventoried",
            "metadata/packaging": "metadata_verified",
        }
        for index, (category, status) in enumerate(cases.items()):
            with self.subTest(category=category):
                path = f"case/{index}"
                row = coverage_row(path=path, category=category, status=status)
                self.assertEqual(validation_findings([row], expected_paths={path}, require_complete=True), [])
                wrong = {**row, "review_status": "generated_verified" if status != "generated_verified" else "vendor_verified"}
                self.assertIn("incompatible terminal status", "\n".join(validation_findings([wrong], expected_paths={path})))

    def test_achieved_review_rejects_inventory_defaults_and_unverified_obligations(self) -> None:
        row = coverage_row()
        row.update(
            {
                "reviewed_symbols_or_sections": [],
                "responsibility_summary": "Inventory classification pending semantic review.",
                "evidence_commands": ["git ls-files -z", "docs/generated/PROJECT_INDEX.jsonl"],
                "prior_audit_coverage": "not_reconciled",
                "reviewer_notes": "",
                "verified_obligations": [],
                "project_index_present": False,
                "project_index_hash_matches": False,
                "project_index_reconciliation": "not_reconciled",
            }
        )
        joined = "\n".join(validation_findings([row], expected_paths={"src/a.py"}, require_complete=True))
        self.assertIn("no reviewed symbols/sections", joined)
        self.assertIn("placeholder responsibility", joined)
        self.assertIn("only inventory/default evidence", joined)
        self.assertIn("prior-audit coverage is not reconciled", joined)
        self.assertIn("verified obligations do not exactly satisfy", joined)
        self.assertIn("unindexed path lacks an explicit reconciliation rationale", joined)

    def test_baseline_does_not_claim_semantic_review(self) -> None:
        row = {
            "file_category": "first-party executable source",
            "language_or_type": "Python",
            "assigned_worker": "worker-01",
            "is_tracked": True,
            "total_lines": 10,
            "source_lines": 8,
            "project_index_present": True,
        }
        rendered = baseline_markdown([row], head="abc", branch="audit")
        self.assertIn("achieved=0; blocked=0; open=1", rendered)
        self.assertIn("Inventory metadata does not constitute semantic review", rendered)
        mixed = baseline_markdown(
            [
                {**row, "review_status": "line_reviewed_no_findings"},
                {**row, "review_status": "blocked_with_reason"},
                {**row, "review_status": "pending"},
            ],
            head="abc",
            branch="audit",
        )
        self.assertIn("achieved=1; blocked=1; open=1", mixed)

    def test_owned_untracked_paths_do_not_absorb_unrelated_change_packets(self) -> None:
        owned = audit_owned_untracked_paths()
        self.assertIn("ops/release/changes/unreleased/MP-CHANGE-2026-0720-011.json", owned)
        self.assertNotIn("ops/release/changes/unreleased/MP-CHANGE-2026-0720-012.json", owned)

    def test_error_records_require_unique_ids_and_complete_shape(self) -> None:
        valid = {
            "id": "AUDIT-ERR-TEST-001",
            "timestamp": "2026-07-20",
            "command": "test",
            "working_directory": "repo",
            "exit_code": 1,
            "output_summary": "expected failure",
            "phase": "test",
            "classification": "expected negative-path result",
            "reproduction_status": "reproduced",
            "retry_result": "passed",
            "linked_finding_ids": [],
            "coverage_blocked": False,
            "disposition": "closed",
        }
        self.assertEqual(error_record_findings([valid]), [])
        findings = error_record_findings([valid, {**valid, "linked_finding_ids": "none"}])
        self.assertIn("duplicate error id", "\n".join(findings))
        self.assertIn("linked_finding_ids must be an array", "\n".join(findings))
        malformed = {
            **valid,
            "id": "AUDIT-ERR-TEST-002",
            "command": "",
            "classification": "invented class",
            "exit_code": "1",
            "linked_finding_ids": ["MISSING"],
        }
        joined = "\n".join(error_record_findings([malformed], valid_finding_ids={"KNOWN"}))
        self.assertIn("command must be a nonempty string", joined)
        self.assertIn("invalid classification", joined)
        self.assertIn("exit_code must be an integer or null", joined)
        self.assertIn("linked finding does not exist", joined)

    def test_strict_evidence_gate_rejects_blocking_and_stale_error_ledgers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "a.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n", encoding="utf-8")
            output_dir = root / "audit"
            workers = output_dir / "workers"
            workers.mkdir(parents=True)
            finding = finding_record()
            (workers / "worker-99-findings.jsonl").write_text(jsonl_text([finding]), encoding="utf-8")
            error = {
                "id": "AUDIT-ERR-TEST-001",
                "timestamp": "2026-07-20T12:00:00+00:00",
                "command": "test",
                "working_directory": "repo",
                "exit_code": 1,
                "output_summary": "failed",
                "phase": "test",
                "classification": "test failure",
                "reproduction_status": "reproduced",
                "retry_result": "still failing",
                "linked_finding_ids": ["AUDIT-FIND-TEST-001"],
                "coverage_blocked": True,
                "disposition": "open pending correction",
            }
            error_fragment = workers / "worker-99-errors.jsonl"
            error_fragment.write_text(jsonl_text([error]), encoding="utf-8")
            merge_finding_ledgers(output_dir, root=root)
            merge_error_ledgers(output_dir, root=root)
            joined = "\n".join(evidence_ledger_findings(output_dir, root=root, require_complete=True))
            self.assertIn("coverage-blocking error records remain unresolved", joined)
            error_fragment.write_text(jsonl_text([{**error, "retry_result": "changed after merge"}]), encoding="utf-8")
            joined = "\n".join(evidence_ledger_findings(output_dir, root=root))
            self.assertIn("central error ledger is missing, stale", joined)

    def test_review_fragments_enforce_hash_and_worker_ownership(self) -> None:
        baseline = {
            "src/a.py": {
                "path": "src/a.py",
                "content_sha256": "current",
                "assigned_worker": "worker-01",
            }
        }
        fragment = {
            "path": "src/a.py",
            "content_sha256": "stale",
            "assigned_worker": "worker-02",
            "review_status": "line_reviewed_no_findings",
            "review_depth": "line_by_line",
            "reviewed_symbols_or_sections": ["all"],
            "reviewer": "agent",
            "finding_ids": [],
            "error_ids": [],
            "prior_audit_coverage": "none",
            "evidence_commands": ["read"],
            "reviewer_notes": "reviewed",
            "second_review_status": "not_required",
            "project_index_reconciliation": "hash_matched",
            "verified_obligations": ["semantic_line_review"],
        }
        findings = "\n".join(review_fragment_findings([fragment], baseline_rows=baseline))
        self.assertIn("does not own baseline slice", findings)
        self.assertIn("hash does not match", findings)

    def test_review_fragments_join_finding_and_error_ids(self) -> None:
        baseline = {
            "src/a.py": {
                "path": "src/a.py",
                "content_sha256": "current",
                "assigned_worker": "worker-01",
            }
        }
        fragment = {
            "path": "src/a.py",
            "content_sha256": "current",
            "assigned_worker": "worker-01",
            "review_status": "line_reviewed_with_findings",
            "review_depth": "line_by_line",
            "reviewed_symbols_or_sections": ["all"],
            "reviewer": "/root/reviewer",
            "finding_ids": ["AUDIT-FIND-MISSING"],
            "error_ids": ["AUDIT-ERR-MISSING"],
            "prior_audit_coverage": "none",
            "evidence_commands": ["read"],
            "reviewer_notes": "reviewed",
            "second_review_status": "not_required",
            "project_index_reconciliation": "hash_matched",
            "verified_obligations": ["semantic_line_review"],
        }
        findings = "\n".join(
            review_fragment_findings(
                [fragment],
                baseline_rows=baseline,
                valid_finding_ids={"AUDIT-FIND-CURRENT"},
                valid_error_ids={"AUDIT-ERR-CURRENT"},
            )
        )
        self.assertIn("review fragment finding does not exist: AUDIT-FIND-MISSING", findings)
        self.assertIn("review fragment error does not exist: AUDIT-ERR-MISSING", findings)
        no_findings = {**fragment, "review_status": "line_reviewed_no_findings"}
        self.assertIn(
            "no-findings review status has finding IDs",
            "\n".join(review_fragment_findings([no_findings], baseline_rows=baseline)),
        )

    def test_review_fragments_require_exact_path_local_finding_set(self) -> None:
        baseline = {
            "src/a.py": {
                "path": "src/a.py",
                "content_sha256": "current",
                "assigned_worker": "worker-01",
            }
        }
        fragment = {
            "path": "src/a.py",
            "content_sha256": "current",
            "assigned_worker": "worker-01",
            "review_status": "line_reviewed_with_findings",
            "review_depth": "line_by_line",
            "reviewed_symbols_or_sections": ["all"],
            "reviewer": "/root/reviewer",
            "finding_ids": ["AUDIT-FIND-CURRENT"],
            "error_ids": [],
            "prior_audit_coverage": "none",
            "evidence_commands": ["read"],
            "reviewer_notes": "reviewed",
            "second_review_status": "not_required",
            "project_index_reconciliation": "hash_matched",
            "verified_obligations": ["semantic_line_review"],
        }
        valid_ids = {"AUDIT-FIND-CURRENT", "AUDIT-FIND-OMITTED"}
        exact = review_fragment_findings(
            [fragment],
            baseline_rows=baseline,
            valid_finding_ids=valid_ids,
            finding_ids_by_location={"src/a.py": {"AUDIT-FIND-CURRENT"}},
        )
        self.assertEqual(exact, [])
        omitted = "\n".join(
            review_fragment_findings(
                [fragment],
                baseline_rows=baseline,
                valid_finding_ids=valid_ids,
                finding_ids_by_location={
                    "src/a.py": {"AUDIT-FIND-CURRENT", "AUDIT-FIND-OMITTED"}
                },
            )
        )
        self.assertIn("omits current path-local findings: AUDIT-FIND-OMITTED", omitted)
        unexpected = "\n".join(
            review_fragment_findings(
                [fragment],
                baseline_rows=baseline,
                valid_finding_ids=valid_ids,
                finding_ids_by_location={"src/else.py": {"AUDIT-FIND-CURRENT"}},
            )
        )
        self.assertIn("claims findings not located on this path: AUDIT-FIND-CURRENT", unexpected)

    def test_review_merge_refuses_stale_worktree_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            source = root / "src" / "a.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "src/a.py"], cwd=root, check=True)
            row = coverage_row(status="pending")
            row.update(
                {
                    "git_blob_hash": git_blob_map(root=root)["src/a.py"][1],
                    "content_sha256": sha256_file(source),
                    "file_size_bytes": source.stat().st_size,
                    "total_lines": 1,
                    "source_lines": 1,
                    "review_depth": "inventory_only",
                    "reviewed_symbols_or_sections": [],
                    "reviewer": "",
                    "reviewer_notes": "",
                    "verified_obligations": [],
                }
            )
            output_dir = root / "audit"
            workers = output_dir / "workers"
            workers.mkdir(parents=True)
            matrix = output_dir / "COVERAGE_MATRIX.jsonl"
            matrix.write_text(jsonl_text([row]), encoding="utf-8")
            fragment = {
                "path": "src/a.py",
                "content_sha256": row["content_sha256"],
                "assigned_worker": "worker",
                "review_status": "line_reviewed_no_findings",
                "review_depth": "line_by_line",
                "reviewed_symbols_or_sections": ["all"],
                "reviewer": "reviewer",
                "finding_ids": [],
                "error_ids": [],
                "prior_audit_coverage": "none",
                "evidence_commands": ["read"],
                "reviewer_notes": "reviewed",
                "second_review_status": "not_required",
                "project_index_reconciliation": "hash_matched",
                "verified_obligations": ["semantic_line_review"],
            }
            (workers / "worker-99-review.jsonl").write_text(jsonl_text([fragment]), encoding="utf-8")
            before = matrix.read_bytes()
            source.write_text("value = 2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "baseline is stale"):
                merge_review_ledgers(output_dir, root=root)
            self.assertEqual(matrix.read_bytes(), before)
            self.assertFalse((output_dir / "COVERAGE_MATRIX.csv").exists())

    def test_missing_tracked_worktree_file_uses_current_index_blob(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "audit@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Audit Test"], cwd=root, check=True)
            source = root / "src" / "a.py"
            source.parent.mkdir(parents=True)
            payload = b"value = 1\n"
            source.write_bytes(payload)
            subprocess.run(["git", "add", "src/a.py"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
            source.unlink()
            output_dir = root / "audit"
            rows = write_outputs(output_dir, root=root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["content_source"], "git_index_blob")
            self.assertEqual(rows[0]["content_sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual((rows[0]["total_lines"], rows[0]["source_lines"]), (1, 1))
            self.assertEqual(current_content_findings(rows, expected_paths={"src/a.py"}, root=root), [])
            source.write_bytes(payload)
            self.assertIn(
                "content source changed after ledger generation",
                "\n".join(current_content_findings(rows, expected_paths={"src/a.py"}, root=root)),
            )

    def test_special_git_modes_use_index_identity_without_following_worktree(self) -> None:
        module = "mediapipeline.tools.dev.repository_audit_ledger"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            link_path = "links/external.py"
            materialized_link = root / link_path
            materialized_link.parent.mkdir(parents=True)
            materialized_link.write_text("external target bytes must be ignored\n", encoding="utf-8")
            link_payload = b"../../outside.py"
            link_blob = "b" * 40
            with (
                mock.patch(f"{module}.git_tracked_paths", return_value=[link_path]),
                mock.patch(f"{module}.git_untracked_paths", return_value=[]),
                mock.patch(f"{module}.git_blob_map", return_value={link_path: ("120000", link_blob)}),
                mock.patch(f"{module}.git_blob_bytes", return_value=link_payload),
            ):
                rows = build_rows(root=root, output_dir=root / "audit", project_records={})
                self.assertEqual(rows[0]["content_source"], "git_index_blob")
                self.assertEqual(rows[0]["content_sha256"], hashlib.sha256(link_payload).hexdigest())
                self.assertEqual(rows[0]["file_category"], "metadata/packaging")
                self.assertEqual(current_content_findings(rows, expected_paths={link_path}, root=root), [])
                materialized_link.unlink()
                with mock.patch(f"{module}.git_blob_map", return_value={link_path: ("100644", link_blob)}):
                    self.assertIn(
                        "Git index mode changed after ledger generation",
                        "\n".join(current_content_findings(rows, expected_paths={link_path}, root=root)),
                    )
                (root / ".git").mkdir()
                link_finding = finding_record()
                link_finding["locations"] = [
                    {"path": link_path, "start_line": 1, "end_line": 1, "symbol": "link target"}
                ]
                self.assertEqual(finding_record_findings([link_finding], root=root), [])

            gitlink_path = "vendor/submodule"
            gitlink_commit = "c" * 40
            with (
                mock.patch(f"{module}.git_tracked_paths", return_value=[gitlink_path]),
                mock.patch(f"{module}.git_untracked_paths", return_value=[]),
                mock.patch(f"{module}.git_blob_map", return_value={gitlink_path: ("160000", gitlink_commit)}),
                mock.patch(f"{module}.git_blob_bytes", side_effect=AssertionError("gitlink is not a blob")),
            ):
                rows = build_rows(root=root, output_dir=root / "audit", project_records={})
                self.assertEqual(rows[0]["content_source"], "git_index_gitlink")
                self.assertEqual(
                    rows[0]["content_sha256"],
                    hashlib.sha256(f"gitlink:{gitlink_commit}".encode("ascii")).hexdigest(),
                )
                self.assertEqual(rows[0]["file_category"], "metadata/packaging")
                self.assertEqual(current_content_findings(rows, expected_paths={gitlink_path}, root=root), [])

            regular_mode_row = coverage_row(path=link_path, status="pending")
            regular_mode_row.update({"git_mode": "100644", "git_blob_hash": link_blob})
            with (
                mock.patch(f"{module}.git_tracked_paths", return_value=[link_path]),
                mock.patch(f"{module}.git_blob_map", return_value={link_path: ("100644", link_blob)}),
                mock.patch.object(type(root), "is_symlink", return_value=True),
            ):
                self.assertIn(
                    "unsafe worktree path: worktree path is a symlink",
                    "\n".join(
                        current_content_findings(
                            [regular_mode_row],
                            expected_paths={link_path},
                            root=root,
                        )
                    ),
                )

    def test_review_fragment_loader_includes_established_prior_audit_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "audit"
            workers = output_dir / "workers"
            workers.mkdir(parents=True)
            (workers / "worker-99-review.jsonl").write_text(
                jsonl_text([{"path": "src/current.py"}]),
                encoding="utf-8",
            )
            (workers / "prior-production-audit-review.jsonl").write_text(
                jsonl_text([{"path": "src/prior.py"}]),
                encoding="utf-8",
            )
            records = load_review_fragments(output_dir)
            self.assertEqual([record["path"] for record in records], ["src/prior.py", "src/current.py"])
            self.assertEqual(
                [record["source_fragment"] for record in records],
                [
                    "workers/prior-production-audit-review.jsonl",
                    "workers/worker-99-review.jsonl",
                ],
            )

    def test_finding_records_require_evidence_shape(self) -> None:
        record = finding_record()
        self.assertEqual(finding_record_findings([record]), [])
        broken = {**record, "severity": "P9", "locations": []}
        findings = "\n".join(finding_record_findings([broken]))
        self.assertIn("invalid severity", findings)
        self.assertIn("locations must be a nonempty array", findings)

    def test_finding_records_reject_exact_duplicate_root_causes_and_stale_fingerprints(self) -> None:
        first = finding_record(finding_id="AUDIT-FIND-TEST-001")
        second = finding_record(finding_id="AUDIT-FIND-TEST-002")
        self.assertEqual(finding_root_cause_fingerprint(first), finding_root_cause_fingerprint(second))
        joined = "\n".join(finding_record_findings([first, second]))
        self.assertIn("duplicate root-cause fingerprint", joined)
        stale = {**first, "root_cause_fingerprint": "stale"}
        self.assertIn("stored root-cause fingerprint is stale", "\n".join(finding_record_findings([stale])))

    def test_finding_locations_reject_parent_absolute_and_outside_root_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "a.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n", encoding="utf-8")
            normal = finding_record(finding_id="AUDIT-FIND-TEST-001")
            parent_alias = finding_record(finding_id="AUDIT-FIND-TEST-002")
            parent_alias["locations"] = [{"path": "src/../src/a.py", "start_line": 1, "end_line": 1, "symbol": "a"}]
            joined = "\n".join(finding_record_findings([normal, parent_alias], root=root))
            self.assertIn("invalid finding location path", joined)
            with self.assertRaisesRegex(ValueError, "repository-relative"):
                strict_repository_relative_path("C:/outside.py")
            with self.assertRaisesRegex(ValueError, "parent segments"):
                strict_repository_relative_path("../outside.py")
            with self.assertRaisesRegex(ValueError, "dot or space"):
                strict_repository_relative_path("src/a.py.")
            with self.assertRaisesRegex(ValueError, "dot or space"):
                strict_repository_relative_path("src/a.py ")
            with self.assertRaisesRegex(ValueError, "Windows-invalid"):
                strict_repository_relative_path("src/a.py:stream")
            with self.assertRaisesRegex(ValueError, "Windows-reserved"):
                strict_repository_relative_path("src/CON.txt")
            with self.assertRaisesRegex(ValueError, "Windows-reserved"):
                strict_repository_relative_path("src/COM¹.txt")
            with self.assertRaisesRegex(ValueError, "Windows-reserved"):
                strict_repository_relative_path("src/LPT³.log")

    def test_resolved_repository_path_rejects_available_windows_short_name_alias(self) -> None:
        if os.name != "nt":
            self.skipTest("Win32 short-name identity is Windows-specific")
        root = Path(__file__).resolve().parents[3]
        alias = "src/mediapipeline/tools/dev/REPOSI~1.PY"
        if not (root / alias).exists():
            self.skipTest("8.3 alias is not enabled on this volume")
        with self.assertRaisesRegex(ValueError, "resolved repository-relative identity"):
            resolved_repository_path(root, alias)

    def test_regular_worktree_path_rejects_resolved_ancestor_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            candidate = root / "linked" / "a.py"
            outside = root.parent / "outside" / "a.py"
            concrete_path_type = type(root)
            real_resolve = concrete_path_type.resolve

            def synthetic_resolve(path: Path, strict: bool = False) -> Path:
                if path == candidate:
                    return outside
                return real_resolve(path, strict=strict)

            with mock.patch.object(concrete_path_type, "resolve", autospec=True, side_effect=synthetic_resolve):
                with self.assertRaisesRegex(ValueError, "outside the repository root"):
                    resolved_regular_worktree_path(root, "linked/a.py")

    def test_inventory_and_freshness_never_hash_an_unsafe_resolved_worktree_path(self) -> None:
        module = "mediapipeline.tools.dev.repository_audit_ledger"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = "linked/a.py"
            blob = "d" * 40
            with (
                mock.patch(f"{module}.git_tracked_paths", return_value=[path]),
                mock.patch(f"{module}.git_untracked_paths", return_value=[]),
                mock.patch(f"{module}.git_blob_map", return_value={path: ("100644", blob)}),
                mock.patch(f"{module}.resolved_regular_worktree_path", side_effect=ValueError("outside root")),
                mock.patch(f"{module}.sha256_file", side_effect=AssertionError("unsafe read")),
            ):
                rows = build_rows(root=root, output_dir=root / "audit", project_records={})
                self.assertEqual(rows[0]["content_source"], "unsafe_worktree_path")
                self.assertEqual(rows[0]["content_sha256"], "")
                self.assertIn(
                    "unsafe worktree path: outside root",
                    "\n".join(current_content_findings(rows, expected_paths={path}, root=root)),
                )

    def test_preparation_preserves_existing_and_new_historical_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "src" / "a.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n", encoding="utf-8")
            output_dir = root / "audit"
            workers = output_dir / "workers"
            workers.mkdir(parents=True)
            finding = finding_record()
            finding["related_finding_ids"] = ["FR-NEW"]
            finding["historical_related_finding_ids"] = ["CPA-2026-07-19-OLD"]
            (workers / "worker-99-findings.jsonl").write_text(jsonl_text([finding]), encoding="utf-8")
            finding_records, finding_findings = prepare_finding_records(output_dir, root=root)
            self.assertEqual(finding_findings, [])
            self.assertEqual(
                finding_records[0]["historical_related_finding_ids"],
                ["CPA-2026-07-19-OLD", "FR-NEW"],
            )
            error = {
                "id": "AUDIT-ERR-TEST-001",
                "timestamp": "2026-07-20",
                "command": "test",
                "working_directory": "repo",
                "exit_code": 1,
                "output_summary": "expected",
                "phase": "test",
                "classification": "expected negative-path result",
                "reproduction_status": "reproduced",
                "retry_result": "closed",
                "linked_finding_ids": ["FR-NEW"],
                "historical_linked_finding_ids": ["CPA-2026-07-19-OLD"],
                "coverage_blocked": False,
                "disposition": "closed",
            }
            (workers / "worker-99-errors.jsonl").write_text(jsonl_text([error]), encoding="utf-8")
            error_records, error_findings = prepare_error_records(
                output_dir,
                valid_finding_ids={"AUDIT-FIND-TEST-001"},
            )
            self.assertEqual(error_findings, [])
            self.assertEqual(
                error_records[0]["historical_linked_finding_ids"],
                ["CPA-2026-07-19-OLD", "FR-NEW"],
            )

    def test_artifact_set_rolls_back_after_third_replacement_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.txt"
            second = root / "second.txt"
            third = root / "third.txt"
            first.write_text("old-first", encoding="utf-8")
            second.write_text("old-second", encoding="utf-8")
            third.write_text("old-third", encoding="utf-8")
            real_replace = os.replace
            attempts = 0

            def fail_second_replace(source: str | bytes | os.PathLike[str], destination: str | bytes | os.PathLike[str]) -> None:
                nonlocal attempts
                attempts += 1
                if attempts == 3:
                    raise OSError("synthetic third replacement failure")
                real_replace(source, destination)

            with mock.patch(
                "mediapipeline.tools.dev.repository_audit_ledger.os.replace",
                side_effect=fail_second_replace,
            ):
                with self.assertRaisesRegex(OSError, "synthetic third replacement failure"):
                    atomic_write_text_set([(first, "new-first"), (second, "new-second"), (third, "new-third")])
            self.assertEqual(first.read_text(encoding="utf-8"), "old-first")
            self.assertEqual(second.read_text(encoding="utf-8"), "old-second")
            self.assertEqual(third.read_text(encoding="utf-8"), "old-third")

    def test_strict_check_reconstructs_review_fragments_and_checks_coverage_mirrors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "audit@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Audit Test"], cwd=root, check=True)
            source = root / "src" / "a.py"
            source.parent.mkdir(parents=True)
            source.write_text("value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "src/a.py"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
            output_dir = root / "audit"
            row = write_outputs(output_dir, root=root)[0]
            workers = output_dir / "workers"
            workers.mkdir(parents=True)
            fragment = {
                "path": "src/a.py",
                "content_sha256": row["content_sha256"],
                "assigned_worker": row["assigned_worker"],
                "review_status": "line_reviewed_no_findings",
                "review_depth": "line_by_line",
                "reviewed_symbols_or_sections": ["all"],
                "reviewer": "reviewer",
                "finding_ids": [],
                "error_ids": [],
                "prior_audit_coverage": "no applicable prior finding",
                "evidence_commands": ["line-numbered source read"],
                "reviewer_notes": "Current bytes and every line were reviewed.",
                "second_review_status": "not_required",
                "project_index_reconciliation": "not_indexed_with_rationale",
                "verified_obligations": row["verification_obligations"],
                "responsibility_summary": "Synthetic source used to prove review-ledger freshness.",
            }
            fragment_path = workers / "worker-99-review.jsonl"
            fragment_path.write_text(jsonl_text([fragment]), encoding="utf-8")
            merge_review_ledgers(output_dir, root=root)
            merge_finding_ledgers(output_dir, root=root)
            merge_error_ledgers(output_dir, root=root)
            self.assertEqual(check_outputs(output_dir, root=root, require_complete=True), [])
            (output_dir / "COVERAGE_MATRIX.csv").unlink()
            self.assertIn(
                "COVERAGE_MATRIX.csv is missing or stale",
                "\n".join(check_outputs(output_dir, root=root, require_complete=True)),
            )
            merge_review_ledgers(output_dir, root=root)
            fragment["review_status"] = "blocked_with_reason"
            fragment_path.write_text(jsonl_text([fragment]), encoding="utf-8")
            self.assertIn(
                "not the deterministic merge of current review fragments",
                "\n".join(check_outputs(output_dir, root=root, require_complete=True)),
            )

    def test_independent_attestation_rejects_self_review_and_covers_p1_findings(self) -> None:
        row = coverage_row(risk_tier="high")
        first_review = {
            "path": row["path"],
            "reviewer": "/root/first_reviewer",
            "review_status": row["review_status"],
        }
        self_review = second_review_attestation(row, reviewer="/root/first_reviewer")
        joined = "\n".join(
            second_review_attestation_findings(
                [self_review],
                baseline_rows={str(row["path"]): row},
                first_review_records=[first_review],
            )
        )
        self.assertIn("reviewer identities are the same", joined)
        p1 = {**finding_record(), "severity": "P1"}
        first_review["finding_ids"] = [str(p1["id"])]
        independent = second_review_attestation(row, finding_ids=[str(p1["id"])])
        self.assertEqual(
            second_review_attestation_findings(
                [independent],
                baseline_rows={str(row["path"]): row},
                first_review_records=[first_review],
                valid_finding_ids={str(p1["id"])},
                valid_error_ids=set(),
                finding_dispositions={str(p1["id"]): "confirmed"},
                finding_location_paths={str(p1["id"]): {"SRC/A.PY"}},
            ),
            [],
        )
        self.assertEqual(independent_review_completion_findings([row], [p1], [independent]), [])
        missing = "\n".join(independent_review_completion_findings([row], [p1], []))
        self.assertIn("high-risk achieved rows lack independent attestations", missing)
        self.assertIn("P0/P1 findings lack independent disposition attestations", missing)
        mismatched_first = {**first_review, "finding_ids": []}
        mismatch = "\n".join(
            second_review_attestation_findings(
                [independent],
                baseline_rows={str(row["path"]): row},
                first_review_records=[mismatched_first],
            )
        )
        self.assertIn("independent and first-pass finding ID sets disagree", mismatch)
        unrelated = {**p1, "locations": [{"path": "src/unrelated.py", "start_line": 1, "end_line": 1, "symbol": "x"}]}
        misplaced = "\n".join(
            second_review_attestation_findings(
                [independent],
                baseline_rows={str(row["path"]): row},
                first_review_records=[first_review],
                valid_finding_ids={str(p1["id"])},
                finding_location_paths={str(p1["id"]): {"src/unrelated.py"}},
            )
        )
        self.assertIn("independently reviewed finding is not located on the attested path", misplaced)
        self.assertIn(
            str(p1["id"]),
            "\n".join(independent_review_completion_findings([row], [unrelated], [independent])),
        )

    def test_review_merge_derives_second_review_status_only_from_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "audit@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Audit Test"], cwd=root, check=True)
            source = root / "ops" / "pipeline" / "engine" / "storage" / "move.ps1"
            source.parent.mkdir(parents=True)
            source.write_text("$value = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", source.relative_to(root).as_posix()], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
            output_dir = root / "audit"
            row = write_outputs(output_dir, root=root)[0]
            self.assertEqual(row["risk_tier"], "high")
            workers = output_dir / "workers"
            workers.mkdir(parents=True)
            fragment = {
                "path": row["path"],
                "content_sha256": row["content_sha256"],
                "assigned_worker": row["assigned_worker"],
                "review_status": "line_reviewed_no_findings",
                "review_depth": "line_by_line",
                "reviewed_symbols_or_sections": ["all"],
                "reviewer": "/root/first_reviewer",
                "finding_ids": [],
                "error_ids": [],
                "prior_audit_coverage": "no applicable prior finding",
                "evidence_commands": ["line-numbered source read"],
                "reviewer_notes": "Current bytes were reviewed.",
                "second_review_status": "complete",
                "project_index_reconciliation": "not_indexed_with_rationale",
                "verified_obligations": row["verification_obligations"],
                "responsibility_summary": "Synthetic high-risk source for independent-review proof.",
            }
            (workers / "worker-99-review.jsonl").write_text(jsonl_text([fragment]), encoding="utf-8")
            merged = merge_review_ledgers(output_dir, root=root)
            self.assertEqual(merged[0]["second_review_status"], "pending")
            attested_row = {**merged[0], "review_status": "line_reviewed_no_findings"}
            attestation = second_review_attestation(attested_row)
            (workers / "worker-99-independent-attestation.jsonl").write_text(
                jsonl_text([attestation]),
                encoding="utf-8",
            )
            merged = merge_review_ledgers(output_dir, root=root)
            self.assertEqual(merged[0]["second_review_status"], "complete")


if __name__ == "__main__":
    unittest.main()
