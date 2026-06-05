from __future__ import annotations

import logging
import json
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

REPO_ROOT = find_repo_root(Path(__file__))
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.config.library_profiles import (
    normalize_library_profile_config_values,
    promotion_rules_from_library_profiles,
)
from mediapipeline.core.config.validation import validate_config_values
from mediapipeline.core.final_library import service as promotion_service
from mediapipeline.core.final_library.promotion import (
    cleanup_verified_files,
    destination_for_output,
    match_rule_for_source,
    normalize_promotion_rules,
    promotion_settings_from_config,
    promotion_status_payload,
    promote_item,
    read_item_evidence,
)
from mediapipeline.core.final_library.promotion_parts.planning import (
    normalized_path_key,
    path_within_root,
    plan_promotion_file_targets,
)
from mediapipeline.core.final_library.promotion_parts import transfer as promotion_transfer
from mediapipeline.core.final_library.promotion_parts.transfer import companion_sidecars, copy_file_with_verification
from mediapipeline.core.final_library.service import FinalLibraryPromotionServiceMixin
from mediapipeline.desktop.config_keys import (
    KEY_FINAL_LIBRARY_PROMOTION_CLEANUP_AFTER_VERIFIED,
    KEY_FINAL_LIBRARY_PROMOTION_ENABLED,
    KEY_FINAL_LIBRARY_PROMOTION_OVERWRITE_EXISTING,
    KEY_FINAL_LIBRARY_PROMOTION_RULES,
    KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE,
    KEY_OUTSOURCE,
    KEY_SOURCE_MOVIES,
    KEY_SOURCE_TV,
)
from mediapipeline.desktop.models import CompletedJobRecord, ResolvedPaths


def _resolved(root: Path, outsource: Path, config: dict | None = None) -> ResolvedPaths:
    state = root / "LocalBase" / "State"
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline",
        config_path=root / "Config.psd1",
        audit_script_path=root / "Audit.ps1",
        rerun_script_path=root / "Rerun.ps1",
        powershell_host=None,
        local_base=root / "LocalBase",
        state_root=state,
        pending_push_path=state / "PendingServerPush",
        completed_manifest_path=state / "Completed" / "completed_jobs.jsonl",
        config_data={
            KEY_OUTSOURCE: str(outsource),
            KEY_FINAL_LIBRARY_PROMOTION_ENABLED: True,
            KEY_FINAL_LIBRARY_PROMOTION_RULES: [],
            KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE: "cautious",
            KEY_FINAL_LIBRARY_PROMOTION_CLEANUP_AFTER_VERIFIED: False,
            KEY_FINAL_LIBRARY_PROMOTION_OVERWRITE_EXISTING: False,
            **(config or {}),
        },
    )


def _record(source: Path, output: Path, *, title: str = "Movie") -> CompletedJobRecord:
    sidecar = output.with_suffix(".pipeline.json")
    return CompletedJobRecord(
        sidecar_path=sidecar,
        payload={
            "source_path": str(source),
            "output_path": str(output),
            "output_file": output.name,
            "publish_state": "published",
            "route": "remux",
            "media_type": "Movie",
            "lookup_title": title,
        },
    )


