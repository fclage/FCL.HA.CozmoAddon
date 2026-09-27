"""Constants for the Cozmo Home Assistant integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "ha_cozmo"
DEFAULT_NAME = "Cozmo"
DEFAULT_URL = "http://127.0.0.1:8790"
DEFAULT_ADDON_URL = "http://172.30.32.1:8790"
DEFAULT_SSID = "Cozmo_"

CONF_SSID = "ssid"
CONF_TOKEN = "token"
CONF_WIFI_DEVICE = "wifi_device"
CONF_FROM_ADDON = "from_addon"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

# pycozmo.expressions class names (lowercase). Keep in sync with companion/faces.py.
FACE_OPTIONS = [
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
]

# Official clip names that exist after `pycozmo_resources.py download`.
FALLBACK_ANIMS = [
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
]

ATTR_LEFT = "left_speed"
ATTR_RIGHT = "right_speed"
ATTR_DURATION = "duration"
ATTR_NAME = "name"
ATTR_EXPRESSION = "expression"
ATTR_ANGLE = "angle"
ATTR_HEIGHT = "height"
ATTR_MEDIA = "media_url"
ATTR_TEXT = "text"
ATTR_PHRASE = "phrase_id"

SERVICE_DRIVE = "drive"
SERVICE_PLAY_ANIM = "play_anim"
SERVICE_SET_FACE = "set_face"
SERVICE_STOP = "stop"
SERVICE_PLAY_AUDIO = "play_audio"
SERVICE_SET_HEAD = "set_head"
SERVICE_SET_LIFT = "set_lift"
SERVICE_WIFI_JOIN = "wifi_join"
SERVICE_SPEAK = "speak"
SERVICE_PLAY = "play"
