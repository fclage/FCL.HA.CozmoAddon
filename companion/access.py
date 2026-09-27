"""Who may call the companion HTTP API.

``COZMO_ALLOW`` or ``--allow``:

- ``local`` or ``127.0.0.1`` — this machine only
- a network such as ``192.168.0.0/24`` — that range only
- ``private`` — loopback and private ranges (default)
- ``all`` — any address

Several rules can be combined with commas.
"""

from __future__ import annotations

import ipaddress

_LOCAL = {"local", "localhost", "127.0.0.1", "::1"}


def _addr(ip: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    addr = ipaddress.ip_address(ip.strip())
    mapped = getattr(addr, "ipv4_mapped", None)
    return mapped or addr


def _is_loopback(ip: str) -> bool:
    try:
        return _addr(ip).is_loopback
    except ValueError:
        return False


def _is_private(ip: str) -> bool:
    try:
        addr = _addr(ip)
    except ValueError:
        return False
    return addr.is_loopback or addr.is_private


def client_allowed(ip: str, policy: str | None) -> bool:
    """Return whether ``ip`` may use the API. Empty policy means ``private``."""
    raw = (policy or "private").strip()
    if not raw:
        raw = "private"
    for part in raw.split(","):
        rule = part.strip()
        if not rule:
            continue
        folded = rule.lower()
        if folded in {"all", "*"}:
            return True
        if folded == "private" and _is_private(ip):
            return True
        if folded in _LOCAL and _is_loopback(ip):
            return True
        try:
            network = ipaddress.ip_network(rule, strict=False)
        except ValueError:
            continue
        try:
            if _addr(ip) in network:
                return True
        except ValueError:
            continue
    return False
