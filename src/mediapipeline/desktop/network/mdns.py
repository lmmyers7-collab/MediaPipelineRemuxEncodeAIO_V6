"""
network.mdns
============
mDNS (Bonjour / DNS-SD) helpers for coordinator auto-discovery.

Coordinator advertises on the local network as ``_mediapipeline._tcp``.
Workers can scan for coordinators instead of typing the URL manually.

Requires the optional ``zeroconf`` library.  All public functions
gracefully raise :class:`ZeroconfUnavailable` when the library is not
installed so the rest of the app never crashes on missing zeroconf.

Phase 3: full implementation.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
import threading
from collections.abc import Callable

from .local_ip import get_primary_local_ip

_log = logging.getLogger(__name__)

MDNS_SERVICE_TYPE = "_mediapipeline._tcp.local."
_INSTANCE_NAME    = "MediaPipeline Coordinator"


# ---------------------------------------------------------------------------
# Optional import guard
# ---------------------------------------------------------------------------

try:
    from zeroconf import (
        ServiceBrowser,
        ServiceInfo,
        ServiceStateChange,
        Zeroconf,
    )
    _ZEROCONF_AVAILABLE = True
except ImportError:
    ServiceBrowser = None  # type: ignore[assignment]
    ServiceInfo = None  # type: ignore[assignment]
    ServiceStateChange = None  # type: ignore[assignment]
    Zeroconf = None  # type: ignore[assignment]
    _ZEROCONF_AVAILABLE = False


class ZeroconfUnavailable(RuntimeError):
    """Raised when the ``zeroconf`` library is not installed."""


def _require_zeroconf() -> None:
    if not _ZEROCONF_AVAILABLE:
        raise ZeroconfUnavailable(
            "The 'zeroconf' package is not installed. "
            "Run 'pip install zeroconf' to enable mDNS auto-discovery."
        )


# ---------------------------------------------------------------------------
# Coordinator advertiser
# ---------------------------------------------------------------------------

def _advertised_ip_for_bind_address(bind_address: str) -> str | None:
    bind = str(bind_address or "").strip()
    if not bind or bind in {"0.0.0.0", "::"}:
        return _get_local_ip()
    if bind.startswith("[") and bind.endswith("]"):
        bind = bind[1:-1]
    try:
        parsed = ipaddress.ip_address(bind)
    except ValueError:
        try:
            resolved = socket.gethostbyname(bind)
            parsed = ipaddress.ip_address(resolved)
        except (OSError, ValueError):
            _log.warning("mDNS: could not resolve CoordinatorBindAddress %r for advertisement.", bind_address)
            return None
    if parsed.is_loopback:
        return None
    if parsed.version != 4:
        _log.warning("mDNS: skipping non-IPv4 CoordinatorBindAddress %r for advertisement.", bind_address)
        return None
    return str(parsed)


class CoordinatorAdvertiser:
    """Advertises a MediaPipeline coordinator on the local network via mDNS.

    Usage::

        adv = CoordinatorAdvertiser(port=7830)
        adv.start()
        # ...
        adv.stop()

    Or as a context manager::

        with CoordinatorAdvertiser(port=7830):
            pass  # runs until the with block exits
    """

    def __init__(self, port: int, bind_address: str = "0.0.0.0") -> None:
        _require_zeroconf()
        self._port   = port
        self._bind_address = bind_address
        self._zc: Zeroconf | None          = None
        self._info: ServiceInfo | None     = None
        self.skipped = False
        self.skip_reason = ""

    def start(self) -> bool:
        """Register the mDNS service.  Safe to call from any thread."""
        try:
            hostname    = socket.gethostname()
            local_ip    = _advertised_ip_for_bind_address(getattr(self, "_bind_address", "0.0.0.0"))
            if not local_ip:
                self.skipped = True
                self.skip_reason = f"CoordinatorBindAddress {getattr(self, '_bind_address', '')!r} is not advertised via mDNS."
                _log.info("mDNS: %s", self.skip_reason)
                return False
            service_name = f"{_INSTANCE_NAME}.{MDNS_SERVICE_TYPE}"
            self._info   = ServiceInfo(
                type_    = MDNS_SERVICE_TYPE,
                name     = service_name,
                addresses = [socket.inet_aton(local_ip)],
                port     = self._port,
                properties = {
                    "host":    hostname.encode(),
                    "version": b"1",
                },
                server   = hostname + ".local.",
            )
            self._zc = Zeroconf()
            self._zc.register_service(self._info)
            _log.info(
                "mDNS: advertised coordinator as %s on %s:%d",
                service_name, local_ip, self._port,
            )
            return True
        except Exception:
            _log.exception("mDNS: failed to register coordinator service.")
            if self._zc is not None:
                try:
                    self._zc.close()
                except Exception as exc:
                    _log.warning("mDNS: failed to close Zeroconf after registration failure: %s", exc)
            self._zc = None
            self._info = None
            return False

    def stop(self) -> None:
        """Unregister the mDNS service and close the Zeroconf instance."""
        if self._zc is not None:
            try:
                if self._info is not None:
                    self._zc.unregister_service(self._info)
            except Exception as exc:
                _log.warning("mDNS: failed to unregister coordinator service: %s", exc)
            try:
                self._zc.close()
            except Exception as exc:
                _log.warning("mDNS: failed to close Zeroconf instance: %s", exc)
            self._zc   = None
            self._info = None
            _log.info("mDNS: coordinator advertisement stopped.")

    def __enter__(self) -> CoordinatorAdvertiser:
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_coordinators(timeout_secs: float = 5.0) -> list[str]:
    """Scan the local network for MediaPipeline coordinators.

    Returns a list of ``"http://host:port"`` strings found within
    *timeout_secs* seconds.  The list may be empty if no coordinators
    are advertising or mDNS packets are blocked by the network.

    Raises :class:`ZeroconfUnavailable` when zeroconf is not installed.
    """
    _require_zeroconf()

    found: list[str]  = []
    found_lock        = threading.Lock()
    done_event        = threading.Event()
    zc: Zeroconf | None = None

    def _on_change(
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        if state_change is not ServiceStateChange.Added:
            return
        try:
            info = zeroconf.get_service_info(service_type, name, timeout=2000)
            if info is None or not info.addresses:
                return
            ip   = socket.inet_ntoa(info.addresses[0])
            port = info.port
            url  = f"http://{ip}:{port}"
            with found_lock:
                if url not in found:
                    found.append(url)
                    _log.info("mDNS discovery: found coordinator at %s", url)
        except Exception as exc:
            _log.warning("mDNS discovery: error resolving %s; continuing scan: %s", name, exc)

    try:
        zc      = Zeroconf()
        _browser = ServiceBrowser(zc, MDNS_SERVICE_TYPE, handlers=[_on_change])
        done_event.wait(timeout=timeout_secs)
    except Exception:
        _log.exception("mDNS discovery: ServiceBrowser error.")
    finally:
        if zc is not None:
            try:
                zc.close()
            except Exception as exc:
                _log.warning("mDNS discovery: failed to close Zeroconf instance: %s", exc)

    return list(found)


def discover_coordinators_async(
    callback: Callable[[list[str]], None],
    timeout_secs: float = 5.0,
) -> None:
    """Run :func:`discover_coordinators` in a daemon thread.

    *callback* is invoked on the **background thread** once the scan
    completes (after *timeout_secs*).  Callers that need to update shared
    application state must marshal the result through their own callback
    scheduler.
    """
    def _run() -> None:
        try:
            urls = discover_coordinators(timeout_secs)
        except ZeroconfUnavailable as exc:
            _log.warning("mDNS: %s", exc)
            urls = []
        except Exception:
            _log.exception("mDNS async discovery failed.")
            urls = []
        _invoke_discovery_callback(callback, urls)

    t = threading.Thread(target=_run, name="mDNS-discover", daemon=True)
    try:
        t.start()
    except Exception as exc:
        _log.warning("mDNS async discovery thread failed to start: %s", exc)
        raise RuntimeError(f"Could not start mDNS discovery thread: {exc}") from exc


def _invoke_discovery_callback(callback: Callable[[list[str]], None], urls: list[str]) -> None:
    try:
        callback(urls)
    except Exception:
        _log.exception("mDNS async discovery callback failed.")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _get_local_ip() -> str:
    """Best-effort determination of this machine's LAN IP address.

    Prefers RFC-1918 addresses over VPN tunnel IPs using the same
    priority ordering as ``views.network_tab._get_primary_ip()``:
      0 — 192.168.x.x  (typical home/office LAN)
      1 — 172.16–31.x.x
      2 — 10.x.x.x     (often used by VPN tunnels, ranked last)

    Falls back to the UDP-routing trick only when no RFC-1918 address
    is found (e.g. machine has only public or exotic-range IPs).
    """
    return get_primary_local_ip(empty_fallback="127.0.0.1")
