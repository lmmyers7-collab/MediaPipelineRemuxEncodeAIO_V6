from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Any


@dataclass(frozen=True)
class FirewallOperationResult:
    status: str
    message: str
    command: tuple[str, ...] = ()


def resolve_netsh_path() -> str:
    system_root = os.environ.get("SystemRoot") or r"C:\Windows"
    candidate = Path(system_root) / "System32" / "netsh.exe"
    if candidate.exists():
        return str(candidate)
    return "netsh"


def build_firewall_show_rules_command(netsh_path: str | None = None) -> list[str]:
    return [
        netsh_path or resolve_netsh_path(),
        "advfirewall",
        "firewall",
        "show",
        "rule",
        "name=all",
        "dir=in",
    ]


def build_add_firewall_rule_command(port: int, netsh_path: str | None = None) -> list[str]:
    rule_name = f"MediaPipeline Coordinator (port {int(port)})"
    return [
        netsh_path or resolve_netsh_path(),
        "advfirewall",
        "firewall",
        "add",
        "rule",
        f"name={rule_name}",
        "dir=in",
        "action=allow",
        "protocol=TCP",
        "profile=private",
        "remoteip=localsubnet",
        f"localport={int(port)}",
    ]


def format_command(command: list[str] | tuple[str, ...]) -> str:
    return subprocess.list2cmdline(list(command))


def _command_output_detail(result: Any, *, max_chars: int = 500) -> str:
    parts: list[str] = []
    for label in ("stderr", "stdout"):
        value = str(getattr(result, label, "") or "").strip()
        if value:
            parts.append(value)
    if not parts:
        return ""
    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "..."
    return f"\n\nnetsh output:\n{text}"


def parse_matching_firewall_rule_names(output: str, port: int) -> list[str]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in output.splitlines():
        if line.startswith("Rule Name:"):
            if current:
                blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)

    port_text = str(int(port))
    matches: list[str] = []
    for block in blocks:
        block_text = "\n".join(block)
        if port_text not in block_text:
            continue
        if "LocalPort" not in block_text and "Protocol" not in block_text:
            continue
        matches.append(block[0].replace("Rule Name:", "").strip())
    return matches


def check_firewall_port(port: int, *, timeout_seconds: int = 15) -> FirewallOperationResult:
    command = tuple(build_firewall_show_rules_command())
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return FirewallOperationResult("warning", "netsh not found - firewall check is Windows-only.", command)
    except Exception as exc:
        return FirewallOperationResult("warning", f"Check failed: {exc}", command)

    if result.returncode != 0:
        return FirewallOperationResult(
            "warning",
            f"Firewall check failed (exit {result.returncode}) - run manually:\n"
            f"{format_command(command)}{_command_output_detail(result)}",
            command,
        )

    matches = parse_matching_firewall_rule_names(f"{result.stdout}\n{result.stderr}", port)
    if matches:
        return FirewallOperationResult(
            "ok",
            f"Inbound rule(s) for port {int(port)}: {', '.join(matches[:3])}",
            command,
        )
    return FirewallOperationResult(
        "missing",
        f"No inbound rule for port {int(port)}.\nClick 'Add Rule' to create one, or add it manually.",
        command,
    )


def add_firewall_rule(port: int, *, timeout_seconds: int = 15) -> FirewallOperationResult:
    command = tuple(build_add_firewall_rule_command(port))
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except Exception as exc:
        return FirewallOperationResult("warning", f"Error: {exc}\n\nRun manually:\n{format_command(command)}", command)

    if result.returncode == 0:
        return FirewallOperationResult("ok", f"Rule added for port {int(port)}.", command)
    return FirewallOperationResult(
        "warning",
        f"Could not add rule (exit {result.returncode}) - run as administrator:\n"
        f"{format_command(command)}{_command_output_detail(result)}",
        command,
    )
