"""Procedural faces that exist in pycozmo.expressions (do not invent names)."""

from __future__ import annotations

from typing import Callable

try:
    from PIL import Image
    import numpy as np
except ImportError:  # pragma: no cover - companion venv always has these
    Image = None  # type: ignore[misc, assignment]
    np = None  # type: ignore[misc, assignment]

# pycozmo.expressions class names from expressions/expressions.py
FACE_NAMES = (
    "neutral",
    "anger",
    "sadness",
    "happiness",
    "surprise",
    "disgust",
    "fear",
    "pleading",
    "vulnerability",
    "despair",
    "guilt",
    "disappointment",
    "embarrassment",
    "horror",
    "skepticism",
    "annoyance",
    "fury",
    "suspicion",
    "rejection",
    "boredom",
    "tiredness",
    "asleep",
    "confusion",
    "amazement",
    "excitement",
)

# Short list of official Cozmo clip names (present after `pycozmo_resources.py download`).
# The companion prefers live names from Client.get_anim_names() when assets are loaded.
KNOWN_CLIPS = (
    "anim_launch_wakeup_01",
    "anim_greeting_happy_03",
    "anim_freeplay_reacttoface_identified_01",
    "anim_pounce_success_02",
    "anim_bored_event_01",
    "anim_gotosleep_sleeploop_01",
    "anim_sparking_success_01",
    "anim_dizzy_reaction_medium_01",
    "anim_keepaway_getout_frustrated_01",
    "anim_cozmosays_getout_short_01",
    "anim_explorer_huh_01_head_angle_40",
    "anim_reacttocliff_edge_01",
    "anim_peekaboo_success_01",
)


def expression_factory(name: str) -> Callable:
    """Return a pycozmo.expressions class constructor for *name*."""
    import pycozmo

    key = name.strip().lower()
    if key not in FACE_NAMES:
        raise ValueError(f"Unknown expression {name!r}. Valid: {', '.join(FACE_NAMES)}")
    cls = getattr(pycozmo.expressions, key.capitalize(), None)
    if cls is None:
        raise ValueError(f"Unknown expression {name!r}. Valid: {', '.join(FACE_NAMES)}")
    return cls


def render_expression(name: str):
    """Render a 128×32 OLED image for Cozmo's display (even lines of the procedural face)."""
    if Image is None or np is None:
        raise RuntimeError("Pillow and numpy are required to render faces")
    face = expression_factory(name)()
    im = face.render()
    np_im = np.array(im)
    return Image.fromarray(np_im[::2])


def interpolate_to(cli, target_name: str, from_name: str = "neutral") -> None:
    """Animate from one procedural face to another at the robot frame rate."""
    import pycozmo

    rate = pycozmo.robot.FRAME_RATE
    from_face = expression_factory(from_name)()
    to_face = expression_factory(target_name)()
    timer = pycozmo.util.FPSTimer(rate)
    for face in pycozmo.procedural_face.interpolate(from_face, to_face, max(rate // 3, 1)):
        im = face.render()
        np_im = np.array(im)
        cli.display_image(Image.fromarray(np_im[::2]))
        timer.sleep()
