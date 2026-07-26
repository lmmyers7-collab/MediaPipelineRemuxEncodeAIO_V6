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
POINTER_SCRIPT = REPO_ROOT / "ops" / "scripts" / "release" / "Publish-TauriUpdaterChannelPointer.ps1"
SOURCE_SHA = "a" * 40
VERSION = "2026.6.4+001"
RELEASE_TAG = f"app-v{VERSION}"
ENDPOINT = "https://github.com/owner/repo/releases/download/updater-beta/latest-beta.json"


def _powershell() -> str:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise unittest.SkipTest("PowerShell is required for updater pointer tests.")
    return shell


def _write_channel_json(root: Path, *, version: str = VERSION) -> Path:
    path = root / "latest-beta.json"
    path.write_text(
        json.dumps(
            {
                "version": version,
                "notes": "test",
                "pub_date": "2026-07-23T00:00:00Z",
                "platforms": {
                    "windows-x86_64": {
                        "signature": "signed-updater-payload",
                        "url": (
                            "https://github.com/owner/repo/releases/download/"
                            f"{RELEASE_TAG}/MediaPipelineRemuxEncodeAIO_{VERSION}_x64-setup.exe"
                        ),
                    }
                },
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return path


def _write_fake_gh(root: Path) -> tuple[Path, Path]:
    script = root / "fake-gh.ps1"
    log = root / "gh-commands.jsonl"
    script.write_text(
        r"""
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GhArgs)
$GhArgs | ConvertTo-Json -Compress | Add-Content -LiteralPath $env:FAKE_GH_LOG -Encoding UTF8
$joined = $GhArgs -join ' '
if ($GhArgs.Count -gt 0 -and $GhArgs[0] -eq 'api' -and $joined -match '/releases/tags/updater-beta') {
    if ($env:FAKE_GH_POINTER_JSON -and (Test-Path -LiteralPath $env:FAKE_GH_POINTER_JSON)) {
        Get-Content -LiteralPath $env:FAKE_GH_POINTER_JSON -Raw
        exit 0
    }
    Write-Output 'HTTP 404: Not Found'
    exit 1
}
exit 0
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return script, log


def _write_fake_fetcher(root: Path) -> tuple[Path, Path]:
    script = root / "fake-fetcher.ps1"
    log = root / "endpoint-uris.txt"
    script.write_text(
        r"""
param([Parameter(Mandatory)][string]$Uri, [Parameter(Mandatory)][string]$OutputPath)
$Uri | Add-Content -LiteralPath $env:FAKE_ENDPOINT_LOG -Encoding UTF8
Copy-Item -LiteralPath $env:FAKE_ENDPOINT_BODY -Destination $OutputPath -Force
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return script, log


def _pointer_payload(root: Path, **overrides: object) -> Path:
    payload: dict[str, object] = {
        "tag_name": "updater-beta",
        "name": "MediaPipelineRemuxEncodeAIO updater channel (beta)",
        "draft": False,
        "prerelease": True,
        "immutable": False,
        "assets": [{"name": "latest-beta.json"}],
    }
    payload.update(overrides)
    path = root / "pointer-release.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_pointer(
    root: Path,
    *,
    channel_json: Path | None = None,
    pointer_json: Path | None = None,
    endpoint_body: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[list[str]], list[str]]:
    root.mkdir(parents=True, exist_ok=True)
    channel_json = channel_json or _write_channel_json(root)
    fake_gh, gh_log = _write_fake_gh(root)
    fake_fetcher, endpoint_log = _write_fake_fetcher(root)
    endpoint_body = endpoint_body or channel_json
    env = os.environ.copy()
    env["FAKE_GH_LOG"] = str(gh_log)
    env["FAKE_ENDPOINT_LOG"] = str(endpoint_log)
    env["FAKE_ENDPOINT_BODY"] = str(endpoint_body)
    if pointer_json:
        env["FAKE_GH_POINTER_JSON"] = str(pointer_json)
    result = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(POINTER_SCRIPT),
            "-Channel",
            "beta",
            "-ChannelJsonPath",
            str(channel_json),
            "-Repository",
            "owner/repo",
            "-ReleaseTag",
            RELEASE_TAG,
            "-Version",
            VERSION,
            "-SourceCommit",
            SOURCE_SHA,
            "-GhPath",
            str(fake_gh),
            "-EndpointFetcherPath",
            str(fake_fetcher),
            "-EndpointVerificationAttempts",
            "1",
            "-EndpointVerificationDelaySeconds",
            "0",
            "-AsJson",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    commands = [json.loads(line) for line in gh_log.read_text(encoding="utf-8-sig").splitlines()] if gh_log.exists() else []
    uris = endpoint_log.read_text(encoding="utf-8-sig").splitlines() if endpoint_log.exists() else []
    return result, commands, uris


class TauriUpdaterChannelPointerTests(unittest.TestCase):
    def test_new_pointer_release_is_prerelease_and_exact_endpoint_is_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result, commands, uris = _run_pointer(Path(temp_dir))

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["endpoint_verified"])
        self.assertEqual(payload["endpoint"], ENDPOINT)
        create = next(args for args in commands if args[:2] == ["release", "create"])
        self.assertEqual(create[2], "updater-beta")
        self.assertIn("--prerelease", create)
        self.assertIn("--latest=false", create)
        self.assertEqual(create[create.index("--target") + 1], SOURCE_SHA)
        self.assertEqual(len(uris), 1)
        self.assertTrue(uris[0].startswith(f"{ENDPOINT}?mediapipeline_source={SOURCE_SHA}"))

    def test_existing_pointer_replaces_only_the_channel_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result, commands, _ = _run_pointer(root, pointer_json=_pointer_payload(root))

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertFalse(any(args[:2] == ["release", "create"] for args in commands))
        upload = next(args for args in commands if args[:2] == ["release", "upload"])
        self.assertEqual(upload[2], "updater-beta")
        self.assertIn("--clobber", upload)
        self.assertTrue(json.loads(result.stdout)["pointer_asset_replaced"])

    def test_mismatched_channel_metadata_is_rejected_before_remote_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            channel_json = _write_channel_json(root, version="2026.6.5+001")
            result, commands, uris = _run_pointer(root, channel_json=channel_json)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, [])
        self.assertEqual(uris, [])
        failed = {check["name"] for check in json.loads(result.stdout)["checks"] if not check["ok"]}
        self.assertIn("channel_json:version_identity", failed)

    def test_pointer_release_policy_mismatch_is_rejected_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pointer_json = _pointer_payload(root, prerelease=False, immutable=True, assets=[{"name": "extra.zip"}])
            result, commands, uris = _run_pointer(root, pointer_json=pointer_json)

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(args[:2] in (["release", "create"], ["release", "upload"]) for args in commands))
        self.assertEqual(uris, [])
        failed = {check["name"] for check in json.loads(result.stdout)["checks"] if not check["ok"]}
        self.assertEqual(
            {"pointer_remote:prerelease", "pointer_remote:mutable", "pointer_remote:asset_scope"},
            failed,
        )

    def test_publication_fails_when_exact_endpoint_does_not_serve_published_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            wrong_body = root / "stale.json"
            wrong_body.write_text('{"version":"stale"}', encoding="utf-8")
            result, commands, uris = _run_pointer(root, endpoint_body=wrong_body)

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any(args[:2] == ["release", "create"] for args in commands))
        self.assertEqual(len(uris), 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["endpoint_verified"])
        failed = {check["name"] for check in payload["checks"] if not check["ok"]}
        self.assertIn("pointer_endpoint:exact_content", failed)


if __name__ == "__main__":
    unittest.main()
