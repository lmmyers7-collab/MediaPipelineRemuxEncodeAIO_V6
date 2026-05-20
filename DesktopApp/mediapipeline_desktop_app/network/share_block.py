from __future__ import annotations


from .coordinator_policy import DEFAULT_COORDINATOR_PORT


def coerce_coordinator_port(value: object, default: int = DEFAULT_COORDINATOR_PORT) -> int:
    try:
        text = str(value or "").strip()
        port = int(text) if text else int(default)
    except (TypeError, ValueError):
        return int(default)
    if port < 1 or port > 65535:
        return int(default)
    return port


def select_coordinator_share_ip(bind_address: str, primary_ip: str, detected_ips: list[str]) -> str:
    bind = str(bind_address or "").strip()
    if bind and bind not in {"0.0.0.0", "::"}:
        return bind
    if primary_ip:
        return primary_ip
    if detected_ips:
        return detected_ips[0]
    return "<your-ip>"


def format_coordinator_share_block(
    *,
    port: object,
    token: str,
    bind_address: str,
    primary_ip: str,
    detected_ips: list[str],
) -> str:
    selected_port = coerce_coordinator_port(port)
    ip = select_coordinator_share_ip(bind_address, primary_ip, detected_ips)
    display_token = token.strip() if token else "<not yet generated>"
    return f"Coordinator URL: http://{ip}:{selected_port}\nAuth Token:      {display_token}"
