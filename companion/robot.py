"""Thread-safe pycozmo session used by the HTTP companion."""

from __future__ import annotations

import io
import logging
import queue
import subprocess
import threading
import time
from typing import Any, Callable, Optional

from .audio_util import AudioError, to_cozmo_wav
from .cubes import blank_cube, cube_slot
from .faces import FACE_NAMES, KNOWN_CLIPS, interpolate_to, render_expression
from .keepalive import link_action

log = logging.getLogger("ha_cozmo.robot")

# Typical Cozmo Li-ion window used by the original SDK gauge.
BATT_EMPTY_V = 3.55
BATT_FULL_V = 4.05
MAX_WHEEL_MMPS = 200.0
MIN_HEAD_DEG = -25.0
MAX_HEAD_DEG = 44.5
MIN_LIFT_MM = 32.0
MAX_LIFT_MM = 92.0


def clamp_nudge(current: float, delta: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(current) + float(delta)))


def _battery_percent(voltage: float) -> Optional[int]:
    if voltage <= 0:
        return None
    pct = (voltage - BATT_EMPTY_V) / (BATT_FULL_V - BATT_EMPTY_V) * 100.0
    return int(max(0, min(100, round(pct))))


class RobotSession:
    """Owns a pycozmo.Client (or a dry-run stand-in) and a command worker."""

    def __init__(self, settings: dict) -> None:
        self.settings = settings
        self._lock = threading.RLock()
        self._cmd_q: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._cli = None
        self._connected = False
        self._last_error: Optional[str] = None
        self._last_image = None
        self._last_image_ts: Optional[float] = None
        self._last_state_ts: Optional[float] = None
        self._auto_reconnect = True
        self._face = "neutral"
        self._volume = 75
        self._backpack_rgb = (0, 0, 0)
        self._backpack_on = False
        self._head_light = False
        self._personality = bool(settings.get("personality", True))
        self._auto = bool(settings.get("auto", False))
        self._auto_sleep = bool(settings.get("auto_sleep", False))
        self._sleeping = False
        self._powering_off = False
        self._raise_on_connect = False
        self._last_user = time.time()
        self._last_auto_act = 0.0
        self._mood: Optional[str] = None
        self._last_clip: Optional[str] = None
        self._said_hello = False
        self._last_phrase_ts = 0.0
        self._suppress_until = 0.0
        self._last_link_action = time.time()
        self._button_pressed = False
        self._charging = False
        self._on_charger = False
        self._cliff = False
        self._last_anim: Optional[str] = None
        self._anim_names: list[str] = []
        self._anim_groups: list[str] = []
        self._cubes = {slot: blank_cube() for slot in (1, 2, 3)}
        self._worker = threading.Thread(target=self._worker_loop, name="cozmo-worker", daemon=True)
        self._reconnector = threading.Thread(
            target=self._reconnect_loop, name="cozmo-reconnect", daemon=True
        )
        self._personality_thread = threading.Thread(
            target=self._personality_loop, name="cozmo-idle", daemon=True
        )
        self._auto_thread = threading.Thread(
            target=self._auto_loop, name="cozmo-auto", daemon=True
        )
        self._face_thread = threading.Thread(
            target=self._face_loop, name="cozmo-face", daemon=True
        )

    def start(self) -> None:
        self._worker.start()
        self._reconnector.start()
        self._personality_thread.start()
        self._auto_thread.start()
        self._face_thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.submit("disconnect")

    def submit(self, cmd: str, **kwargs: Any) -> None:
        self._cmd_q.put((cmd, kwargs))

    def status(self) -> dict:
        with self._lock:
            cli = self._cli
            voltage = float(getattr(cli, "battery_voltage", 0.0) or 0.0) if cli else 0.0
            head = getattr(cli, "head_angle", None)
            lift = getattr(cli, "lift_position", None)
            orientation = getattr(cli, "robot_orientation", None)
            serial = getattr(cli, "serial_number", None)
            fw = getattr(cli, "robot_fw_sig", None) or {}
            available = dict(getattr(cli, "available_objects", {}) or {})
            connected = dict(getattr(cli, "connected_objects", {}) or {})
            flags = int(getattr(cli, "robot_status", 0) or 0) if cli else 0
            return {
                "ok": True,
                "dry_run": bool(self.settings.get("dry_run")),
                "robot_connected": self._connected,
                "last_error": self._last_error,
                "ssid": self.settings.get("ssid") or None,
                "wifi_iface": self.settings.get("wifi_iface") or None,
                "battery_voltage": round(voltage, 3) if voltage else None,
                "battery_percent": _battery_percent(voltage),
                "charging": self._charging or bool(flags & 0x2000),
                "on_charger": self._on_charger or bool(flags & 0x1000),
                "cliff": self._cliff or bool(flags & 0x4000),
                "picked_up": bool(getattr(cli, "robot_picked_up", False)) if cli else False,
                "moving": bool(getattr(cli, "robot_moving", False)) if cli else False,
                "animating": bool(flags & 0x40),
                "orientation": getattr(orientation, "name", None) if orientation else None,
                "head_angle": round(head.degrees, 1) if head is not None else None,
                "lift_height_mm": round(lift.height.mm, 1) if lift is not None else None,
                "volume": self._volume,
                "face": self._face,
                "last_anim": self._last_anim,
                "backpack": {"rgb": list(self._backpack_rgb), "on": self._backpack_on},
                "head_light": self._head_light,
                "personality": self._personality,
                "auto": self._auto,
                "auto_sleep": self._auto_sleep,
                "sleeping": self._sleeping,
                "mood": self._mood,
                "serial": f"{serial:08x}" if isinstance(serial, int) else serial,
                "firmware": str(fw.get("version")) if fw else None,
                "body_hw_version": getattr(cli, "body_hw_version", None) if cli else None,
                "cubes_available": len(available),
                "cubes_connected": len(connected),
                "cubes": [
                    {
                        "factory_id": f"{fid:08x}" if isinstance(fid, int) else str(fid),
                        "type": str(getattr(obj, "object_type", "")),
                    }
                    for fid, obj in available.items()
                ],
                "cube_slots": [self._cube_public(slot) for slot in (1, 2, 3)],
                "button_pressed": self._button_pressed,
                "has_image": self._last_image is not None,
                "image_age": (time.time() - self._last_image_ts) if self._last_image_ts else None,
                "last_state_age_s": (time.time() - self._last_state_ts) if self._last_state_ts else None,
                "auto_reconnect": self._auto_reconnect,
                "anims_loaded": bool(self._anim_names),
                "anim_count": len(self._anim_names),
                "faces": list(FACE_NAMES),
            }

    def anims(self) -> dict:
        with self._lock:
            clips = list(self._anim_names) or [n for n in KNOWN_CLIPS]
            groups = list(self._anim_groups)
        options = groups or [n for n in KNOWN_CLIPS if n in set(clips) or not self._anim_names]
        return {"clips": clips, "groups": groups, "select": options}

    def camera_jpeg(self) -> Optional[bytes]:
        with self._lock:
            image = self._last_image
        if image is None:
            return None
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=80)
        return buf.getvalue()

    # --- worker --------------------------------------------------------

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                cmd, kwargs = self._cmd_q.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                self._dispatch(cmd, kwargs)
            except Exception as exc:  # noqa: BLE001 — keep the worker alive
                log.exception("command %s failed", cmd)
                with self._lock:
                    self._last_error = f"{cmd}: {exc}"

    def _robot_reachable(self) -> bool:
        """ICMP the robot on the Cozmo interface. A miss means the AP join dropped."""
        host = self.settings.get("robot_host") or "172.31.1.1"
        iface = (self.settings.get("wifi_iface") or "").strip()
        cmd = ["ping", "-c", "1", "-W", "1"]
        if iface:
            cmd.extend(["-I", iface])
        cmd.append(host)
        try:
            proc = subprocess.run(cmd, check=False, capture_output=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return proc.returncode == 0

    def _note_link_action(self) -> None:
        with self._lock:
            self._last_link_action = time.time()

    def _reconnect_loop(self) -> None:
        """Rejoin Wi-Fi or reopen UDP when Cozmo goes quiet (COZMO 01)."""
        while not self._stop.is_set():
            time.sleep(3.0)
            if self._stop.is_set() or self.settings.get("dry_run"):
                continue
            with self._lock:
                connected = self._connected
                last_state = self._last_state_ts
                auto = self._auto_reconnect
                sleeping = self._sleeping
                since = time.time() - self._last_link_action
            if not auto or sleeping:
                continue
            age = (time.time() - last_state) if last_state else None
            action = link_action(
                wifi_ok=self._robot_reachable(),
                connected=connected,
                state_age_s=age,
                since_action_s=since,
            )
            if action is None:
                continue
            self._note_link_action()
            if action == "rejoin":
                log.warning("Cozmo Wi-Fi is down — rejoining the access point")
                self.submit("wifi_join")
                self.submit("connect")
            elif action == "reconnect":
                log.warning("Cozmo link stale — reopening the session")
                with self._lock:
                    self._connected = False
                    self._last_error = "link lost: no robot state"
                self.submit("disconnect")
                self.submit("connect")
            else:
                self.submit("connect")

    def _personality_loop(self) -> None:
        """Shift the OLED on an uneven pause. Not pycozmo.brain (that is WIP)."""
        import random

        from .personality import face_gap

        while not self._stop.is_set():
            pause = face_gap(random.uniform(-1.0, 1.0))
            deadline = time.time() + pause
            while time.time() < deadline and not self._stop.is_set():
                time.sleep(min(1.0, deadline - time.time()))
            with self._lock:
                enabled = self._personality and self._connected and not self.settings.get("dry_run")
                held = time.time() < self._suppress_until
                moving = bool(getattr(self._cli, "robot_moving", False)) if self._cli else False
                flags = int(getattr(self._cli, "robot_status", 0) or 0) if self._cli else 0
                current = self._face
            if not enabled or held or moving or bool(flags & 0x40) or self._powering_off:
                continue
            expression = self._living_face(current)
            with self._lock:
                self._mood = expression
            self.submit("face", expression=expression, quiet=True)

    def _auto_loop(self) -> None:
        """After 30s with no taps, play. Faces keep going even when this is off."""
        from .auto import auto_ready, pick_auto_action, sleep_ready

        while not self._stop.is_set():
            time.sleep(3)
            if self._stop.is_set():
                return
            with self._lock:
                enabled = self._auto and self._connected and not self.settings.get("dry_run")
                idle = time.time() - self._last_user
                since = time.time() - self._last_auto_act
                docked = self._on_charger
                cliff = self._cliff
                cli = self._cli
            busy = False
            if cli is not None:
                flags = int(getattr(cli, "robot_status", 0) or 0)
                busy = bool(getattr(cli, "robot_moving", False)) or bool(flags & 0x40)
                busy = busy or bool(getattr(getattr(cli, "anim_controller", None), "playing_animation", False))
            with self._lock:
                want_sleep = sleep_ready(
                    enabled=self._auto_sleep,
                    idle_s=idle,
                    already=self._sleeping,
                ) and self._connected
            if want_sleep:
                self.submit("power_off")
                continue
            if not auto_ready(enabled=enabled, idle_s=idle, since_action_s=since, busy=busy):
                continue
            action = pick_auto_action(docked=docked, cliff=cliff, pick=int(time.time()))
            with self._lock:
                self._last_auto_act = time.time()
            self.submit("auto_step", action=action)

    def _dispatch(self, cmd: str, kwargs: dict) -> None:
        handlers: dict[str, Callable] = {
            "connect": self._do_connect,
            "disconnect": self._do_disconnect,
            "drive": self._do_drive,
            "stop": self._do_stop,
            "face": self._do_face,
            "anim": self._do_anim,
            "anim_group": self._do_anim_group,
            "cancel_anim": self._do_cancel_anim,
            "head": self._do_head,
            "lift": self._do_lift,
            "nudge_head": self._do_nudge_head,
            "nudge_lift": self._do_nudge_lift,
            "hold_face": self._do_hold_face,
            "volume": self._do_volume,
            "backpack": self._do_backpack,
            "backpack_off": self._do_backpack_off,
            "head_light": self._do_head_light,
            "personality": self._do_personality,
            "auto": self._do_auto,
            "auto_sleep": self._do_auto_sleep,
            "auto_step": self._do_auto_step,
            "power_off": self._do_power_off,
            "wake": self._do_wake,
            "audio": self._do_audio,
            "idle_blink": self._do_idle_blink,
            "idle": self._do_idle,
            "speak": self._do_speak,
            "play_command": self._do_play_command,
            "wifi_join": self._do_wifi_join,
            "cubes_connect": self._do_cubes_connect,
            "cube_led": self._do_cube_led,
        }
        fn = handlers.get(cmd)
        if fn is None:
            raise ValueError(f"unknown command {cmd}")
        quiet = bool(kwargs.pop("quiet", False))
        if not quiet and cmd not in {
            "connect",
            "disconnect",
            "idle",
            "idle_blink",
            "personality",
            "auto",
            "auto_step",
            "power_off",
            "wifi_join",
            "hold_face",
            "cubes_connect",
            "cube_led",
        }:
            with self._lock:
                was_sleeping = self._sleeping
                self._sleeping = False
                self._last_user = time.time()
                self._suppress_until = time.time() + 30
            if was_sleeping and cmd != "wake":
                self.submit("wake")
        fn(**kwargs)

    def _require_cli(self):
        if self.settings.get("dry_run"):
            return None
        if not self._cli or not self._connected:
            raise RuntimeError("Cozmo is not connected")
        return self._cli

    def _do_connect(self) -> None:
        if self.settings.get("dry_run"):
            with self._lock:
                self._connected = True
                self._last_error = None
                self._placeholder_image()
            log.info("dry-run: pretending Cozmo is connected")
            return
        self._note_link_action()
        self._do_disconnect()
        import pycozmo

        host = self.settings.get("robot_host") or "172.31.1.1"
        port = int(self.settings.get("robot_port") or 5551)
        log.info("connecting to Cozmo at %s:%s", host, port)
        cli = pycozmo.Client(
            robot_addr=(host, port),
            enable_animations=True,
            enable_procedural_face=False,
        )
        try:
            cli.start()
            cli.connect()
            cli.wait_for_robot(timeout=10.0)
        except Exception:
            try:
                cli.disconnect()
            except Exception:  # noqa: BLE001
                pass
            try:
                cli.stop()
            except Exception:  # noqa: BLE001
                pass
            raise
        cli.add_handler(pycozmo.event.EvtNewRawCameraImage, self._on_image)
        cli.add_handler(pycozmo.event.EvtRobotStateUpdated, self._on_state)
        cli.add_handler(pycozmo.protocol_encoder.ButtonPressed, self._on_button)
        cli.add_handler(pycozmo.event.EvtRobotChargingChange, self._on_charging)
        cli.add_handler(pycozmo.event.EvtCliffDetectedChange, self._on_cliff)
        cli.add_handler(pycozmo.event.EvtAnimationCompleted, self._on_anim_done)
        cli.add_handler(pycozmo.protocol_encoder.ObjectAvailable, self._on_cube_seen)
        cli.add_handler(pycozmo.protocol_encoder.ObjectConnectionState, self._on_cube_link)
        cli.add_handler(pycozmo.protocol_encoder.ObjectPowerLevel, self._on_cube_power)
        cli.add_handler(pycozmo.protocol_encoder.ObjectTapped, self._on_cube_tap)
        try:
            cli.load_anims()
            names = sorted(cli.get_anim_names() or [])
            groups = sorted((cli.animation_groups or {}).keys())
        except Exception as exc:  # noqa: BLE001
            log.warning("animation assets not loaded: %s", exc)
            names, groups = [], []
        cli.enable_camera(enable=True, color=bool(self.settings.get("camera_color", True)))
        cli.set_volume(int(self._volume / 100 * 65535))
        import pycozmo.robot as pycozmo_robot

        docked = bool(int(getattr(cli, "robot_status", 0) or 0) & pycozmo_robot.RobotStatusFlag.IS_ON_CHARGER)
        if docked:
            try:
                cli.stop_all_motors()
            except Exception:  # noqa: BLE001
                pass
            log.info("Cozmo is on the charger — staying put")
        else:
            try:
                mid = (
                    pycozmo.robot.MAX_HEAD_ANGLE.radians - pycozmo.robot.MIN_HEAD_ANGLE.radians
                ) / 2.0
                cli.set_head_angle(mid)
            except Exception:  # noqa: BLE001
                pass
        from .personality import should_greet

        with self._lock:
            self._cli = cli
            self._connected = True
            self._last_error = None
            self._last_state_ts = time.time()
            self._anim_names = names
            self._anim_groups = groups
            if docked:
                self._on_charger = True
            greet = should_greet(
                personality=self._personality,
                said_hello=self._said_hello,
                docked=docked,
            )
            if greet or docked:
                self._said_hello = True
        log.info("Cozmo connected (%s clips)", len(names))
        self._paint_face()
        self._note_link_action()
        self.submit("cubes_connect")
        if self._raise_on_connect:
            self._raise_on_connect = False
            self._raise_from_sleep()
        # NamedFaceInitialGreeting drives forward off the contacts.
        # Speak only, and only when he is already off the charger.
        if greet:
            self.submit("speak", phrase_id="im_cozmo")

    def _do_disconnect(self) -> None:
        cli = self._cli
        self._cli = None
        self._connected = False
        if cli is None:
            return
        try:
            cli.disconnect()
        except Exception:  # noqa: BLE001
            pass
        try:
            cli.stop()
        except Exception:  # noqa: BLE001
            pass

    def _do_drive(self, left: float = 0, right: float = 0, duration: float = 0.5) -> None:
        left = max(-MAX_WHEEL_MMPS, min(MAX_WHEEL_MMPS, float(left)))
        right = max(-MAX_WHEEL_MMPS, min(MAX_WHEEL_MMPS, float(right)))
        duration = max(0.0, min(10.0, float(duration)))
        cli = self._require_cli()
        if cli is None:
            return
        cli.drive_wheels(lwheel_speed=left, rwheel_speed=right, duration=duration)

    def _do_stop(self) -> None:
        cli = self._require_cli()
        if cli is None:
            return
        cli.stop_all_motors()
        try:
            cli.cancel_anim()
        except Exception:  # noqa: BLE001
            pass

    def _do_face(self, expression: str = "neutral") -> None:
        key = expression.strip().lower()
        if key not in FACE_NAMES:
            raise ValueError(f"unknown face {expression!r}")
        cli = self._require_cli()
        with self._lock:
            previous = self._face
            self._face = key
        if cli is None:
            return
        cli.enable_procedural_face(False)
        interpolate_to(cli, key, previous)

    def _do_anim(self, name: str = "") -> None:
        if not name:
            raise ValueError("animation name is required")
        cli = self._require_cli()
        with self._lock:
            self._last_anim = name
            self._last_clip = name
        if cli is None:
            return
        if self._docked(cli):
            log.info("not playing %s — Cozmo is on the charger", name)
            return
        if not cli.anim_names:
            raise RuntimeError(
                "Animations not loaded. Run `pycozmo_resources.py download` on the companion host."
            )
        cli.play_anim(name)

    def _do_anim_group(self, name: str = "", force: bool = False) -> None:
        if not name:
            raise ValueError("animation group is required")
        cli = self._require_cli()
        with self._lock:
            self._last_anim = name
        if cli is None:
            return
        if self._docked(cli) and not force:
            log.info("not playing %s — Cozmo is on the charger", name)
            return
        if name in (cli.animation_groups or {}):
            cli.play_anim_group(name)
            return
        if name in (cli.anim_names or set()):
            cli.play_anim(name)
            return
        raise ValueError(f"unknown animation or group {name!r}")

    def _do_cancel_anim(self) -> None:
        cli = self._require_cli()
        if cli is None:
            return
        cli.cancel_anim()

    def _do_nudge_head(self, delta: float = 8.0) -> None:
        cli = self._require_cli()
        if cli is None:
            return
        current = getattr(cli, "head_angle", None)
        degrees = current.degrees if current is not None else 0.0
        self._do_head(clamp_nudge(degrees, delta, MIN_HEAD_DEG, MAX_HEAD_DEG))

    def _do_nudge_lift(self, delta: float = 12.0) -> None:
        cli = self._require_cli()
        if cli is None:
            return
        lift = getattr(cli, "lift_position", None)
        height = lift.height.mm if lift is not None else MIN_LIFT_MM
        self._do_lift(clamp_nudge(height, delta, MIN_LIFT_MM, MAX_LIFT_MM))

    def _do_hold_face(self) -> None:
        self._paint_face()

    def _face_loop(self) -> None:
        """Cozmo blanks the OLED about 30s after the last image, and an animation end clears it."""
        while not self._stop.is_set():
            # Personality already moves the face. A fast redraw would pin the
            # last interpolated frame. Refresh slowly only as a blank-screen guard.
            time.sleep(4 if self._personality else 1.5)
            if self._stop.is_set() or self._powering_off:
                return
            if self._personality:
                continue
            self._paint_face()

    def _living_face(self, current: Optional[str]) -> str:
        from .personality import next_face

        return next_face(current, int(time.time() * 1000) % 100)

    def _on_anim_done(self, _cli) -> None:
        if self._powering_off:
            return
        # Do not leave the clip's last frame on the screen.
        if self._personality:
            self.submit("face", expression=self._living_face(self._face), quiet=True)
            return
        self._paint_face()

    def _paint_face(self) -> None:
        with self._lock:
            cli = self._cli
            connected = self._connected
            expression = self._face or "neutral"
            dry = bool(self.settings.get("dry_run"))
        if dry or not connected or cli is None or self._powering_off:
            return
        if getattr(getattr(cli, "anim_controller", None), "playing_animation", False):
            return
        try:
            cli.enable_procedural_face(False)
            cli.display_image(render_expression(expression))
        except Exception as exc:  # noqa: BLE001 — keep the pump alive
            log.debug("face refresh skipped: %s", exc)

    def _do_head(self, angle: float = 0.0) -> None:
        angle = max(MIN_HEAD_DEG, min(MAX_HEAD_DEG, float(angle)))
        cli = self._require_cli()
        if cli is None:
            return
        import math

        cli.set_head_angle(math.radians(angle))

    def _do_lift(self, height: float = MIN_LIFT_MM) -> None:
        height = max(MIN_LIFT_MM, min(MAX_LIFT_MM, float(height)))
        cli = self._require_cli()
        if cli is None:
            return
        cli.set_lift_height(height)

    def _do_volume(self, level: int = 75) -> None:
        level = int(max(0, min(100, level)))
        with self._lock:
            self._volume = level
        cli = self._require_cli()
        if cli is None:
            return
        cli.set_volume(int(level / 100 * 65535))

    def _do_backpack(self, rgb: Optional[list] = None, brightness: int = 255) -> None:
        rgb = list(rgb or [255, 255, 255])
        while len(rgb) < 3:
            rgb.append(0)
        brightness = int(max(0, min(255, brightness)))
        scaled = tuple(int(c * brightness / 255) for c in rgb[:3])
        with self._lock:
            self._backpack_rgb = tuple(int(c) for c in rgb[:3])
            self._backpack_on = brightness > 0 and any(scaled)
        cli = self._require_cli()
        if cli is None:
            return
        import pycozmo

        color = pycozmo.lights.Color(rgb=scaled)
        light = pycozmo.protocol_encoder.LightState(
            on_color=color.to_int16(), off_color=color.to_int16()
        )
        if self._backpack_on:
            cli.set_all_backpack_lights(light)
        else:
            cli.set_backpack_lights_off()

    def _do_backpack_off(self) -> None:
        with self._lock:
            self._backpack_on = False
        cli = self._require_cli()
        if cli is None:
            return
        cli.set_backpack_lights_off()

    def _do_head_light(self, on: bool = False) -> None:
        with self._lock:
            self._head_light = bool(on)
        cli = self._require_cli()
        if cli is None:
            return
        cli.set_head_light(bool(on))

    def _do_auto(self, enabled: bool = False) -> None:
        with self._lock:
            self._auto = bool(enabled)
            if self._auto:
                self._last_user = time.time()
        log.info("auto play %s", "on" if self._auto else "off")

    def _do_auto_sleep(self, enabled: bool = False) -> None:
        with self._lock:
            self._auto_sleep = bool(enabled)
            if self._auto_sleep:
                self._last_user = time.time()
                self._sleeping = False
        log.info("auto-sleep %s", "on" if self._auto_sleep else "off")

    def _play_clip_forced(self, cli, name: str, timeout: float = 12.0) -> None:
        """Play a clip even on the charger, and wait until it finishes."""
        import pycozmo

        done = threading.Event()

        def _finished(_cli) -> None:
            done.set()

        cli.add_handler(pycozmo.event.EvtAnimationCompleted, _finished)
        try:
            cli.play_anim(name)
            done.wait(timeout)
        finally:
            try:
                cli.del_handler(pycozmo.event.EvtAnimationCompleted, _finished)
            except Exception:  # noqa: BLE001
                pass

    def _do_power_off(self) -> None:
        with self._lock:
            if self._sleeping or self._powering_off:
                return
            self._powering_off = True
            self._sleeping = True
        cli = self._cli
        log.info("powering off after the tired animation")
        if cli is not None:
            try:
                self._play_clip_forced(cli, "anim_gotosleep_getin_01")
            except Exception as exc:  # noqa: BLE001
                log.info("tired animation skipped: %s", exc)
                try:
                    self._do_face("tiredness")
                except Exception:  # noqa: BLE001
                    pass
            try:
                cli.stop_all_motors()
            except Exception:  # noqa: BLE001
                pass
            try:
                import pycozmo

                cli.conn.send(pycozmo.protocol_encoder.ShutdownRobot())
            except Exception as exc:  # noqa: BLE001
                log.warning("power off failed: %s", exc)
        with self._lock:
            self._connected = False
            self._cli = None
            self._powering_off = False

    def _raise_from_sleep(self) -> None:
        """Open the eyes and lift the head. Wheels stay still, including on the charger."""
        self._do_face("neutral")
        self._do_head(12)

    def _do_wake(self) -> None:
        with self._lock:
            self._sleeping = False
            self._powering_off = False
            self._last_user = time.time()
            connected = self._connected
        if not connected:
            self._raise_on_connect = True
            self.submit("wifi_join")
            self.submit("connect")
            return
        self._raise_from_sleep()

    def _do_auto_step(self, action: str = "happy") -> None:
        """One idle beat. Does not count as a user tap."""
        if action in {"turn_left", "turn_right", "forward", "back"}:
            if self._docked():
                action = "happy"
            elif action == "forward" and self._cliff:
                action = "back"
        if action == "turn_left":
            self._do_drive(-45, 45, 0.45)
        elif action == "turn_right":
            self._do_drive(45, -45, 0.45)
        elif action == "forward":
            self._do_drive(50, 50, 0.35)
        elif action == "back":
            self._do_drive(-40, -40, 0.3)
        elif action == "head_up":
            self._do_nudge_head(6)
        elif action == "head_down":
            self._do_nudge_head(-6)
        elif action == "lift_up":
            self._do_nudge_lift(8)
        elif action == "lift_down":
            self._do_nudge_lift(-8)
        elif action == "curious":
            self._do_face("confusion")
        elif action == "excited":
            self._do_face("excitement")
        else:
            self._do_face("happiness")
        with self._lock:
            self._mood = action

    def _do_personality(self, enabled: bool = False) -> None:
        with self._lock:
            self._personality = bool(enabled)

    def _cube_public(self, slot: int) -> dict:
        row = self._cubes[slot]
        return {
            "slot": slot,
            "factory_id": row["factory_id"],
            "connected": row["connected"],
            "battery": row["battery"],
            "missed_packets": row["missed_packets"],
            "rssi": row["rssi"],
            "last_tap": row["last_tap"] or None,
            "taps": row["taps"],
            "leds": [list(color) if color else None for color in row["leds"]],
            "seen": row["factory_id"] is not None,
        }

    def _slot_for_object(self, object_id: int) -> Optional[int]:
        with self._lock:
            for slot, row in self._cubes.items():
                if row["object_id"] == object_id:
                    return slot
        return None

    def _remember_cube(self, slot: int, factory_id: int, rssi) -> None:
        with self._lock:
            row = self._cubes[slot]
            row["factory_id"] = f"{int(factory_id):08x}"
            if rssi is not None:
                row["rssi"] = int(rssi)

    def _do_cubes_connect(self) -> None:
        cli = self._require_cli()
        if cli is None:
            return
        import pycozmo

        try:
            cli.conn.send(pycozmo.protocol_encoder.SetAccessoryDiscovery(enable=True))
        except Exception as exc:  # noqa: BLE001
            log.debug("cube discovery: %s", exc)
        seen = list(getattr(cli, "available_objects", {}).items())
        pending = []
        for factory_id, obj in seen:
            slot = cube_slot(getattr(obj, "object_type", None))
            if slot is None:
                continue
            self._remember_cube(slot, int(factory_id), None)
            with self._lock:
                already = bool(self._cubes[slot]["connected"])
            if already:
                continue
            pending.append((slot, int(factory_id)))
        # The robot answers a second ObjectConnect by disconnecting whoever
        # is already on radio slot 1. Link one cube, and do not send another
        # connect while that slot is taken.
        with self._lock:
            held = [s for s, row in self._cubes.items() if row["connected"]]
        if held:
            log.info("cube %s is holding the radio slot; not connecting another", held[0])
            return
        if not pending:
            log.info("no unlinked cubes in range")
            return
        slot, factory_id = pending[0]
        try:
            cli.conn.send(
                pycozmo.protocol_encoder.ObjectConnect(factory_id=factory_id, connect=True)
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("cube %s connect failed: %s", slot, exc)
            return
        deadline = time.time() + 3.0
        while time.time() < deadline and not self._stop.is_set():
            with self._lock:
                linked = bool(self._cubes[slot]["connected"])
            if linked:
                break
            time.sleep(0.1)
        with self._lock:
            linked = bool(self._cubes[slot]["connected"])
        log.info("cube %s link attempt %s", slot, "ok" if linked else "timed out")

    def _do_cube_led(self, slot: int = 1, index: int = 0, rgb=None, on: bool = True) -> None:
        slot = int(slot)
        index = int(index)
        if slot not in (1, 2, 3) or index not in (0, 1, 2, 3):
            raise ValueError("cube LED is slot 1-3 and index 0-3")
        cli = self._require_cli()
        if cli is None:
            return
        with self._lock:
            row = self._cubes[slot]
            object_id = row["object_id"]
            if on and rgb:
                row["leds"][index] = [int(rgb[0]), int(rgb[1]), int(rgb[2])]
            else:
                row["leds"][index] = None
            colors = list(row["leds"])
        if object_id is None:
            raise RuntimeError(f"cube {slot} is not linked")
        import pycozmo

        def one(color):
            if not color:
                value = 0
            else:
                value = pycozmo.lights.Color(rgb=tuple(int(c) for c in color)).to_int16()
            return pycozmo.protocol_encoder.LightState(on_color=value, off_color=value)

        states = tuple(one(color) for color in colors)
        cli.conn.send(pycozmo.protocol_encoder.CubeId(object_id=int(object_id), rotation_period_frames=0))
        cli.conn.send(pycozmo.protocol_encoder.CubeLights(states=states))

    def _on_cube_seen(self, cli, pkt) -> None:
        slot = cube_slot(getattr(pkt, "object_type", None))
        if slot is None:
            return
        self._remember_cube(slot, int(pkt.factory_id), getattr(pkt, "rssi", None))
        del cli

    def _on_cube_link(self, _cli, pkt) -> None:
        slot = cube_slot(getattr(pkt, "object_type", None))
        if slot is None:
            slot = self._slot_for_factory(pkt.factory_id)
        if slot is None:
            return
        with self._lock:
            row = self._cubes[slot]
            row["factory_id"] = f"{int(pkt.factory_id):08x}"
            row["connected"] = bool(pkt.connected)
            row["object_id"] = int(pkt.object_id) if pkt.connected else None
        log.info(
            "cube %s %s object_id=%s factory=%08x type=%s",
            slot,
            "linked" if pkt.connected else "unlinked",
            pkt.object_id,
            int(pkt.factory_id),
            pkt.object_type,
        )

    def _slot_for_factory(self, factory_id: int) -> Optional[int]:
        text = f"{int(factory_id):08x}"
        with self._lock:
            for slot, row in self._cubes.items():
                if row["factory_id"] == text:
                    return slot
        return None

    def _on_cube_power(self, _cli, pkt) -> None:
        slot = self._slot_for_object(int(pkt.object_id))
        if slot is None:
            return
        with self._lock:
            self._cubes[slot]["battery"] = int(pkt.battery_level)
            self._cubes[slot]["missed_packets"] = int(pkt.missed_packets)

    def _on_cube_tap(self, _cli, pkt) -> None:
        slot = self._slot_for_object(int(pkt.object_id))
        if slot is None:
            return
        with self._lock:
            self._cubes[slot]["last_tap"] = time.time()
            self._cubes[slot]["taps"] = int(getattr(pkt, "num_taps", 1) or 1)
        log.info("cube %s tapped (%s)", slot, getattr(pkt, "num_taps", 1))

    def _do_idle_blink(self) -> None:
        cli = self._require_cli()
        if cli is None:
            return
        with self._lock:
            current = self._face
        try:
            interpolate_to(cli, "asleep", current)
            time.sleep(0.15)
            interpolate_to(cli, current, "asleep")
        except Exception as exc:  # noqa: BLE001
            log.debug("idle blink skipped: %s", exc)

    def _do_audio(self, path: str = "") -> None:
        if not path:
            raise AudioError("audio path is required")
        wav = to_cozmo_wav(path, ffmpeg=self.settings.get("ffmpeg") or "ffmpeg")
        cli = self._require_cli()
        try:
            if cli is None:
                return
            try:
                from .audio_fix import play_wav_on_client

                play_wav_on_client(cli, str(wav))
            except Exception as exc:  # noqa: BLE001
                log.debug("audio_fix fallback to Client.play_audio: %s", exc)
                cli.play_audio(str(wav))
        finally:
            for victim in {str(wav), path}:
                if "cozmo-" in victim:
                    try:
                        import os

                        os.unlink(victim)
                    except OSError:
                        pass

    def _do_wifi_join(
        self,
        ssid: Optional[str] = None,
        password: Optional[str] = None,
        iface: Optional[str] = None,
    ) -> None:
        from .wifi import join_ap

        if iface:
            self.settings["wifi_iface"] = iface
        if ssid:
            self.settings["ssid"] = ssid
        if password is not None and password != "":
            self.settings["password"] = password
        self._note_link_action()
        ok, msg = join_ap(
            self.settings.get("wifi_iface") or "",
            ssid or self.settings.get("ssid") or "",
            password if password not in (None, "") else (self.settings.get("password") or ""),
        )
        with self._lock:
            self._last_error = None if ok else msg
        if not ok:
            raise RuntimeError(msg)

    # --- event handlers ------------------------------------------------

    def _do_speak(self, text: str = "", phrase_id: str = "") -> None:
        if phrase_id and not text:
            from .personality import phrase_by_id

            phrase = phrase_by_id(phrase_id)
            if not phrase:
                raise ValueError(f"unknown phrase {phrase_id!r}")
            text = phrase.text
        from .tts import synthesize

        wav = synthesize(text)
        self._do_audio(path=str(wav))

    def _do_play_command(self, name: str = "") -> None:
        from .personality import anim_by_id

        if name == "greet":
            # Deliberate button. This clip may drive off the charger.
            self._do_anim_group(name="NamedFaceInitialGreeting", force=True)
            return
        cmd = anim_by_id(name)
        if not cmd:
            raise ValueError(f"unknown command {name!r}")
        if cmd.group:
            self._do_anim_group(name=cmd.group)
            return
        if cmd.anim:
            self._do_anim(name=cmd.anim)
            return
        raise ValueError(f"command {name!r} has no group/anim")

    def _do_idle(self) -> None:
        from .personality import IDLE_ANIM_CLIPS, IDLE_ANIM_GROUPS

        groups = [g for g in IDLE_ANIM_GROUPS if g in self._anim_groups]
        if groups:
            self._do_anim_group(name=groups[0])
            return
        clips = [c for c in IDLE_ANIM_CLIPS if c in self._anim_names]
        if clips:
            self._do_anim(name=clips[0])
            return
        self._do_idle_blink()

    def _docked(self, cli=None) -> bool:
        cli = cli if cli is not None else self._cli
        flags = int(getattr(cli, "robot_status", 0) or 0) if cli is not None else 0
        with self._lock:
            remembered = self._on_charger
        try:
            import pycozmo.robot as pycozmo_robot

            mask = pycozmo_robot.RobotStatusFlag.IS_ON_CHARGER
        except Exception:  # noqa: BLE001
            mask = 0x1000
        return remembered or bool(flags & mask)

    def _on_state(self, cli) -> None:
        flags = int(getattr(cli, "robot_status", 0) or 0)
        try:
            import pycozmo.robot as pycozmo_robot

            on_charger = bool(flags & pycozmo_robot.RobotStatusFlag.IS_ON_CHARGER)
        except Exception:  # noqa: BLE001
            on_charger = bool(flags & 0x1000)
        with self._lock:
            self._last_state_ts = time.time()
            self._on_charger = on_charger

    def _on_image(self, _cli, image) -> None:
        with self._lock:
            self._last_image = image
            self._last_image_ts = time.time()

    def _on_button(self, _cli, pkt) -> None:
        with self._lock:
            self._button_pressed = bool(getattr(pkt, "pressed", False))

    def _on_charging(self, _cli, state: bool) -> None:
        with self._lock:
            self._charging = bool(state)
            if state:
                self._on_charger = True

    def _on_cliff(self, _cli, state: bool) -> None:
        with self._lock:
            self._cliff = bool(state)

    def _placeholder_image(self) -> None:
        try:
            from PIL import Image, ImageDraw

            im = Image.new("RGB", (320, 240), (30, 30, 36))
            draw = ImageDraw.Draw(im)
            draw.text((20, 100), "Cozmo dry-run", fill=(220, 220, 220))
            self._last_image = im
            self._last_image_ts = time.time()
        except Exception:  # noqa: BLE001
            self._last_image = None
