from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
MODULE_PATH = (
    REPO_ROOT
    / "src"
    / "mediapipeline"
    / "tools"
    / "dev"
    / "check_test_suite_subsystem_inventory.py"
)
INVENTORY_PATH = (
    REPO_ROOT
    / "docs"
    / "inventories"
    / "TEST_SUITE_SUBSYSTEM_INVENTORY.v1.json"
)
spec = importlib.util.spec_from_file_location(
    "check_test_suite_subsystem_inventory_for_tests",
    MODULE_PATH,
)
assert spec and spec.loader
inventory_check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = inventory_check
spec.loader.exec_module(inventory_check)


LEGACY_TEXT = """function Assert-True {
    param([bool]$Condition)
}
# block start
Assert-True $true "PowerShell assertion"
Invoke-PowerShellBehaviorCheck -Name "behavior" -Body { return $true }
assert payload["ok"]
raise AssertionError("embedded Python assertion")
# block end
"""


def _block(
    *,
    block_id: str = "LDRR-PS-001",
    start_anchor: str = "# block start",
    end_anchor: str = "# block end",
    active: bool = True,
) -> dict[str, object]:
    return {
        "id": block_id,
        "title": "Structured reliability assertions",
        "legacy_location": {
            "baseline_start_line": 4,
            "baseline_end_line": 9,
            "start_anchor": start_anchor,
            "end_anchor": end_anchor,
            "active": active,
        },
        "domain": "reliability",
        "risk_domains": [],
        "behavior_or_invariant": "The focused harness retains structured assertions.",
        "boundary_register_refs": [],
        "production_surfaces": ["test harness"],
        "equivalent_coverage": {
            "status": "unknown",
            "paths": [],
            "evidence": [],
        },
        "runnability": {
            "status": "runnable",
            "checked_command": "pwsh -File legacy.ps1",
            "checked_date": "2026-07-20",
            "requirements": ["PowerShell 7"],
            "blockers": [],
        },
        "fixtures_environment": {
            "fixtures": [],
            "environment": ["Windows"],
            "temp_writes": [],
        },
        "real_media_requirement": {
            "status": "not_required",
            "reason": "This is behavior-neutral test inventory tooling.",
        },
        "classification": "unclear_preserve",
        "proposed_destination": {
            "suite": "reliability",
            "path": "ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1",
            "rationale": "Preserve until equivalence is established.",
        },
        "disposition": {
            "status": "preserve",
            "change_packet": "MP-CHANGE-20260720-001",
        },
        "evidence": {
            "replacement_or_obsolescence": [],
            "validation": [],
        },
    }


def _inventory(*, blocks: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "schema_version": "test_suite_subsystem_inventory.v1",
        "owner_document": "docs/inventories/TEST_SUITE_SUBSYSTEM_INVENTORY.md",
        "legacy_script": "ops/pipeline/tests/Legacy/Invoke-LegacyDesktopReliabilityRegressionChecks.ps1",
        "baseline_sha256": "a" * 64,
        "block_marker_format": "content anchors",
        "coverage_exclusions": [],
        "blocks": [_block()] if blocks is None else blocks,
    }


def _rule_ids(findings: list[object]) -> set[str]:
    return {finding.rule_id for finding in findings}


