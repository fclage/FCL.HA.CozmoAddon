"""Idle play. Faces are separate and stay on when this is off."""

from __future__ import annotations

IDLE_S = 30.0
GAP_S = 8.0
SLEEP_IDLE_S = 300.0

# Off the charger he may roll and turn. On the contacts, expression and head only.
FREE_ACTIONS = (
    "turn_left",
    "turn_right",
    "forward",
    "back",
    "happy",
    "curious",
    "excited",
    "head_up",
    "head_down",
    "lift_up",
    "lift_down",
)
DOCKED_ACTIONS = (
    "happy",
    "curious",
    "excited",
    "head_up",
    "head_down",
    "lift_up",
    "lift_down",
)


def sleep_ready(*, enabled: bool, idle_s: float, already: bool, timeout: float = SLEEP_IDLE_S) -> bool:
    """Power off after quiet time. The charger does not count as activity."""
    return bool(enabled) and not already and idle_s >= timeout


def auto_ready(
    *,
    enabled: bool,
    idle_s: float,
    since_action_s: float,
    busy: bool,
    timeout: float = IDLE_S,
    gap: float = GAP_S,
) -> bool:
    if not enabled or busy:
        return False
    if idle_s < timeout or since_action_s < gap:
        return False
    return True


def pick_auto_action(*, docked: bool, cliff: bool, pick: int) -> str:
    pool = list(DOCKED_ACTIONS if docked else FREE_ACTIONS)
    if cliff:
        pool = [name for name in pool if name != "forward"]
    return pool[pick % len(pool)]
