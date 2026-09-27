"""Curated animation groups, idle pool, and spoken phrases.

Groups are preferred over exact clips — they pick a random member from the
official library.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AnimCommand:
    id: str
    label: str
    description: str
    group: Optional[str] = None
    anim: Optional[str] = None


@dataclass(frozen=True)
class Phrase:
    id: str
    label: str
    text: str


ANIM_COMMANDS: list[AnimCommand] = [
    AnimCommand("wake", "Wake up", "Power-on style wake", group="ConnectWakeUp"),
    AnimCommand("hello", "Hello", "Greet the player", group="NamedFaceInitialGreeting"),
    AnimCommand("happy", "Happy", "Cheerful reaction", group="CodeLabHappy"),
    AnimCommand("curious", "Curious", "Curious look", group="CodeLabCurious"),
    AnimCommand("celebrate", "Celebrate", "Victory / yay", group="CodeLabCelebrate"),
    AnimCommand("bored", "Bored", "Nothing to do", group="CodeLabBored"),
    AnimCommand("blink", "Blink", "Big blink", group="CodeLabBlink"),
    AnimCommand("pounce", "Pounce", "Pounce attack", group="PouncePounce"),
    AnimCommand("sleep", "Go to sleep", "Drift off", group="GoToSleepGetIn"),
    AnimCommand("dance", "Dance", "Mambo move", group="CodeLabDancingMambo"),
    AnimCommand("idle_bored", "Idle (bored)", "Bored idle fidget", group="NothingToDoBoredIdle"),
]

IDLE_ANIM_GROUPS: list[str] = [
    "CodeLabIdle",
    "CodeLabBlink",
    "NothingToDoBoredIdle",
    "InteractWithFaceTrackingIdle",
    "SparkIdle",
    "HikingLookAround",
    "CodeLabCurious",
]

IDLE_ANIM_CLIPS: list[str] = [
    "anim_idle_01",
    "anim_bored_01",
    "anim_sparking_idle_01",
    "anim_hiking_lookaround_01",
    "anim_lookinplaceforfaces_keepalive_short",
]

PHRASES: list[Phrase] = [
    Phrase("hello", "Hello!", "Hello!"),
    Phrase("im_cozmo", "I'm Cozmo", "Hi! I am Cozmo!"),
    Phrase("lets_play", "Let's play", "Let's play!"),
    Phrase("whee", "Whee!", "Wheee!"),
    Phrase("yay", "Yay!", "Yay!"),
    Phrase("uh_oh", "Uh oh", "Uh oh!"),
    Phrase("goodbye", "Goodbye", "Goodbye!"),
    Phrase("need_charge", "Need charge", "I need a charge soon."),
]


def catalog() -> dict:
    return {
        "animations": [
            {
                "id": a.id,
                "label": a.label,
                "description": a.description,
                "group": a.group,
                "anim": a.anim,
            }
            for a in ANIM_COMMANDS
        ],
        "phrases": [{"id": p.id, "label": p.label, "text": p.text} for p in PHRASES],
        "idle_groups": list(IDLE_ANIM_GROUPS),
    }


def anim_by_id(cmd_id: str) -> Optional[AnimCommand]:
    for a in ANIM_COMMANDS:
        if a.id == cmd_id:
            return a
    return None


def phrase_by_id(phrase_id: str) -> Optional[Phrase]:
    for p in PHRASES:
        if p.id == phrase_id:
            return p
    return None


# In-place clips only. Groups such as PouncePounce drive the wheels.
MOODS: dict[str, dict] = {
    "cheerful": {
        "face": "happiness",
        "clips": ("anim_sparking_idle_01", "anim_idle_01"),
        "color": (0, 160, 40),
    },
    "curious": {
        "face": "confusion",
        "clips": ("anim_hiking_lookaround_01", "anim_lookinplaceforfaces_keepalive_short"),
        "color": (40, 90, 220),
    },
    "playful": {
        "face": "excitement",
        "clips": ("anim_idle_01", "anim_sparking_idle_01"),
        "color": (230, 120, 0),
    },
    "sleepy": {
        "face": "tiredness",
        "clips": ("anim_bored_01", "anim_idle_01"),
        "color": (50, 20, 90),
    },
    "low_battery": {
        "face": "pleading",
        "clips": ("anim_bored_01",),
        "color": (180, 30, 20),
        "phrase": "need_charge",
    },
}


def should_greet(*, personality: bool, said_hello: bool, docked: bool) -> bool:
    """The hello clip drives off the contacts. Skip it while he is docked."""
    return bool(personality) and not said_hello and not docked


# One in four shifts lands on the resting face. The rest are other expressions.
NORMAL_FACE_WEIGHT = 25


def next_face(current: Optional[str], roll: int, names: tuple[str, ...] = ()) -> str:
    """Pick the next OLED expression. ``roll`` is 0–99, or any integer.

    A roll in the first 25 percent of 100 returns the neutral face. Otherwise
    the result is a different expression from ``names``.
    """
    if names:
        catalog = names
    else:
        from .faces import FACE_NAMES

        catalog = FACE_NAMES
    if roll % 100 < NORMAL_FACE_WEIGHT:
        return "neutral"
    others = [name for name in catalog if name not in {current, "neutral"}]
    if not others:
        return "neutral"
    return others[roll % len(others)]


def choose_mood(*, battery: Optional[int], on_charger: bool, pick: int) -> str:
    """Pick a mood. ``pick`` is any integer; tests pass it instead of a RNG."""
    if battery is not None and battery < 18:
        return "low_battery"
    if on_charger:
        return ("sleepy", "curious", "cheerful")[pick % 3]
    return ("cheerful", "curious", "playful")[pick % 3]


def plan_beat(
    *,
    mood: str,
    clips: list[str],
    last_clip: Optional[str],
    allow_phrase: bool,
) -> dict:
    """One personality beat: animated face, optional in-place clip, backpack colour."""
    spec = MOODS[mood]
    available = set(clips)
    chosen = None
    for name in spec["clips"]:
        if name in available and name != last_clip:
            chosen = name
            break
    if chosen is None:
        for name in spec["clips"]:
            if name in available:
                chosen = name
                break
    phrase = spec.get("phrase") if allow_phrase else None
    return {
        "mood": mood,
        "face": spec["face"],
        "clip": chosen,
        "backpack": list(spec["color"]),
        "phrase_id": phrase,
    }
