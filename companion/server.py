"""Minimal stdlib HTTP API for the Home Assistant integration."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import personality
from .robot import RobotSession
from .wifi import list_unbound_wifi, list_wifi_devices, scan_cozmo_networks, wifi_status

STATIC_DIR = Path(__file__).resolve().parent / "static"

log = logging.getLogger("ha_cozmo.http")


def _json_bytes(payload: Any, status: int = 200) -> tuple[int, bytes, str]:
    return status, json.dumps(payload).encode("utf-8"), "application/json"


class CompanionHandler(BaseHTTPRequestHandler):
    server_version = "ha-cozmo-companion/0.1"
    robot: RobotSession
    token: str = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)

    def _unauthorized(self) -> None:
        self._send(*_json_bytes({"ok": False, "error": "unauthorized"}, 401))

    def _check_auth(self) -> bool:
        if not self.token:
            return True
        header = self.headers.get("Authorization", "")
        if header == f"Bearer {self.token}":
            return True
        if self.headers.get("X-Api-Key") == self.token:
            return True
        self._unauthorized()
        return False

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON object required")
        return data

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length > 0 else b""

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def _serve_static(self, path: str) -> bool:
        rel = path[len("/ui") :].lstrip("/") or "index.html"
        target = (STATIC_DIR / rel).resolve()
        if STATIC_DIR not in target.parents and target != STATIC_DIR:
            return False
        if not target.is_file():
            return False
        data = target.read_bytes()
        ctype = "text/html; charset=utf-8"
        if target.suffix == ".js":
            ctype = "text/javascript; charset=utf-8"
        elif target.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        self._send(200, data, ctype)
        return True

    def _stream_mjpeg(self) -> None:
        boundary = b"frame"
        self.send_response(200)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={boundary.decode()}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            while True:
                jpeg = self.robot.camera_jpeg()
                if jpeg:
                    header = (
                        b"--" + boundary + b"\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                    )
                    self.wfile.write(header + jpeg + b"\r\n")
                    self.wfile.flush()
                time.sleep(0.12)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        public = path in ("/", "/v1/health", "/v1/wifi/scan", "/v1/wifi/ifaces") or path.startswith("/ui")
        if not public and not self._check_auth():
            return
        try:
            if path.startswith("/ui"):
                if self._serve_static(path):
                    return
                self._send(*_json_bytes({"ok": False, "error": "not found"}, 404))
                return
            if path in ("/", "/v1/health"):
                payload = {
                    "ok": True,
                    "service": "ha-cozmo-companion",
                    "robot_connected": self.robot.status().get("robot_connected"),
                    "ui": "/ui/",
                }
                self._send(*_json_bytes(payload))
                return
            if path == "/v1/wifi/scan":
                iface = self.robot.settings.get("wifi_iface") or ""
                self._send(*_json_bytes({"networks": scan_cozmo_networks(iface), "iface": iface}))
                return
            if path == "/v1/wifi/ifaces":
                self._send(
                    *_json_bytes(
                        {
                            "wifi": list_wifi_devices(),
                            "unbound": list_unbound_wifi(),
                            "selected": self.robot.settings.get("wifi_iface") or "",
                        }
                    )
                )
                return
            if path == "/v1/status":
                status = self.robot.status()
                status["wifi"] = wifi_status(self.robot.settings.get("wifi_iface") or "")
                self._send(*_json_bytes(status))
                return
            if path == "/v1/anims":
                self._send(*_json_bytes(self.robot.anims()))
                return
            if path == "/v1/catalog":
                self._send(*_json_bytes(personality.catalog()))
                return
            if path == "/v1/faces":
                self._send(*_json_bytes({"faces": self.robot.status()["faces"]}))
                return
            if path == "/v1/camera/stream":
                self._stream_mjpeg()
                return
            if path in ("/v1/camera.jpg", "/v1/camera"):
                jpeg = self.robot.camera_jpeg()
                if jpeg is None:
                    self._send(*_json_bytes({"ok": False, "error": "no camera frame yet"}, 404))
                    return
                self._send(200, jpeg, "image/jpeg")
                return
            self._send(*_json_bytes({"ok": False, "error": "not found"}, 404))
        except Exception as exc:  # noqa: BLE001
            log.exception("GET %s", path)
            self._send(*_json_bytes({"ok": False, "error": str(exc)}, 500))

    def do_POST(self) -> None:  # noqa: N802
        if not self._check_auth():
            return
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if path == "/v1/command":
                body = self._read_json()
                cmd = body.pop("cmd", None) or body.pop("command", None)
                if not cmd:
                    self._send(*_json_bytes({"ok": False, "error": "cmd is required"}, 400))
                    return
                self.robot.submit(str(cmd), **body)
                self._send(*_json_bytes({"ok": True, "cmd": cmd}))
                return
            if path == "/v1/audio":
                data = self._read_body()
                if not data:
                    self._send(*_json_bytes({"ok": False, "error": "empty body"}, 400))
                    return
                suffix = ".wav"
                ctype = (self.headers.get("Content-Type") or "").lower()
                if "mpeg" in ctype or "mp3" in ctype:
                    suffix = ".mp3"
                elif "ogg" in ctype:
                    suffix = ".ogg"
                fd, tmp = tempfile.mkstemp(prefix="cozmo-in-", suffix=suffix)
                os.close(fd)
                Path(tmp).write_bytes(data)
                self.robot.submit("audio", path=tmp)
                self._send(*_json_bytes({"ok": True, "cmd": "audio", "bytes": len(data)}))
                return
            if path == "/v1/wifi":
                body = self._read_json()
                self.robot.submit(
                    "wifi_join",
                    ssid=body.get("ssid"),
                    password=body.get("password"),
                    iface=body.get("iface") or body.get("wifi_device"),
                )
                self._send(*_json_bytes({"ok": True, "cmd": "wifi_join"}))
                return
            self._send(*_json_bytes({"ok": False, "error": "not found"}, 404))
        except ValueError as exc:
            self._send(*_json_bytes({"ok": False, "error": str(exc)}, 400))
        except Exception as exc:  # noqa: BLE001
            log.exception("POST %s", path)
            self._send(*_json_bytes({"ok": False, "error": str(exc)}, 500))


def serve(robot: RobotSession, host: str, port: int, token: str = "") -> ThreadingHTTPServer:
    handler = type(
        "BoundHandler",
        (CompanionHandler,),
        {"robot": robot, "token": token},
    )
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd
