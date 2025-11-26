"""Centralized environment/config helpers."""

import os


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() == "true"


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def crcon_url(default: str = "http://localhost:8010") -> str:
    return os.getenv("CRCON_URL", default).strip()


def crcon_api_key() -> str:
    return (os.getenv("CRCON_API_KEY") or "").strip()


def enable_kill_feed(default: bool = False) -> bool:
    return _get_bool("ENABLE_KILL_FEED", default)


def crcon_ws_url(default: str = "wss://localhost:8010/ws/logs") -> str:
    # Prefer secure websocket by default for remote servers.
    return os.getenv("CRCON_WS_URL", default).strip()


def crcon_ws_token() -> str:
    raw = (os.getenv("CRCON_WS_TOKEN") or "").strip()
    if raw:
        return raw
    return crcon_api_key()


def crcon_timeout(default: int = 15) -> int:
    return _get_int("CRCON_TIMEOUT", default)


def tanks_file(default: str = "tanks.json") -> str:
    return os.getenv("TANKS_FILE", default).strip()


def crcon_ws_heartbeat(default: int = 30) -> int:
    """Heartbeat interval (seconds) for the CRCON WebSocket; 0 disables pings."""
    return _get_int("CRCON_WS_HEARTBEAT", default)


def crcon_ws_verify_ssl(default: bool = True) -> bool:
    """Whether to verify TLS certificates for the CRCON WebSocket."""
    return _get_bool("CRCON_WS_VERIFY_SSL", default)
