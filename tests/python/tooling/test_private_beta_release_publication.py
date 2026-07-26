from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
PUBLISH_SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "Publish-PrivateBetaGitHubRelease.ps1"
UPDATER_SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "New-TauriUpdaterChannelJson.ps1"
SOURCE_SHA = "a" * 40


def _powershell() -> str:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise unittest.SkipTest("PowerShell is required for release publication tests.")
    return shell


def _write_bundle(root: Path) -> Path:
    bundle = root / "bundle"
    nsis = bundle / "nsis"
    nsis.mkdir(parents=True)
    installer = nsis / "MediaPipelineRemuxEncodeAIO_2026.6.4+001_x64-setup.exe"
    installer.write_bytes(b"installer")
    (nsis / f"{installer.name}.sig").write_text("signature", encoding="utf-8")
    (bundle / "latest-beta.json").write_text("{}", encoding="utf-8")
    (bundle / "SHA256SUMS.txt").write_text("checksums", encoding="utf-8")
    return bundle


def _write_fake_gh(root: Path) -> tuple[Path, Path]:
    script = root / "fake-gh.ps1"
    log = root / "gh-commands.jsonl"
    script.write_text(
        r"""
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GhArgs)
$GhArgs | ConvertTo-Json -Compress | Add-Content -LiteralPath $env:FAKE_GH_LOG -Encoding UTF8
$joined = $GhArgs -join ' '
if ($GhArgs.Count -gt 0 -and $GhArgs[0] -eq 'api') {
    if ($joined -match '/releases/tags/') {
        if ($env:FAKE_GH_RELEASE_JSON -and (Test-Path -LiteralPath $env:FAKE_GH_RELEASE_JSON)) {
            Get-Content -LiteralPath $env:FAKE_GH_RELEASE_JSON -Raw
            exit 0
        }
        Write-Output 'HTTP 404: Not Found'
        exit 1
    }
    if ($joined -match '/git/ref/tags/') {
        if ($env:FAKE_GH_REF_JSON -and (Test-Path -LiteralPath $env:FAKE_GH_REF_JSON)) {
            Get-Content -LiteralPath $env:FAKE_GH_REF_JSON -Raw
            exit 0
        }
        Write-Output 'HTTP 404: Not Found'
        exit 1
    }
}
exit 0
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return script, log


def _release_payload(
    root: Path,
    *,
    sha: str = SOURCE_SHA,
    prerelease: bool = True,
    title: str | None = None,
    assets: list[dict[str, str]] | None = None,
) -> Path:
    path = root / "release.json"
    path.write_text(
        json.dumps(
            {
                "tag_name": "app-v2026.6.4+001",
                "target_commitish": sha,
                "name": title or "MediaPipelineRemuxEncodeAIO 2026.6.4+001 (beta)",
                "draft": False,
                "prerelease": prerelease,
                "assets": assets
                if assets is not None
                else [
                    {"name": "MediaPipelineRemuxEncodeAIO_2026.6.4+001_x64-setup.exe"},
                    {"name": "latest-beta.json"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _ref_payload(root: Path, *, sha: str = SOURCE_SHA) -> Path:
    path = root / "ref.json"
    path.write_text(json.dumps({"object": {"type": "commit", "sha": sha}}), encoding="utf-8")
    return path


def _run_publisher(
    root: Path,
    *,
    release_tag: str = "app-v2026.6.4+001",
    release_json: Path | None = None,
    ref_json: Path | None = None,
    allow_rebuild: bool = False,
    protected_approval: str = "false",
) -> tuple[subprocess.CompletedProcess[str], list[list[str]]]:
    root.mkdir(parents=True, exist_ok=True)
    bundle = _write_bundle(root)
    fake_gh, log = _write_fake_gh(root)
    env = os.environ.copy()
    env["FAKE_GH_LOG"] = str(log)
    if release_json:
        env["FAKE_GH_RELEASE_JSON"] = str(release_json)
    if ref_json:
        env["FAKE_GH_REF_JSON"] = str(ref_json)
    args = [
        _powershell(),
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(PUBLISH_SCRIPT),
        "-Channel",
        "beta",
        "-BundleRoot",
        str(bundle),
        "-Repository",
        "owner/repo",
        "-ReleaseTag",
        release_tag,
        "-Version",
        "2026.6.4+001",
        "-SourceCommit",
        SOURCE_SHA,
        "-ProtectedRebuildApproval",
        protected_approval,
        "-GhPath",
        str(fake_gh),
        "-AsJson",
    ]
    if allow_rebuild:
        args.append("-AllowSameCommitRebuild")
    result = subprocess.run(args, cwd=REPO_ROOT, env=env, text=True, capture_output=True, check=False)
    commands = [json.loads(line) for line in log.read_text(encoding="utf-8-sig").splitlines()] if log.exists() else []
    return result, commands


class PrivateBetaReleasePublicationTests(unittest.TestCase):
    def test_mismatched_version_tag_is_rejected_before_remote_query(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result, commands = _run_publisher(Path(temp_dir), release_tag="app-v2026.6.5+001")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, [])
        failed = {item["name"] for item in json.loads(result.stdout)["checks"] if not item["ok"]}
        self.assertIn("release_tag:version_identity", failed)

    def test_new_release_binds_target_commit_and_uploads_without_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result, commands = _run_publisher(Path(temp_dir))

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        create = next(args for args in commands if args[:2] == ["release", "create"])
        upload = next(args for args in commands if args[:2] == ["release", "upload"])
        self.assertEqual(create[create.index("--target") + 1], SOURCE_SHA)
        self.assertIn("--prerelease", create)
        self.assertNotIn("--clobber", upload)

    def test_existing_tag_on_different_commit_is_rejected_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result, commands = _run_publisher(
                root,
                release_json=_release_payload(root, sha="b" * 40),
                ref_json=_ref_payload(root, sha="b" * 40),
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(args[:2] in (["release", "create"], ["release", "upload"]) for args in commands))
        failed = {item["name"] for item in json.loads(result.stdout)["checks"] if not item["ok"]}
        self.assertIn("remote:tag_matches_source", failed)
        self.assertIn("remote:target_identity", failed)

    def test_existing_assets_are_immutable_without_dual_rebuild_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result, commands = _run_publisher(
                root,
                release_json=_release_payload(root),
                ref_json=_ref_payload(root),
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(args[:2] == ["release", "upload"] for args in commands))
        failed = {item["name"] for item in json.loads(result.stdout)["checks"] if not item["ok"]}
        self.assertIn("assets:immutable_default", failed)

    def test_existing_same_commit_release_accepts_only_missing_assets_without_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result, commands = _run_publisher(
                root,
                release_json=_release_payload(root, assets=[]),
                ref_json=_ref_payload(root),
            )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertFalse(any(args[:2] == ["release", "create"] for args in commands))
        upload = next(args for args in commands if args[:2] == ["release", "upload"])
        self.assertNotIn("--clobber", upload)

    def test_protected_same_commit_rebuild_is_the_only_clobber_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            release_json = _release_payload(root)
            ref_json = _ref_payload(root)
            denied, denied_commands = _run_publisher(
                root / "denied",
                release_json=release_json,
                ref_json=ref_json,
                allow_rebuild=True,
            )
            allowed, allowed_commands = _run_publisher(
                root / "allowed",
                release_json=release_json,
                ref_json=ref_json,
                allow_rebuild=True,
                protected_approval="true",
            )

        self.assertNotEqual(denied.returncode, 0)
        self.assertEqual(denied_commands, [])
        self.assertEqual(allowed.returncode, 0, allowed.stderr or allowed.stdout)
        upload = next(args for args in allowed_commands if args[:2] == ["release", "upload"])
        self.assertIn("--clobber", upload)
        self.assertTrue(json.loads(allowed.stdout)["rebuild_authorized"])

    def test_existing_release_channel_or_title_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result, _ = _run_publisher(
                root,
                release_json=_release_payload(root, prerelease=False, title="Wrong title"),
                ref_json=_ref_payload(root),
            )

        self.assertNotEqual(result.returncode, 0)
        failed = {item["name"] for item in json.loads(result.stdout)["checks"] if not item["ok"]}
        self.assertIn("remote:title_identity", failed)
        self.assertIn("remote:channel_identity", failed)

    def test_updater_metadata_rejects_mismatched_tag_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "latest-beta.json"
            result = subprocess.run(
                [
                    _powershell(),
                    "-NoProfile",
                    "-NonInteractive",
                    "-File",
                    str(UPDATER_SCRIPT),
                    "-Channel",
                    "beta",
                    "-BundleRoot",
                    str(root / "missing"),
                    "-Repository",
                    "owner/repo",
                    "-ReleaseTag",
                    "app-v2026.6.5+001",
                    "-Version",
                    "2026.6.4+001",
                    "-OutputPath",
                    str(output),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())
        self.assertIn("app-v<version>", result.stderr)

    def test_updater_metadata_writes_only_matching_version_tag_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bundle = _write_bundle(root)
            output = bundle / "generated-latest-beta.json"
            result = subprocess.run(
                [
                    _powershell(),
                    "-NoProfile",
                    "-NonInteractive",
                    "-File",
                    str(UPDATER_SCRIPT),
                    "-Channel",
                    "beta",
                    "-BundleRoot",
                    str(bundle),
                    "-Repository",
                    "owner/repo",
                    "-ReleaseTag",
                    "app-v2026.6.4+001",
                    "-Version",
                    "2026.6.4+001",
                    "-OutputPath",
                    str(output),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            payload = json.loads(output.read_text(encoding="utf-8-sig")) if output.exists() else {}

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(payload["version"], "2026.6.4+001")
        self.assertIn("/app-v2026.6.4+001/", payload["platforms"]["windows-x86_64"]["url"])


if __name__ == "__main__":
    unittest.main()
