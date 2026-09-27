"""Light-cube identity. Slots 1–3 match the symbol printed on the cube."""

from __future__ import annotations

from typing import Optional


def blank_cube() -> dict:
    return {
        "factory_id": None,
        "object_id": None,
        "connected": False,
        "battery": None,
        "missed_packets": None,
        "rssi": None,
        "last_tap": 0.0,
        "taps": 0,
        "leds": [None, None, None, None],
    }


def cube_slot(object_type) -> Optional[int]:
    """Return 1, 2, or 3 for a light cube. Chargers and ghosts are ignored."""
    if object_type is None:
        return None
    value = getattr(object_type, "value", object_type)
    if isinstance(value, int) and value in (1, 2, 3):
        return value
    text = str(object_type)
    for slot in (1, 2, 3):
        if f"LIGHTCUBE{slot}" in text:
            return slot
    return None
