from __future__ import annotations

from dataclasses import dataclass
import urllib.error
import urllib.request


@dataclass(frozen=True)
class NetworkProbeResult:
    ok: bool
    detail: str
    status_code: int | None = None


def probe_coordinator_health(base_url: str, *, timeout_seconds: int = 4) -> NetworkProbeResult:
    url = base_url.rstrip("/") + "/api/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            code = int(response.getcode())
        return NetworkProbeResult(True, f"HTTP {code}", code)
    except urllib.error.HTTPError as exc:
        return NetworkProbeResult(False, f"HTTP {exc.code}", int(exc.code))
    except Exception as exc:
        error = str(exc)
        if isinstance(exc, TimeoutError) or "timed out" in error.lower() or "refused" in error.lower():
            return NetworkProbeResult(False, f"Cannot reach {url}")
        return NetworkProbeResult(False, error[:70])


def probe_worker_auth(base_url: str, token: str, *, timeout_seconds: int = 4) -> NetworkProbeResult:
    url = base_url.rstrip("/")
    try:
        request = urllib.request.Request(
            url + "/api/workers",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            code = int(response.getcode())
        if code == 200:
            return NetworkProbeResult(True, f"Token accepted (HTTP {code})", code)
        return NetworkProbeResult(False, f"Unexpected HTTP {code}", code)
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        if code == 401:
            return NetworkProbeResult(False, "401 Unauthorized - token does not match coordinator", code)
        return NetworkProbeResult(False, f"HTTP {code}", code)
    except Exception as exc:
        error = str(exc)
        if isinstance(exc, TimeoutError) or "timed out" in error.lower() or "refused" in error.lower():
            return NetworkProbeResult(False, f"Cannot reach {url}")
        return NetworkProbeResult(False, error[:70])
