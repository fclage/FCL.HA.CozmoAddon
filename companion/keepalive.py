"""Decide when to rejoin Cozmo's Wi-Fi or reopen the UDP session.

Cozmo drops the link if the station goes quiet or the radio sleeps. The
protocol ping lives in PyCozmo. This module only chooses the recovery step.
"""

from __future__ import annotations

# No RobotState for this long means the UDP session is dead (face shows COZMO 01).
STALE_STATE_S = 2.5
MIN_ACTION_GAP_S = 20.0


def session_fresh(
    *,
    connected: bool,
    state_age_s: float | None,
    stale_after: float = STALE_STATE_S,
) -> bool:
    """True when the open session is still receiving robot state."""
    if not connected or state_age_s is None:
        return False
    return state_age_s <= stale_after


def link_action(
    *,
    wifi_ok: bool,
    connected: bool,
    state_age_s: float | None,
    since_action_s: float,
    min_gap: float = MIN_ACTION_GAP_S,
    stale_after: float = STALE_STATE_S,
) -> str | None:
    """Return ``rejoin``, ``reconnect``, ``connect``, or ``None``.

    ``rejoin`` associates the dongle again, then opens the protocol.
    ``reconnect`` resets a session that stopped sending state.
    ``connect`` opens the protocol when Wi-Fi is already up.
    """
    if since_action_s < min_gap:
        return None
    if not wifi_ok:
        return "rejoin"
    if connected and (state_age_s is None or state_age_s > stale_after):
        return "reconnect"
    if not connected:
        return "connect"
    return None