class TestSuiteSubsystemInventoryTests(unittest.TestCase):
    def test_valid_inventory_covers_each_supported_assertion_form(self) -> None:
        findings = inventory_check.validate_inventory(
            _inventory(),
            legacy_text=LEGACY_TEXT,
        )

        self.assertEqual(findings, [])
        assertions = inventory_check.find_assertion_lines(LEGACY_TEXT)
        self.assertEqual(
            [item.kind for item in assertions],
            [
                "powershell_assert",
                "powershell_behavior_check",
                "python_assert",
                "python_raise_assertion_error",
            ],
        )

    def test_schema_version_and_classification_are_exact_enums(self) -> None:
        inventory = _inventory()
        inventory["schema_version"] = "test_suite_subsystem_inventory.v2"
        inventory["blocks"][0]["classification"] = "unique"

        findings = inventory_check.validate_inventory(
            inventory,
            legacy_text=LEGACY_TEXT,
        )

        self.assertIn("TSI001", _rule_ids(findings))
        self.assertIn("TSI010", _rule_ids(findings))

    def test_block_requires_every_inventory_and_evidence_field(self) -> None:
        inventory = _inventory()
        del inventory["blocks"][0]["production_surfaces"]
        del inventory["blocks"][0]["evidence"]

        findings = inventory_check.validate_inventory(
            inventory,
            legacy_text=LEGACY_TEXT,
        )

        missing_messages = [finding.message for finding in findings if finding.rule_id == "TSI006"]
        self.assertTrue(any("production_surfaces" in message for message in missing_messages))
        self.assertTrue(any("evidence" in message for message in missing_messages))

    def test_active_block_anchors_must_each_be_unique_and_ordered(self) -> None:
        duplicate_anchor_text = LEGACY_TEXT + "\n# block start\n"
        findings = inventory_check.validate_inventory(
            _inventory(),
            legacy_text=duplicate_anchor_text,
        )
        self.assertIn("TSI021", _rule_ids(findings))

        reversed_block = _block(start_anchor="# block end", end_anchor="# block start")
        findings = inventory_check.validate_inventory(
            _inventory(blocks=[reversed_block]),
            legacy_text=LEGACY_TEXT,
        )
        self.assertIn("TSI022", _rule_ids(findings))

    def test_uncovered_and_multiply_covered_assertions_are_rejected(self) -> None:
        too_short = _block(end_anchor='Assert-True $true "PowerShell assertion"')
        findings = inventory_check.validate_inventory(
            _inventory(blocks=[too_short]),
            legacy_text=LEGACY_TEXT,
        )
        self.assertIn("TSI024", _rule_ids(findings))

        first = _block(block_id="LDRR-PS-001")
        second = _block(block_id="LDRR-PS-002")
        findings = inventory_check.validate_inventory(
            _inventory(blocks=[first, second]),
            legacy_text=LEGACY_TEXT,
        )
        self.assertIn("TSI025", _rule_ids(findings))

    def test_documented_exclusion_covers_an_assertion_exactly_once(self) -> None:
        placeholder = _block(active=False)
        placeholder["classification"] = "obsolete_removed_surface"
        placeholder["disposition"]["status"] = "removed"
        placeholder["evidence"] = {
            "replacement_or_obsolescence": ["The placeholder surface was removed."],
            "validation": ["passed: placeholder removal evidence"],
        }
        inventory = _inventory(blocks=[placeholder])
        inventory["coverage_exclusions"] = [
            {
                "id": "HARNESS-001",
                "anchor": 'Assert-True $true "PowerShell assertion"',
                "reason": "Harness self-check outside a logical behavior block.",
            },
            {
                "id": "HARNESS-002",
                "anchor": "Invoke-PowerShellBehaviorCheck -Name",
                "reason": "Harness helper exercise.",
            },
            {
                "id": "HARNESS-003",
                "anchor": 'assert payload["ok"]',
                "reason": "Embedded helper self-check.",
            },
            {
                "id": "HARNESS-004",
                "anchor": 'raise AssertionError("embedded Python assertion")',
                "reason": "Embedded helper failure sentinel.",
            },
        ]

        self.assertEqual(
            inventory_check.validate_inventory(inventory, legacy_text=LEGACY_TEXT),
            [],
        )

        inventory["blocks"] = [_block()]
        findings = inventory_check.validate_inventory(inventory, legacy_text=LEGACY_TEXT)
        self.assertIn("TSI025", _rule_ids(findings))

    def test_exclusion_anchor_must_be_unique_and_assertion_bearing(self) -> None:
        inventory = _inventory()
        inventory["coverage_exclusions"] = [
            {
                "id": "HARNESS-001",
                "anchor": "# block start",
                "reason": "Not actually an assertion.",
            }
        ]

        findings = inventory_check.validate_inventory(inventory, legacy_text=LEGACY_TEXT)

        self.assertIn("TSI019", _rule_ids(findings))

    def test_removed_unique_block_requires_equivalent_passing_replacement(self) -> None:
        block = _block(active=False)
        block["classification"] = "uniquely_valuable_needing_migration"
        block["disposition"]["status"] = "removed"
        inventory = _inventory(blocks=[block])
        removed_text = LEGACY_TEXT.replace(
            "# block start\nAssert-True $true \"PowerShell assertion\"\n"
            "Invoke-PowerShellBehaviorCheck -Name \"behavior\" -Body { return $true }\n"
            "assert payload[\"ok\"]\n"
            "raise AssertionError(\"embedded Python assertion\")\n# block end\n",
            "",
        )

        findings = inventory_check.validate_inventory(inventory, legacy_text=removed_text)

        self.assertIn("TSI028", _rule_ids(findings))

        block["equivalent_coverage"] = {
            "status": "equivalent",
            "paths": ["tests/python/tooling/test_replacement.py"],
            "evidence": ["replacement selector exercises the invariant"],
        }
        block["evidence"] = {
            "replacement_or_obsolescence": ["Focused replacement retained the assertion."],
            "validation": ["passed: python -m unittest tests.python.tooling.test_replacement"],
        }
        self.assertEqual(
            inventory_check.validate_inventory(inventory, legacy_text=removed_text),
            [],
        )

    def test_removed_obsolete_block_requires_obsolescence_evidence(self) -> None:
        block = _block(active=False)
        block["classification"] = "obsolete_removed_surface"
        block["disposition"]["status"] = "removed"
        inventory = _inventory(blocks=[block])
        removed_text = "function Assert-True { param([bool]$Condition) }\n"

        findings = inventory_check.validate_inventory(inventory, legacy_text=removed_text)
        self.assertIn("TSI027", _rule_ids(findings))

        block["evidence"] = {
            "replacement_or_obsolescence": [
                "Architecture inventory proves the production surface was removed."
            ],
            "validation": ["passed: python -m unittest removal_readiness"],
        }
        self.assertEqual(
            inventory_check.validate_inventory(inventory, legacy_text=removed_text),
            [],
        )

    def test_unclear_block_cannot_be_removed(self) -> None:
        block = _block(active=False)
        block["disposition"]["status"] = "removed"

        findings = inventory_check.validate_inventory(
            _inventory(blocks=[block]),
            legacy_text="function Assert-True { param([bool]$Condition) }\n",
        )

        self.assertIn("TSI029", _rule_ids(findings))

    def test_inactive_and_disposition_removed_states_must_agree(self) -> None:
        block = _block(active=False)
        findings = inventory_check.validate_inventory(
            _inventory(blocks=[block]),
            legacy_text="function Assert-True { param([bool]$Condition) }\n",
        )
        self.assertIn("TSI026", _rule_ids(findings))

    def test_schema_block_id_pattern_is_enforced(self) -> None:
        inventory = _inventory()
        inventory["blocks"][0]["id"] = "LDR-0001"

        findings = inventory_check.validate_inventory(inventory, legacy_text=LEGACY_TEXT)

        self.assertTrue(any(finding.path.endswith(".id") for finding in findings))

    def test_schema_disposition_enum_is_enforced(self) -> None:
        inventory = _inventory()
        inventory["blocks"][0]["disposition"]["status"] = "inventory"

        findings = inventory_check.validate_inventory(inventory, legacy_text=LEGACY_TEXT)

        self.assertTrue(
            any(finding.path.endswith(".disposition.status") for finding in findings)
        )

    def test_schema_string_arrays_and_risk_enum_are_enforced_independently(self) -> None:
        inventory = _inventory()
        inventory["blocks"][0]["production_surfaces"] = [{"path": "legacy.ps1"}]
        findings = inventory_check.validate_inventory(inventory, legacy_text=LEGACY_TEXT)
        self.assertTrue(
            any(finding.path.endswith(".production_surfaces[0]") for finding in findings)
        )

        inventory = _inventory()
        inventory["blocks"][0]["boundary_register_refs"] = ["duplicate", "duplicate"]
        findings = inventory_check.validate_inventory(inventory, legacy_text=LEGACY_TEXT)
        self.assertTrue(any("duplicate item" in finding.message for finding in findings))

        inventory = _inventory()
        inventory["blocks"][0]["risk_domains"] = ["unknown_risk"]
        findings = inventory_check.validate_inventory(inventory, legacy_text=LEGACY_TEXT)
        self.assertTrue(any("invalid risk domain" in finding.message for finding in findings))

    def test_schema_full_date_and_top_level_path_consts_are_enforced(self) -> None:
        for checked_date in ("20260720", "2026-W30-1", "2026-02-30"):
            with self.subTest(checked_date=checked_date):
                inventory = _inventory()
                inventory["blocks"][0]["runnability"]["checked_date"] = checked_date
                findings = inventory_check.validate_inventory(inventory, legacy_text=LEGACY_TEXT)
                self.assertTrue(
                    any(finding.path.endswith(".checked_date") for finding in findings)
                )

        for field in ("owner_document", "legacy_script"):
            with self.subTest(field=field):
                inventory = _inventory()
                inventory[field] = "wrong/path"
                findings = inventory_check.validate_inventory(inventory, legacy_text=LEGACY_TEXT)
                self.assertTrue(any(finding.path == field for finding in findings))

    def test_schema_rejects_null_for_required_sha_and_risk_array(self) -> None:
        inventory = _inventory()
        inventory["baseline_sha256"] = None
        findings = inventory_check.validate_inventory(inventory, legacy_text=LEGACY_TEXT)
        self.assertTrue(any(finding.path == "baseline_sha256" for finding in findings))

        inventory = _inventory()
        inventory["blocks"][0]["risk_domains"] = None
        findings = inventory_check.validate_inventory(inventory, legacy_text=LEGACY_TEXT)
        self.assertTrue(any(finding.path.endswith(".risk_domains") for finding in findings))

    def test_schema_rejects_unexpected_properties_at_each_object_level(self) -> None:
        inventory = _inventory()
        inventory["unexpected"] = True
        block = inventory["blocks"][0]
        block["unexpected"] = True
        block["legacy_location"]["unexpected"] = True

        findings = inventory_check.validate_inventory(inventory, legacy_text=LEGACY_TEXT)
        messages = [finding.message for finding in findings]

        self.assertGreaterEqual(
            sum("unexpected fields: unexpected" in message for message in messages),
            3,
        )

        block = _block(active=True)
        block["disposition"]["status"] = "removed"
        findings = inventory_check.validate_inventory(
            _inventory(blocks=[block]),
            legacy_text=LEGACY_TEXT,
        )
        self.assertIn("TSI026", _rule_ids(findings))

    @unittest.skipUnless(
        INVENTORY_PATH.is_file(),
        "Machine-readable inventory is created by the inventory authoring tranche.",
    )
    def test_current_repository_inventory_is_valid(self) -> None:
        inventory = inventory_check.load_inventory()
        legacy_path = REPO_ROOT / inventory["legacy_script"]

        findings = inventory_check.validate_inventory(
            inventory,
            legacy_text=legacy_path.read_text(encoding="utf-8-sig"),
        )

        self.assertEqual(findings, [])

    def test_cli_returns_nonzero_and_renders_findings_for_invalid_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inventory_path = root / "inventory.json"
            legacy_path = root / "legacy.ps1"
            inventory_path.write_text('{"schema_version": "wrong"}', encoding="utf-8")
            legacy_path.write_text(LEGACY_TEXT, encoding="utf-8")

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = inventory_check.main(
                    [
                        "--inventory",
                        str(inventory_path),
                        "--legacy-script",
                        str(legacy_path),
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("TSI001", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
