"""Shared Tdarr proof-pack constants and path policy."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Iterable


TDARR_PROOF_PACK_SCHEMA_VERSION = "tdarr_proof_pack.v1"
TDARR_PROOF_PACK_SENTINEL = ".tdarr-proof-pack.json"
TDARR_PROOF_PACK_NAME = "tdarr-proof-pack"
TDARR_PROOF_PACK_ROOT = Path("E:/Videos/TdarrMatrix/ProofPack")
TDARR_LEGACY_MATRIX_ROOT = Path("E:/Videos/TdarrMatrix/TestLibraries/TdarrMatrix")
TDARR_LEGACY_MATRIX_RUNS_ROOT = Path("E:/Videos/TdarrMatrix/TestLibraries/TdarrMatrixRuns")

TDARR_PROOF_CASE_IDS_BY_BUCKET: dict[str, tuple[str, ...]] = {
    "audio-only": (
        "tdarr-0002",
        "tdarr-0011",
        "tdarr-0023",
        "tdarr-0026",
        "tdarr-0028",
        "tdarr-0029",
    ),
    "h264-h265-direct": (
        "tdarr-0249",
        "tdarr-0258",
        "tdarr-0263",
        "tdarr-0277",
        "tdarr-0286",
        "tdarr-0295",
        "tdarr-0300",
        "tdarr-0306",
    ),
    "av1-vp-modern": (
        "tdarr-0144",
        "tdarr-0158",
        "tdarr-0161",
        "tdarr-1037",
        "tdarr-1039",
        "tdarr-1109",
    ),
    "legacy-video": (
        "tdarr-0078",
        "tdarr-0403",
        "tdarr-0937",
        "tdarr-0967",
        "tdarr-0969",
        "tdarr-1005",
        "tdarr-1294",
        "tdarr-1297",
    ),
    "mjpeg-large": (
        "tdarr-0322",
        "tdarr-0329",
        "tdarr-0343",
        "tdarr-0349",
        "tdarr-1222",
        "tdarr-1223",
    ),
    "container-stress": (
        "tdarr-0063",
        "tdarr-0143",
        "tdarr-0248",
        "tdarr-0250",
        "tdarr-0253",
        "tdarr-0285",
        "tdarr-0315",
        "tdarr-0404",
        "tdarr-0716",
        "tdarr-1187",
        "tdarr-1656",
        "tdarr-2125",
    ),
}

TDARR_SMOKE_CASE_IDS_BY_BUCKET: dict[str, tuple[str, ...]] = {
    "audio-only": ("tdarr-0002",),
    "h264-h265-direct": ("tdarr-0249", "tdarr-0286"),
    "av1-vp-modern": ("tdarr-0144", "tdarr-1109"),
    "legacy-video": ("tdarr-0403", "tdarr-0937"),
    "mjpeg-large": ("tdarr-0322", "tdarr-1222"),
    "container-stress": ("tdarr-0063", "tdarr-0248", "tdarr-0253"),
}


def tdarr_case_ids_for_pack(pack: str) -> tuple[str, ...]:
    groups = (
        TDARR_SMOKE_CASE_IDS_BY_BUCKET
        if str(pack or "").strip().casefold().replace("_", "-") in {"smoke", "smoke-pack"}
        else TDARR_PROOF_CASE_IDS_BY_BUCKET
    )
    return tuple(case_id for case_ids in groups.values() for case_id in case_ids)


def tdarr_case_keys_for_pack(pack: str, *, views: Iterable[str] = ("movies", "tv")) -> tuple[str, ...]:
    view_tokens = tuple(str(view or "").strip().casefold() for view in views if str(view or "").strip())
    return tuple(f"{case_id}:{view}" for case_id in tdarr_case_ids_for_pack(pack) for view in view_tokens)


def tdarr_expected_source_count(pack: str) -> int:
    return len(tdarr_case_ids_for_pack(pack))


def tdarr_expected_manifest_count(pack: str) -> int:
    return len(tdarr_case_keys_for_pack(pack))


def _looks_like_repo_root(workspace_root: Path) -> bool:
    return (workspace_root / "AGENTS.md").exists() and (workspace_root / "src" / "mediapipeline").exists()


def tdarr_proof_pack_root(workspace_root: Path) -> Path:
    """Default proof root.

    Real operator runs use the E-drive proof library. Temp/unit workspaces keep their
    generated roots inside the temp workspace so tests never depend on machine-local E:.
    """
    workspace_root = Path(workspace_root)
    if _looks_like_repo_root(workspace_root):
        return TDARR_PROOF_PACK_ROOT
    return workspace_root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrProofPack"


def tdarr_proof_runs_root(workspace_root: Path) -> Path:
    return tdarr_proof_pack_root(workspace_root) / "runs"


def tdarr_legacy_cache_root(workspace_root: Path) -> Path:
    return Path(workspace_root) / "LocalBase" / "TestFixtures" / "TdarrSamples"


def tdarr_legacy_cleanup_targets(workspace_root: Path) -> dict[str, Path]:
    workspace_root = Path(workspace_root)
    if _looks_like_repo_root(workspace_root):
        matrix_root = TDARR_LEGACY_MATRIX_ROOT
        runs_root = TDARR_LEGACY_MATRIX_RUNS_ROOT
    else:
        matrix_root = workspace_root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrix"
        runs_root = workspace_root / "LocalBase" / "Scratch" / "TestLibraries" / "TdarrMatrixRuns"
    return {
        "legacy_matrix_library": matrix_root,
        "legacy_matrix_runs": runs_root,
        "legacy_download_cache": tdarr_legacy_cache_root(workspace_root),
    }


__all__ = [
    "TDARR_LEGACY_MATRIX_ROOT",
    "TDARR_LEGACY_MATRIX_RUNS_ROOT",
    "TDARR_PROOF_CASE_IDS_BY_BUCKET",
    "TDARR_PROOF_PACK_NAME",
    "TDARR_PROOF_PACK_ROOT",
    "TDARR_PROOF_PACK_SCHEMA_VERSION",
    "TDARR_PROOF_PACK_SENTINEL",
    "TDARR_SMOKE_CASE_IDS_BY_BUCKET",
    "tdarr_case_ids_for_pack",
    "tdarr_case_keys_for_pack",
    "tdarr_expected_manifest_count",
    "tdarr_expected_source_count",
    "tdarr_legacy_cache_root",
    "tdarr_legacy_cleanup_targets",
    "tdarr_proof_pack_root",
    "tdarr_proof_runs_root",
]
