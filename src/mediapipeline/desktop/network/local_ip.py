"""
network.local_ip
================
Shared LAN IPv4 selection policy for Network tab display and mDNS advertising.
"""
from __future__ import annotations

import ipaddress
import logging
import socket

_log = logging.getLogger(__name__)


def rfc1918_priority(ip_str: str) -> int:
    """Return the preferred ordering for local RFC-1918 IPv4 addresses."""
    try:
        packed = int(ipaddress.IPv4Address(ip_str))
    except Exception as exc:
        _log.debug("Ignoring invalid IPv4 candidate %r: %s", ip_str, exc)
        return 999
    if (packed >> 16) == 0xC0A8:   # 192.168.x.x
        return 0
    if (packed >> 20) == 0xAC1:    # 172.16-31.x.x (/12)
        return 1
    if (packed >> 24) == 10:       # 10.x.x.x
        return 2
    return 999


def get_all_local_ips() -> list[str]:
    """Return all non-loopback, non-link-local IPv4 addresses from hostname lookup."""
    result: list[str] = []
    try:
        _, _, addrs = socket.gethostbyname_ex(socket.gethostname())
    except Exception as exc:
        _log.warning("Local IPv4 hostname lookup failed: %s", exc)
        return result
    for addr in addrs:
        try:
            ip = ipaddress.IPv4Address(addr)
        except Exception as exc:
            _log.debug("Ignoring invalid local IPv4 candidate %r: %s", addr, exc)
            continue
        if not ip.is_loopback and not ip.is_link_local:
            result.append(addr)
    return result


def get_primary_local_ip(
    candidates: list[str] | None = None,
    *,
    empty_fallback: str = "127.0.0.1",
    udp_timeout: float = 0.1,
) -> str:
    """Select the best LAN IPv4 address using the shared Network/mDNS policy."""
    all_ips = list(candidates) if candidates is not None else get_all_local_ips()
    rfc1918 = [ip for ip in all_ips if rfc1918_priority(ip) < 999]
    if rfc1918:
        return min(rfc1918, key=rfc1918_priority)

    # Fall back to the UDP routing trick only when hostname lookup does not
    # reveal a private LAN address. This may return a VPN tunnel address.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(udp_timeout)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception as exc:
        _log.warning("UDP route local IPv4 detection failed: %s", exc)
        return all_ips[0] if all_ips else empty_fallback
