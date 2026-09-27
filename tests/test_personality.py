from companion.auto import auto_ready, pick_auto_action, sleep_ready
from companion.cubes import cube_slot
from companion.keepalive import link_action
from companion.personality import catalog, choose_mood, phrase_by_id, plan_beat, should_greet
from companion.robot import clamp_nudge


def test_catalog_has_phrases_and_anims() -> None:
    cat = catalog()
    assert cat["phrases"]
    assert cat["animations"]
    assert phrase_by_id("hello").text.startswith("Hello")
    assert phrase_by_id("missing") is None


def test_cube_slot_is_the_printed_number() -> None:
    assert cube_slot(1) == 1
    assert cube_slot(2) == 2
    assert cube_slot("ObjectType.Block_LIGHTCUBE3") == 3
    assert cube_slot("ObjectType.Charger_Basic") is None
    assert cube_slot(4) is None


def test_auto_sleep_ignores_the_charger_and_waits_five_minutes() -> None:
    assert sleep_ready(enabled=False, idle_s=600, already=False) is False
    assert sleep_ready(enabled=True, idle_s=299, already=False) is False
    assert sleep_ready(enabled=True, idle_s=300, already=False) is True
    assert sleep_ready(enabled=True, idle_s=600, already=True) is False


def test_auto_waits_for_idle_and_stays_put_on_the_charger() -> None:
    assert auto_ready(enabled=False, idle_s=60, since_action_s=20, busy=False) is False
    assert auto_ready(enabled=True, idle_s=10, since_action_s=20, busy=False) is False
    assert auto_ready(enabled=True, idle_s=31, since_action_s=9, busy=False) is True
    assert pick_auto_action(docked=True, cliff=False, pick=0) in {
        "happy",
        "curious",
        "excited",
        "head_up",
        "head_down",
        "lift_up",
        "lift_down",
    }
    assert pick_auto_action(docked=False, cliff=True, pick=2) != "forward"


def test_greeting_stays_off_the_charger() -> None:
    assert should_greet(personality=True, said_hello=False, docked=True) is False
    assert should_greet(personality=True, said_hello=False, docked=False) is True
    assert should_greet(personality=True, said_hello=True, docked=False) is False


def test_mood_follows_battery_and_charger() -> None:
    assert choose_mood(battery=10, on_charger=False, pick=0) == "low_battery"
    assert choose_mood(battery=80, on_charger=True, pick=0) == "sleepy"
    assert choose_mood(battery=80, on_charger=False, pick=1) == "curious"


def test_beat_stays_in_place_and_skips_the_last_clip() -> None:
    beat = plan_beat(
        mood="curious",
        clips=[
            "anim_hiking_lookaround_01",
            "anim_lookinplaceforfaces_keepalive_short",
        ],
        last_clip="anim_hiking_lookaround_01",
        allow_phrase=False,
    )
    assert beat["face"] == "confusion"
    assert beat["clip"] == "anim_lookinplaceforfaces_keepalive_short"
    quiet = plan_beat(
        mood="low_battery",
        clips=["anim_bored_01"],
        last_clip=None,
        allow_phrase=True,
    )
    assert quiet["phrase_id"] == "need_charge"
    silent = plan_beat(
        mood="low_battery",
        clips=["anim_bored_01"],
        last_clip=None,
        allow_phrase=False,
    )
    assert silent["phrase_id"] is None


def test_nudge_stays_inside_head_and_lift_limits() -> None:
    assert clamp_nudge(40, 8, -25, 44.5) == 44.5
    assert clamp_nudge(-20, -8, -25, 44.5) == -25
    assert clamp_nudge(32, -12, 32, 92) == 32
    assert clamp_nudge(60, 12, 32, 92) == 72


def test_link_action_waits_then_rejoins_or_reconnects() -> None:
    assert link_action(wifi_ok=False, connected=True, state_age_s=0.2, since_action_s=1) is None
    assert link_action(wifi_ok=False, connected=True, state_age_s=0.2, since_action_s=20) == "rejoin"
    assert link_action(wifi_ok=True, connected=True, state_age_s=5, since_action_s=20) == "reconnect"
    assert link_action(wifi_ok=True, connected=False, state_age_s=None, since_action_s=20) == "connect"
    assert link_action(wifi_ok=True, connected=True, state_age_s=0.4, since_action_s=20) is None