class FinalLibraryPromotionTests(unittest.TestCase):
    def test_profile_derived_rule_generated_from_normalized_builtin_profile(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source_movies = root / "SourceMovies"
            source_tv = root / "SourceTV"
            outsource = root / "Processed"
            destination = root / "FinalMovies"
            stale_destination = root / "OldFinalMovies"
            config = {
                KEY_SOURCE_MOVIES: str(source_movies),
                KEY_SOURCE_TV: str(source_tv),
                KEY_OUTSOURCE: str(outsource),
                KEY_FINAL_LIBRARY_PROMOTION_RULES: [
                    {
                        "id": "stale-movies",
                        "label": "Old Movies",
                        "enabled": True,
                        "source_root": str(source_movies),
                        "output_root": str(root / "OldProcessed"),
                        "destination_root": str(stale_destination),
                        "library_id": "old-movies",
                        "designation": "tv",
                    }
                ],
                "LibraryProfiles": [
                    {
                        "id": "movies",
                        "name": "Movies",
                        "enabled": True,
                        "designation": "movie",
                        "source_path": "",
                        "output_path": "",
                        "promotion_enabled": True,
                        "promotion_destination": str(destination),
                    }
                ],
            }

            normalized = normalize_library_profile_config_values(config, require_profiles=True)
            rules = normalized[KEY_FINAL_LIBRARY_PROMOTION_RULES]

            self.assertEqual([rule["id"] for rule in rules], ["library-profile-movies"])
            self.assertEqual(
                rules[0],
                {
                    "id": "library-profile-movies",
                    "label": "Movies promotion",
                    "enabled": True,
                    "source_root": str(source_movies),
                    "output_root": str(outsource),
                    "destination_root": str(destination),
                    "library_id": "movies",
                    "designation": "movie",
                },
            )

    def test_profile_derived_rule_generated_from_custom_inherited_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source_root = root / "ConcertsSource"
            outsource = root / "Processed"
            destination = root / "FinalConcerts"
            config = {
                KEY_SOURCE_MOVIES: str(root / "Movies"),
                KEY_SOURCE_TV: str(root / "TV"),
                KEY_OUTSOURCE: str(outsource),
                "LibraryProfiles": [
                    {
                        "id": "concerts",
                        "name": "Concerts",
                        "enabled": True,
                        "designation": "auto",
                        "source_path": str(source_root),
                        "output_path": "",
                        "promotion_enabled": True,
                        "promotion_destination": str(destination),
                    }
                ],
            }

            rules = promotion_rules_from_library_profiles(config, include_existing=False)

            self.assertEqual(len(rules), 1)
            self.assertEqual(rules[0]["id"], "library-profile-concerts")
            self.assertEqual(rules[0]["source_root"], str(source_root))
            self.assertEqual(rules[0]["output_root"], str(outsource))
            self.assertEqual(rules[0]["destination_root"], str(destination))
            self.assertEqual(rules[0]["library_id"], "concerts")
            self.assertEqual(rules[0]["designation"], "auto")

    def test_explicit_custom_output_equal_to_outsource_remains_pinned_after_outsource_changes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            original_outsource = root / "ProcessedA"
            changed_outsource = root / "ProcessedB"
            source_root = root / "ConcertsSource"
            destination = root / "FinalConcerts"
            source = source_root / "Concert.mkv"
            output = original_outsource / "Concerts" / "Concert.mkv"
            source_root.mkdir()
            output.parent.mkdir(parents=True)
            destination.mkdir()
            output.write_bytes(b"media")
            config = {
                KEY_SOURCE_MOVIES: str(root / "Movies"),
                KEY_SOURCE_TV: str(root / "TV"),
                KEY_OUTSOURCE: str(changed_outsource),
                "LibraryProfiles": [
                    {
                        "id": "concerts",
                        "name": "Concerts",
                        "enabled": True,
                        "designation": "auto",
                        "source_path": str(source_root),
                        "output_path": str(original_outsource),
                        "promotion_enabled": True,
                        "promotion_destination": str(destination),
                    }
                ],
            }

            rules = promotion_rules_from_library_profiles(config, include_existing=False)
            item = promotion_status_payload(_resolved(root, changed_outsource, config), [_record(source, output)])["items"][0]

            self.assertEqual(rules[0]["output_root"], str(original_outsource))
            self.assertTrue(item["ready_for_promotion"])
            self.assertEqual(item["library_output_root"], str(original_outsource))
            self.assertEqual(item["final_library_rule_id"], "library-profile-concerts")
            self.assertEqual(item["final_library_destination_path"], str(destination / "Concerts" / "Concert.mkv"))

    def test_promotion_enabled_profile_without_destination_is_rejected_and_generates_no_rule(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = {
                KEY_SOURCE_MOVIES: str(root / "Movies"),
                KEY_SOURCE_TV: str(root / "TV"),
                KEY_OUTSOURCE: str(root / "Processed"),
                "LibraryProfiles": [
                    {
                        "id": "concerts",
                        "name": "Concerts",
                        "enabled": True,
                        "designation": "auto",
                        "source_path": str(root / "ConcertsSource"),
                        "output_path": "",
                        "promotion_enabled": True,
                    }
                ],
            }

            errors, _warnings = validate_config_values(
                config,
                normalized_path_key=normalized_path_key,
                path_within_root=path_within_root,
            )
            rules = promotion_rules_from_library_profiles(config, include_existing=False)

            self.assertTrue(
                any("promotion_destination is required when promotion is enabled" in error for error in errors),
                errors,
            )
            self.assertEqual(rules, [])

    def test_uncovered_legacy_fallback_rule_survives_profile_rule_generation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source_root = root / "AnimeSource"
            fallback_source = root / "LegacySource"
            outsource = root / "Processed"
            destination = root / "FinalAnime"
            fallback_destination = root / "FinalLegacy"
            config = {
                KEY_SOURCE_MOVIES: str(root / "Movies"),
                KEY_SOURCE_TV: str(root / "TV"),
                KEY_OUTSOURCE: str(outsource),
                KEY_FINAL_LIBRARY_PROMOTION_RULES: [
                    {
                        "id": "legacy-uncovered",
                        "label": "Legacy uncovered",
                        "enabled": True,
                        "source_root": str(fallback_source),
                        "destination_root": str(fallback_destination),
                    }
                ],
                "LibraryProfiles": [
                    {
                        "id": "anime",
                        "name": "Anime",
                        "enabled": True,
                        "designation": "tv",
                        "source_path": str(source_root),
                        "output_path": "",
                        "promotion_enabled": True,
                        "promotion_destination": str(destination),
                    }
                ],
            }

            rules = promotion_rules_from_library_profiles(config, include_existing=True)

            self.assertEqual([rule["id"] for rule in rules], ["library-profile-anime", "legacy-uncovered"])
            self.assertEqual(rules[0]["source_root"], str(source_root))
            self.assertEqual(rules[0]["output_root"], str(outsource))
            self.assertEqual(rules[0]["destination_root"], str(destination))
            self.assertEqual(rules[0]["library_id"], "anime")
            self.assertEqual(rules[0]["designation"], "tv")
            self.assertEqual(rules[1]["source_root"], str(fallback_source))
            self.assertEqual(rules[1]["destination_root"], str(fallback_destination))

    def test_completion_gate_profile_rules_are_authoritative_and_fallback_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source_root = root / "ConcertsSource"
            fallback_source = root / "LegacySource"
            outsource = root / "Processed"
            destination = root / "FinalConcerts"
            stale_destination = root / "OldFinalConcerts"
            fallback_destination = root / "FinalLegacy"
            source = source_root / "Concert.mkv"
            output = outsource / "Concerts" / "Concert.mkv"
            legacy_source = fallback_source / "Legacy.mkv"
            legacy_output = outsource / "Legacy" / "Legacy.mkv"
            output.parent.mkdir(parents=True)
            legacy_output.parent.mkdir(parents=True)
            source.parent.mkdir(parents=True)
            legacy_source.parent.mkdir(parents=True)
            destination.mkdir()
            stale_destination.mkdir()
            fallback_destination.mkdir()
            output.write_bytes(b"media")
            legacy_output.write_bytes(b"legacy")
            config = {
                KEY_SOURCE_MOVIES: str(root / "Movies"),
                KEY_SOURCE_TV: str(root / "TV"),
                KEY_OUTSOURCE: str(outsource),
                KEY_FINAL_LIBRARY_PROMOTION_RULES: [
                    {
                        "id": "stale-concerts",
                        "label": "Old Concerts",
                        "enabled": True,
                        "source_root": str(source_root),
                        "output_root": str(root / "OldProcessed"),
                        "destination_root": str(stale_destination),
                        "library_id": "stale",
                        "designation": "movie",
                    },
                    {
                        "id": "legacy-uncovered",
                        "label": "Legacy uncovered",
                        "enabled": True,
                        "source_root": str(fallback_source),
                        "destination_root": str(fallback_destination),
                    },
                ],
                "LibraryProfiles": [
                    {
                        "id": "concerts",
                        "name": "Concerts",
                        "enabled": True,
                        "designation": "auto",
                        "source_path": str(source_root),
                        "output_path": "",
                        "promotion_enabled": True,
                        "promotion_destination": str(destination),
                    }
                ],
            }

            normalized = normalize_library_profile_config_values(config, require_profiles=True)
            rules = normalized[KEY_FINAL_LIBRARY_PROMOTION_RULES]
            payload = promotion_status_payload(
                _resolved(root, outsource, normalized),
                [_record(source, output, title="Concert"), _record(legacy_source, legacy_output, title="Legacy")],
            )
            items_by_title = {item["lookup_title"]: item for item in payload["items"]}

            self.assertEqual([rule["id"] for rule in rules], ["library-profile-concerts", "legacy-uncovered"])
            self.assertEqual(rules[0]["source_root"], str(source_root))
            self.assertEqual(rules[0]["output_root"], str(outsource))
            self.assertEqual(rules[0]["destination_root"], str(destination))
            self.assertEqual(rules[0]["library_id"], "concerts")
            self.assertEqual(rules[0]["designation"], "auto")
            self.assertNotIn("stale-concerts", {rule["id"] for rule in rules})
            self.assertNotEqual(rules[0]["destination_root"], str(stale_destination))
            self.assertEqual(rules[1]["source_root"], str(fallback_source))
            self.assertEqual(rules[1]["destination_root"], str(fallback_destination))
            self.assertEqual(items_by_title["Concert"]["library_profile_id"], "concerts")
            self.assertEqual(items_by_title["Concert"]["library_output_root"], str(outsource))
            self.assertEqual(items_by_title["Concert"]["final_library_rule_id"], "library-profile-concerts")
            self.assertEqual(items_by_title["Concert"]["final_library_destination_root"], str(destination))
            self.assertEqual(items_by_title["Legacy"]["final_library_rule_id"], "legacy-uncovered")
            self.assertEqual(items_by_title["Legacy"]["final_library_destination_root"], str(fallback_destination))

    def test_rule_matching_uses_longest_source_root_and_destination_relative_to_outsource(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "Source" / "Movies" / "4K" / "Film.mkv"
            outsource = root / "Outsource"
            output = outsource / "Movies" / "Film.mkv"
            dest_general = root / "Final" / "Movies"
            dest_specific = root / "Final" / "4K"
            rules = normalize_promotion_rules(
                [
                    {"id": "general", "label": "Movies", "enabled": True, "source_root": root / "Source", "destination_root": dest_general},
                    {"id": "specific", "label": "4K", "enabled": True, "source_root": root / "Source" / "Movies" / "4K", "destination_root": dest_specific},
                ]
            )

            matched = match_rule_for_source(source, rules)
            destination = destination_for_output(output, outsource, matched.destination_root if matched else "")

            self.assertIsNotNone(matched)
            self.assertEqual(matched.id, "specific")
            self.assertEqual(destination, dest_specific / "Movies" / "Film.mkv")

    def test_status_blocks_output_outside_outsource_and_missing_destination_rule(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            outsource = root / "Outsource"
            outsource.mkdir()
            dest = root / "Final"
            dest.mkdir()
            source = root / "Source" / "Movie.mkv"
            output = outsource / "Movie.mkv"
            source.parent.mkdir(parents=True)
            output.write_bytes(b"media")
            outside_output = root / "Elsewhere" / "Other.mkv"
            outside_output.parent.mkdir()
            outside_output.write_bytes(b"media")
            resolved = _resolved(
                root,
                outsource,
                {
                    KEY_FINAL_LIBRARY_PROMOTION_RULES: [
                        {"id": "movies", "enabled": True, "source_root": str(root / "DifferentSource"), "destination_root": str(dest)}
                    ]
                },
            )

            no_rule = promotion_status_payload(resolved, [_record(source, output)])["items"][0]
            outside = promotion_status_payload(
                _resolved(
                    root,
                    outsource,
                    {
                        KEY_FINAL_LIBRARY_PROMOTION_RULES: [
                            {"id": "movies", "enabled": True, "source_root": str(root / "Source"), "destination_root": str(dest)}
                        ]
                    },
                ),
                [_record(source, outside_output)],
            )["items"][0]

            self.assertTrue(no_rule["no_destination_rule"])
            self.assertEqual(no_rule["final_library_promotion_status"], "no_destination_rule")
            self.assertFalse(outside["ready_for_promotion"])
            self.assertEqual(outside["final_library_promotion_status"], "outside_outsource")

    def test_promote_item_fails_closed_without_resolved_destination(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            outsource = root / "Outsource"
            source = root / "Source" / "Movie.mkv"
            output = outsource / "Movie.mkv"
            source.parent.mkdir(parents=True)
            output.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            output.write_bytes(b"media")
            resolved = _resolved(root, outsource)
            item = promotion_status_payload(resolved, [_record(source, output)])["items"][0]

            evidence = promote_item(item, promotion_settings_from_config(resolved.config_data))

            self.assertFalse(evidence["success"])
            self.assertIn("Final destination path is not resolved.", evidence["failures"])
            self.assertEqual(evidence["destination_path"], "")
            self.assertTrue(output.exists())

    def test_status_uses_library_profile_output_and_promotion_destination(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source_root = root / "AnimeSource"
            output_root = root / "AnimeProcessed"
            promotion_root = root / "FinalAnime"
            source = source_root / "Show" / "Season 01" / "Show - S01E01.mkv"
            output = output_root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"
            source.parent.mkdir(parents=True)
            output.parent.mkdir(parents=True)
            promotion_root.mkdir()
            output.write_bytes(b"media")
            resolved = _resolved(
                root,
                root / "LegacyOutsource",
                {
                    "LibraryProfiles": [
                        {
                            "id": "anime",
                            "name": "Anime",
                            "enabled": True,
                            "designation": "tv",
                            "source_path": str(source_root),
                            "output_path": str(output_root),
                            "promotion_enabled": True,
                            "promotion_destination": str(promotion_root),
                            "editor_overrides": {},
                            "media_overrides": {},
                        }
                    ]
                },
            )

            item = promotion_status_payload(resolved, [_record(source, output, title="Show")])["items"][0]

            self.assertTrue(item["ready_for_promotion"])
            self.assertEqual(item["library_profile_id"], "anime")
            self.assertEqual(item["final_library_rule_id"], "library-profile-anime")
            self.assertEqual(
                item["final_library_destination_path"],
                str(promotion_root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"),
            )

    def test_status_uses_profile_inherited_output_before_stale_fallback_rule(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            outsource = root / "Processed"
            source_root = root / "ConcertsSource"
            promotion_root = root / "FinalConcerts"
            stale_destination = root / "OldFinalConcerts"
            source = source_root / "Concert.mkv"
            output = outsource / "Concerts" / "Concert.mkv"
            source_root.mkdir()
            output.parent.mkdir(parents=True)
            promotion_root.mkdir()
            stale_destination.mkdir()
            output.write_bytes(b"media")
            resolved = _resolved(
                root,
                outsource,
                {
                    KEY_FINAL_LIBRARY_PROMOTION_RULES: [
                        {
                            "id": "stale-concerts",
                            "enabled": True,
                            "source_root": str(source_root),
                            "destination_root": str(stale_destination),
                        }
                    ],
                    "LibraryProfiles": [
                        {
                            "id": "concerts",
                            "name": "Concerts",
                            "enabled": True,
                            "designation": "auto",
                            "source_path": str(source_root),
                            "output_path": "",
                            "promotion_enabled": True,
                            "promotion_destination": str(promotion_root),
                        }
                    ],
                },
            )

            item = promotion_status_payload(resolved, [_record(source, output, title="Concert")])["items"][0]

            self.assertTrue(item["ready_for_promotion"])
            self.assertEqual(item["library_profile_id"], "concerts")
            self.assertEqual(item["library_output_root"], str(outsource))
            self.assertEqual(item["final_library_rule_id"], "library-profile-concerts")
            self.assertEqual(item["final_library_destination_root"], str(promotion_root))
            self.assertEqual(item["final_library_destination_path"], str(promotion_root / "Concerts" / "Concert.mkv"))

    def test_fast_and_cautious_transfer_copy_sidecars_and_cleanup_verified_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            outsource = root / "Outsource"
            dest = root / "Final"
            source = root / "Source" / "Movie.mkv"
            output = outsource / "Movies" / "Movie.mkv"
            output.parent.mkdir(parents=True)
            dest.mkdir()
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            output.write_bytes(b"media")
            output.with_suffix(".en.srt").write_text("subtitle", encoding="utf-8")
            resolved = _resolved(
                root,
                outsource,
                {
                    KEY_FINAL_LIBRARY_PROMOTION_RULES: [
                        {"id": "movies", "enabled": True, "source_root": str(root / "Source"), "destination_root": str(dest)}
                    ],
                    KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE: "cautious",
                    KEY_FINAL_LIBRARY_PROMOTION_CLEANUP_AFTER_VERIFIED: True,
                },
            )
            item = promotion_status_payload(resolved, [_record(source, output)])["items"][0]

            evidence = promote_item(item, promotion_settings_from_config(resolved.config_data))

            self.assertTrue(evidence["success"])
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix(".en.srt").exists())
            self.assertTrue((dest / "Movies" / "Movie.mkv").exists())
            self.assertTrue((dest / "Movies" / "Movie.en.srt").exists())
            self.assertTrue(outsource.exists())
            self.assertFalse((outsource / "Movies").exists())

    def test_destructive_overwrite_replaces_existing_final_file_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            outsource = root / "Outsource"
            dest = root / "Final"
            source = root / "Source" / "Movie.mkv"
            output = outsource / "Movie.mkv"
            final = dest / "Movie.mkv"
            output.parent.mkdir(parents=True)
            dest.mkdir()
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            output.write_bytes(b"new-media")
            final.write_bytes(b"old-media")
            resolved = _resolved(
                root,
                outsource,
                {
                    KEY_FINAL_LIBRARY_PROMOTION_RULES: [
                        {"id": "movies", "enabled": True, "source_root": str(root / "Source"), "destination_root": str(dest)}
                    ],
                    KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE: "fast",
                    KEY_FINAL_LIBRARY_PROMOTION_OVERWRITE_EXISTING: True,
                },
            )
            item = promotion_status_payload(resolved, [_record(source, output)])["items"][0]

            evidence = promote_item(item, promotion_settings_from_config(resolved.config_data))

            self.assertTrue(evidence["success"])
            self.assertEqual(final.read_bytes(), b"new-media")
            self.assertEqual(evidence["overwritten_files"], [str(final)])

    def test_copy_without_overwrite_refuses_existing_destination_and_preserves_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "Outsource" / "Movie.mkv"
            destination_root = root / "Final"
            destination = destination_root / "Movie.mkv"
            source.parent.mkdir(parents=True)
            destination.parent.mkdir(parents=True)
            source.write_bytes(b"new-media")
            destination.write_bytes(b"old-media")

            result = copy_file_with_verification(
                source,
                destination,
                destination_root=destination_root,
                verification_mode="fast",
                overwrite_existing=False,
            )

            self.assertFalse(result["ok"])
            self.assertIn("overwrite is disabled", result["error"])
            self.assertEqual(source.read_bytes(), b"new-media")
            self.assertEqual(destination.read_bytes(), b"old-media")

    def test_cautious_copy_hash_mismatch_does_not_publish_destination(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "Outsource" / "Movie.mkv"
            destination_root = root / "Final"
            destination = destination_root / "Movie.mkv"
            source.parent.mkdir(parents=True)
            destination_root.mkdir(parents=True)
            source.write_bytes(b"media")

            def corrupt_copy(_source, target):
                Path(target).write_bytes(b"other")

            with patch.object(promotion_transfer.shutil, "copy2", side_effect=corrupt_copy):
                result = promotion_transfer.copy_file_with_verification(
                    source,
                    destination,
                    destination_root=destination_root,
                    verification_mode="cautious",
                    overwrite_existing=False,
                )

            self.assertFalse(result["ok"])
            self.assertIn("SHA-256 hash does not match", result["error"])
            self.assertFalse(destination.exists())
            self.assertEqual(list(destination.parent.glob(".*.promotion-*.tmp")), [])

    def test_final_verification_failure_removes_new_unverified_destination(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "Outsource" / "Movie.mkv"
            destination_root = root / "Final"
            destination = destination_root / "Movie.mkv"
            source.parent.mkdir(parents=True)
            destination_root.mkdir(parents=True)
            source.write_bytes(b"media")
            real_verify = promotion_transfer.verify_copy

            def fail_only_final_copy(check_source, check_destination, mode):
                if Path(check_destination) == destination:
                    return {
                        "source_path": str(check_source),
                        "destination_path": str(check_destination),
                        "mode": mode,
                        "exists": True,
                        "size_match": True,
                        "hash_match": False,
                        "ok": False,
                        "error": "forced final verification failure",
                    }
                return real_verify(check_source, check_destination, mode)

            with patch.object(promotion_transfer, "verify_copy", side_effect=fail_only_final_copy):
                result = promotion_transfer.copy_file_with_verification(
                    source,
                    destination,
                    destination_root=destination_root,
                    verification_mode="cautious",
                    overwrite_existing=False,
                )

            self.assertFalse(result["ok"])
            self.assertIn("forced final verification failure", result["error"])
            self.assertTrue(result["removed_unverified_destination"])
            self.assertFalse(destination.exists())
            self.assertTrue(source.exists())
            self.assertEqual(list(destination.parent.glob(".*.promotion-*.tmp")), [])

    def test_overwrite_copy_hash_mismatch_preserves_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "Outsource" / "Movie.mkv"
            destination_root = root / "Final"
            destination = destination_root / "Movie.mkv"
            source.parent.mkdir(parents=True)
            destination_root.mkdir(parents=True)
            source.write_bytes(b"new-media")
            destination.write_bytes(b"old-media")

            def corrupt_copy(_source, target):
                Path(target).write_bytes(b"bad-media")

            with patch.object(promotion_transfer.shutil, "copy2", side_effect=corrupt_copy):
                result = promotion_transfer.copy_file_with_verification(
                    source,
                    destination,
                    destination_root=destination_root,
                    verification_mode="cautious",
                    overwrite_existing=True,
                )

            self.assertFalse(result["ok"])
            self.assertFalse(result["overwritten"])
            self.assertIn("SHA-256 hash does not match", result["error"])
            self.assertEqual(source.read_bytes(), b"new-media")
            self.assertEqual(destination.read_bytes(), b"old-media")
            self.assertEqual(list(destination.parent.glob(".*.promotion-*.tmp")), [])

    def test_sidecar_discovery_uses_primary_stem_and_excludes_temp_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            primary = root / "Outsource" / "Movie.mkv"
            primary.parent.mkdir(parents=True)
            primary.write_bytes(b"media")
            expected = [
                primary.with_name("Movie.en.srt"),
                primary.with_name("Movie.pipeline.json"),
            ]
            for path in expected:
                path.write_text("sidecar", encoding="utf-8")
            primary.with_name("Movie2.en.srt").write_text("wrong stem", encoding="utf-8")
            primary.with_name("Movie.promotion-temp.srt").write_text("temp", encoding="utf-8")

            self.assertEqual(companion_sidecars(primary), expected)

    def test_cleanup_never_deletes_outsource_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            outsource = root / "Outsource"
            output = outsource / "Movie.mkv"
            outsource.mkdir()
            output.write_bytes(b"media")

            cleanup = cleanup_verified_files([{"source_path": str(output)}], outsource)

            self.assertTrue(cleanup["completed"])
            self.assertTrue(outsource.exists())
            self.assertFalse(output.exists())

    def test_cleanup_scope_skips_outside_sibling_prefix_and_removes_only_empty_publish_folders(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            publish_root = root / "Outsource"
            inside = publish_root / "Movies" / "Movie.mkv"
            keep = publish_root / "Movies" / "keep.txt"
            sibling_prefix = root / "OutsourceSibling" / "Movie.mkv"
            outside = root / "Elsewhere" / "Movie.mkv"
            for path in [inside, keep, sibling_prefix, outside]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"data")

            cleanup = cleanup_verified_files(
                [
                    {"source_path": str(inside)},
                    {"source_path": str(sibling_prefix)},
                    {"source_path": str(outside)},
                    {"source_path": str(publish_root)},
                ],
                publish_root,
            )

            self.assertTrue(cleanup["completed"])
            self.assertFalse(inside.exists())
            self.assertTrue(keep.exists())
            self.assertTrue(sibling_prefix.exists())
            self.assertTrue(outside.exists())
            self.assertTrue(publish_root.exists())
            self.assertTrue(publish_root.joinpath("Movies").exists())
            skipped = {(item["path"], item["reason"]) for item in cleanup["skipped_files"]}
            self.assertIn((str(sibling_prefix), "outside_publish_root"), skipped)
            self.assertIn((str(outside), "outside_publish_root"), skipped)
            self.assertIn((str(publish_root), "publish_root_never_deleted"), skipped)

    def test_dry_run_planning_maps_primary_and_sidecar_without_mutation_and_rejects_sibling_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            publish_root = root / "Outsource"
            destination_root = root / "Final"
            output = publish_root / "Movies" / "Movie.mkv"
            sidecar = publish_root / "Movies" / "Movie.en.srt"
            sibling_prefix_output = root / "OutsourceSibling" / "Movie.mkv"
            for path in [output, sidecar, sibling_prefix_output]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"data")
            destination_root.mkdir()

            plan = plan_promotion_file_targets(output, publish_root, destination_root, [sidecar])
            bad_plan = plan_promotion_file_targets(sibling_prefix_output, publish_root, destination_root, [])

            self.assertTrue(plan.ok)
            self.assertEqual([target.destination_path for target in plan.files], [
                destination_root / "Movies" / "Movie.mkv",
                destination_root / "Movies" / "Movie.en.srt",
            ])
            self.assertFalse((destination_root / "Movies").exists())
            self.assertTrue(output.exists())
            self.assertFalse(bad_plan.ok)
            self.assertIn("outside publish root", str(bad_plan.failures[0]))


class _PromotionHarness(FinalLibraryPromotionServiceMixin):
    def __init__(self, records: list[CompletedJobRecord]) -> None:
        self.records = records
        self.logger = logging.getLogger("final-library-promotion-test")

    def load_recent_completed_jobs(self, resolved: ResolvedPaths, *, limit: int = 500, force_refresh: bool = False):
        return self.records[:limit]

    def scan_pending_publish(self, resolved: ResolvedPaths):
        return {"rows": []}


class FinalLibraryPromotionServiceTests(unittest.TestCase):
    def test_service_promotes_selected_row_keys_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            outsource = root / "Outsource"
            dest = root / "Final"
            source_root = root / "Source"
            outsource.mkdir()
            dest.mkdir()
            source_root.mkdir()
            records = []
            for index in range(2):
                source = source_root / f"Movie{index}.mkv"
                output = outsource / f"Movie{index}.mkv"
                source.write_bytes(b"source")
                output.write_bytes(b"media")
                records.append(_record(source, output, title=f"Movie {index}"))
            resolved = _resolved(
                root,
                outsource,
                {
                    KEY_FINAL_LIBRARY_PROMOTION_RULES: [
                        {"id": "movies", "enabled": True, "source_root": str(source_root), "destination_root": str(dest)}
                    ],
                    KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE: "fast",
                },
            )
            selected_key = promotion_status_payload(resolved, records)["items"][1]["row_key"]
            harness = _PromotionHarness(records)
            promoted_keys: list[str] = []

            def record_success(item, settings):
                promoted_keys.append(str(item["row_key"]))
                return {
                    "row_key": item["row_key"],
                    "success": True,
                    "destination_path": item.get("final_library_destination_path"),
                    "failures": [],
                    "cleanup_result": {"completed": False},
                }

            with patch.object(promotion_service, "promote_item", side_effect=record_success):
                started = harness.start_final_library_promotion_run(resolved, records, row_keys=[selected_key])
                self.assertTrue(started["ok"])
                self.assertEqual(started["data"]["requested_row_keys"], [selected_key])
                deadline = time.time() + 5
                while harness._final_library_promotion_active_snapshot() and time.time() < deadline:
                    time.sleep(0.05)

            self.assertIsNone(harness._final_library_promotion_active_snapshot())
            self.assertEqual(promoted_keys, [selected_key])
            self.assertEqual(set(read_item_evidence(resolved)), {selected_key})

    def test_service_rejects_selected_rows_that_are_not_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            outsource = root / "Outsource"
            dest = root / "Final"
            source = root / "Source" / "Movie.mkv"
            output = outsource / "Movie.mkv"
            output.parent.mkdir(parents=True)
            dest.mkdir()
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            output.write_bytes(b"media")
            resolved = _resolved(root, outsource)
            records = [_record(source, output)]
            selected_key = promotion_status_payload(resolved, records)["items"][0]["row_key"]
            harness = _PromotionHarness(records)

            result = harness.start_final_library_promotion_run(resolved, records, row_keys=[selected_key])

            self.assertFalse(result["ok"])
            self.assertIn("no_eligible_selected_items", result["errors"])
            self.assertFalse(read_item_evidence(resolved))

    def test_service_rejects_duplicate_active_run_and_records_success_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            outsource = root / "Outsource"
            dest = root / "Final"
            source = root / "Source" / "Movie.mkv"
            output = outsource / "Movie.mkv"
            output.parent.mkdir(parents=True)
            dest.mkdir()
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            output.write_bytes(b"media")
            resolved = _resolved(
                root,
                outsource,
                {
                    KEY_FINAL_LIBRARY_PROMOTION_RULES: [
                        {"id": "movies", "enabled": True, "source_root": str(root / "Source"), "destination_root": str(dest)}
                    ],
                    KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE: "fast",
                },
            )
            harness = _PromotionHarness([_record(source, output)])

            def slow_success(item, settings):
                time.sleep(0.2)
                result = promote_item(item, settings)
                return result

            with patch.object(promotion_service, "promote_item", side_effect=slow_success):
                first = harness.start_final_library_promotion_run(resolved, harness.records)
                second = harness.start_final_library_promotion_run(resolved, harness.records)
                self.assertTrue(first["ok"])
                self.assertFalse(second["ok"])
                self.assertIn("Pipeline start blocked", harness.final_library_promotion_active_block_message("Pipeline start"))
                deadline = time.time() + 5
                while harness._final_library_promotion_active_snapshot() and time.time() < deadline:
                    time.sleep(0.05)

            evidence = read_item_evidence(resolved)
            self.assertEqual(len(evidence), 1)
            self.assertTrue(next(iter(evidence.values()))["success"])

    def test_service_stops_after_three_consecutive_item_failures(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            outsource = root / "Outsource"
            dest = root / "Final"
            source_root = root / "Source"
            outsource.mkdir()
            dest.mkdir()
            source_root.mkdir()
            records = []
            for index in range(4):
                source = source_root / f"Movie{index}.mkv"
                output = outsource / f"Movie{index}.mkv"
                source.write_bytes(b"source")
                output.write_bytes(b"media")
                records.append(_record(source, output, title=f"Movie {index}"))
            resolved = _resolved(
                root,
                outsource,
                {
                    KEY_FINAL_LIBRARY_PROMOTION_RULES: [
                        {"id": "movies", "enabled": True, "source_root": str(source_root), "destination_root": str(dest)}
                    ],
                    KEY_FINAL_LIBRARY_PROMOTION_VERIFICATION_MODE: "fast",
                },
            )
            harness = _PromotionHarness(records)

            def fail_item(item, settings):
                return {
                    "row_key": item["row_key"],
                    "success": False,
                    "failures": ["forced failure"],
                    "cleanup_result": {"completed": False},
                }

            with patch.object(promotion_service, "promote_item", side_effect=fail_item):
                started = harness.start_final_library_promotion_run(resolved, records)
                self.assertTrue(started["ok"])
                deadline = time.time() + 5
                while harness._final_library_promotion_active_snapshot() and time.time() < deadline:
                    time.sleep(0.05)

            manifests = sorted((resolved.state_root / "FinalLibraryPromotion").glob("*.run.json"))
            self.assertTrue(manifests)
            run_manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
            self.assertEqual(len(run_manifest["items"]), 3)
            self.assertIn("3 consecutive", run_manifest["stop_reason"])


class FinalLibraryPromotionWebViewSettingsTests(unittest.TestCase):
    def test_settings_has_dedicated_final_library_promotion_controls(self) -> None:
        static_root = REPO_ROOT / "apps" / "desktop" / "webview" / "static"
        settings_html = (static_root / "partials" / "page-settings.html").read_text(encoding="utf-8")
        settings_js = (static_root / "assets" / "settingsView.js").read_text(encoding="utf-8")
        settings_patch_review_js = (static_root / "assets" / "settings" / "patchReview.js").read_text(encoding="utf-8")
        settings_script_text = settings_js + "\n" + settings_patch_review_js
        metadata_js = (static_root / "assets" / "settingsMetadata.js").read_text(encoding="utf-8")

        self.assertIn('data-settings-tab="paths"', settings_html)
        self.assertIn("settings-final-library-enabled", settings_html)
        self.assertIn("settings-final-library-rules-rows", settings_html)
        self.assertIn("Preview Final Library Settings", settings_html)
        self.assertIn("Save Final Library Settings", settings_html)
        self.assertIn("FinalLibraryPromotionRuleDestinationRoot", settings_script_text)
        self.assertIn("collectFinalLibraryPromotionSettingsPatch", settings_script_text)
        self.assertIn("saveFinalLibraryPromotionSettings", settings_script_text)
        self.assertIn("/api/settings/save-patch", settings_script_text)
        self.assertIn("confirm_save: true", settings_script_text)
        self.assertIn("It never promotes, overwrites, cleans up, or touches media files", settings_script_text)
        self.assertIn("Existing final files are staged and verified before the replacement is revealed", metadata_js)
        self.assertIn("finalLibraryPromotionSettingsBuilderFields", metadata_js)

    def test_webview_exposes_dashboard_and_selected_file_promotion_entry_points(self) -> None:
        static_root = REPO_ROOT / "apps" / "desktop" / "webview" / "static"
        home_html = (static_root / "partials" / "page-home.html").read_text(encoding="utf-8")
        completed_html = (static_root / "partials" / "page-completed.html").read_text(encoding="utf-8")
        app_js = (static_root / "assets" / "app.js").read_text(encoding="utf-8")
        home_js = (static_root / "assets" / "app" / "home.js").read_text(encoding="utf-8")
        refresh_js = (static_root / "assets" / "app" / "refresh.js").read_text(encoding="utf-8")
        completed_js = (static_root / "assets" / "completedView.js").read_text(encoding="utf-8")
        completed_promotion_js = (static_root / "assets" / "completed" / "promotionCommands.js").read_text(encoding="utf-8")
        completed_table_js = (static_root / "assets" / "completed" / "table.js").read_text(encoding="utf-8")
        completed_script_text = completed_js + "\n" + completed_promotion_js
        lifecycle_js = (static_root / "assets" / "app" / "lifecycle.js").read_text(encoding="utf-8")

        self.assertIn('data-cross-page-target="completed" data-home-promotion-entry disabled>Promote Files</button>', home_html)
        self.assertIn("function renderHomePromotionEntry", home_js)
        self.assertIn("counts.eligible", home_js)
        self.assertIn("homePromotionRunActive", home_js)
        self.assertIn('renderHomePromotionEntry(finalLibraryPromotion || {})', app_js)
        self.assertIn("renderHomePromotionEntry?.(finalLibraryPromotion)", refresh_js)

        self.assertIn("data-completed-promote-selected disabled", completed_html)
        self.assertIn("function finalLibraryPromotionActionState", completed_script_text)
        self.assertIn("item.promoted || item.promoted_cleaned", completed_script_text)
        self.assertIn("item.output_exists === false", completed_script_text)
        self.assertIn("item.no_destination_rule", completed_script_text)
        self.assertIn("item.destination_offline", completed_script_text)
        self.assertIn("!item.final_library_destination_path", completed_script_text)
        self.assertIn("!item.ready_for_promotion", completed_script_text)
        self.assertIn("button.dataset.completedPromoteRowKey = item.row_key || \"\";", completed_script_text)
        self.assertIn("requestSelectedFinalLibraryPromotion", completed_script_text)
        self.assertIn("if (selectedRowKeys.length) request.row_keys = selectedRowKeys;", completed_script_text)
        self.assertIn('apiPost("/api/final-library-promotion/promote-queue", request)', completed_script_text)
        self.assertIn("Promote these files to their final destination?", completed_script_text)
        self.assertIn("window.confirm(finalLibraryPromotionConfirmMessage(rowCount))", completed_script_text)
        self.assertIn("await ctx.refreshCurrentOutputStatus();", completed_script_text)
        self.assertIn("Start failed", completed_script_text)
        self.assertIn("appendCompletedPromotionCellAction", completed_table_js)
        self.assertIn('tbodyId === "completed-rows"', completed_table_js)
        self.assertIn("[data-completed-promote-selected]", app_js)
        self.assertIn("[data-home-promotion-entry]", lifecycle_js)


if __name__ == "__main__":
    unittest.main()

