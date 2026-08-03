from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from mediapipeline.tools.dev.audit_sarif_provenance import (
    PROVENANCE_PROPERTY,
    compare_sarif_evidence,
    fetch_pinned_ruleset,
    main,
    normalized_sarif_digest,
    stamp_sarif_provenance,
)
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))


class _Response:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._content


def _opener(content: bytes):
    def open_request(request: object, *, timeout: int) -> _Response:
        del request
        if timeout != 60:
            raise AssertionError(f"unexpected timeout: {timeout}")
        return _Response(content)

    return open_request


def _sarif(*, scanner: str, version_field: str, version: str) -> dict[str, object]:
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": scanner, version_field: version}},
                "results": [],
            }
        ],
    }


class AuditSarifProvenanceTests(unittest.TestCase):
    def test_fetch_pinned_ruleset_writes_only_exact_digest(self) -> None:
        content = b"rules:\n- id: pinned.example\n"
        expected = hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "rules.yml"
            evidence = fetch_pinned_ruleset(
                source="https://semgrep.dev/c/p/default",
                expected_sha256=expected,
                output=output,
                opener=_opener(content),
            )

            self.assertEqual(output.read_bytes(), content)
            self.assertEqual(evidence.sha256, expected)
            self.assertEqual(evidence.bytes_written, len(content))

    def test_fetch_digest_mismatch_preserves_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "rules.yml"
            output.write_bytes(b"existing")

            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                fetch_pinned_ruleset(
                    source="https://semgrep.dev/c/p/default",
                    expected_sha256="0" * 64,
                    output=output,
                    opener=_opener(b"different"),
                )

            self.assertEqual(output.read_bytes(), b"existing")

    def test_stamp_sarif_records_verified_scanner_and_ruleset(self) -> None:
        payload = _sarif(
            scanner="Semgrep OSS",
            version_field="semanticVersion",
            version="1.172.0",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            sarif = Path(temp_dir) / "semgrep.sarif"
            sarif.write_text(json.dumps(payload), encoding="utf-8")

            evidence = stamp_sarif_provenance(
                sarif=sarif,
                scanner="semgrep",
                expected_version="1.172.0",
                ruleset_source="https://semgrep.dev/c/p/default",
                ruleset_sha256="a" * 64,
            )

            stamped = json.loads(sarif.read_text(encoding="utf-8"))
            provenance = stamped["runs"][0]["properties"][PROVENANCE_PROPERTY]
            self.assertEqual(provenance["scanner"], "semgrep")
            self.assertEqual(provenance["scanner_version"], "1.172.0")
            self.assertEqual(provenance["ruleset_sha256"], "a" * 64)
            self.assertEqual(evidence.ruleset_source, "https://semgrep.dev/c/p/default")

    def test_stamp_version_mismatch_does_not_rewrite_sarif(self) -> None:
        payload = _sarif(scanner="ruff", version_field="version", version="0.16.1")
        with tempfile.TemporaryDirectory() as temp_dir:
            sarif = Path(temp_dir) / "ruff.sarif"
            original = json.dumps(payload)
            sarif.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "version mismatch"):
                stamp_sarif_provenance(
                    sarif=sarif,
                    scanner="ruff",
                    expected_version="0.15.20",
                )

            self.assertEqual(sarif.read_text(encoding="utf-8"), original)

    def test_normalized_digest_ignores_json_layout_but_detects_evidence_changes(self) -> None:
        payload = _sarif(scanner="ruff", version_field="version", version="0.16.1")
        payload["runs"][0]["properties"] = {
            PROVENANCE_PROPERTY: {
                "scanner": "ruff",
                "scanner_version": "0.16.1",
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            compact = Path(temp_dir) / "compact.sarif"
            pretty = Path(temp_dir) / "pretty.sarif"
            compact.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            pretty.write_text(json.dumps(payload, indent=4, sort_keys=True), encoding="utf-8")

            first = normalized_sarif_digest(compact)
            second = normalized_sarif_digest(pretty)
            self.assertEqual(first.sha256, second.sha256)
            self.assertEqual(first.provenance[0]["scanner_version"], "0.16.1")
            self.assertTrue(compare_sarif_evidence((compact, pretty)).ok)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "compare-sarif",
                            "--sarif",
                            str(compact),
                            "--sarif",
                            str(pretty),
                        ]
                    ),
                    0,
                )

            payload["runs"][0]["properties"][PROVENANCE_PROPERTY][
                "scanner_version"
            ] = "0.16.2"
            pretty.write_text(json.dumps(payload), encoding="utf-8")
            self.assertNotEqual(first.sha256, normalized_sarif_digest(pretty).sha256)
            comparison = compare_sarif_evidence((compact, pretty))
            self.assertFalse(comparison.ok)
            self.assertTrue(
                any("provenance mismatch" in error for error in comparison.errors)
            )
            self.assertTrue(
                any("digest mismatch" in error for error in comparison.errors)
            )
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "compare-sarif",
                            "--sarif",
                            str(compact),
                            "--sarif",
                            str(pretty),
                        ]
                    ),
                    1,
                )

    def test_workflow_locks_and_reports_every_audit_input(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "audit-sarif.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn('RUFF_VERSION: "0.16.1"', workflow)
        self.assertIn('SEMGREP_VERSION: "1.172.0"', workflow)
        self.assertIn(
            'SEMGREP_RULESET_SHA256: "a7eb740a484688c0ba24668bb5fb7fc9a8ebc04c8eae982230d75f2ad9094bbc"',
            workflow,
        )
        self.assertNotIn('ruff>=', workflow)
        self.assertNotIn('semgrep>=', workflow)
        self.assertNotIn("--config p/default", workflow)
        self.assertIn('ruff==${RUFF_VERSION}', workflow)
        self.assertIn('semgrep==${SEMGREP_VERSION}', workflow)
        self.assertIn("audit_sarif_provenance fetch-ruleset", workflow)
        self.assertEqual(workflow.count("audit_sarif_provenance stamp-sarif"), 2)
        self.assertIn('--config "${RUNNER_TEMP}/semgrep-p-default.yml"', workflow)
        self.assertEqual(workflow.count("mediaPipelineAuditProvenance"), 2)


if __name__ == "__main__":
    unittest.main()
